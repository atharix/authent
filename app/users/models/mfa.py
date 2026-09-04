"""Segundo factor por correo (OTP) y dispositivos de confianza.

El OTP se emite DESPUÉS de validar la contraseña y ANTES de acuñar los tokens:
mientras no se verifica, no existe sesión (ver ``users/views/auth.py``). Eso es
lo que separa un segundo factor real de un diálogo en el cliente.

El molde es ``EmailVerification`` del paquete ``atharix_authent_django`` (alta de
cuenta), no ``PasswordReset``: PIN hasheado, contador de intentos en la fila y
caducidad. Los contadores viven en la BD y no en cache porque los entornos de
desarrollo corren con DummyCache y allí un cooldown en cache no existe.
"""

import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


def hash_opaque_token(raw: str) -> str:
    """SHA-256 de un token opaco de alta entropía.

    No lleva sal ni derivación lenta a propósito: el valor tiene 256 bits de
    aleatoriedad, así que no hay diccionario que atacar y la búsqueda por hash
    tiene que ser indexable.
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class EmailOtp(models.Model):
    """Código de un solo uso enviado por correo como segundo factor de login."""

    CODE_LENGTH = 6
    TTL_SECONDS = 600
    MAX_ATTEMPTS = 5
    MAX_SENDS = 5
    RESEND_COOLDOWN_SECONDS = 60

    PENDING = "pending"
    USED = "used"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (USED, "Used"),
        (CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_otps",
        verbose_name="User",
    )
    application_code = models.CharField(
        "Application code",
        max_length=50,
        blank=True,
        help_text="Producto que inició el login (Application.code).",
    )
    code_hash = models.CharField("Code hash", max_length=256)
    attempts = models.PositiveIntegerField("Attempts", default=0)
    sends = models.PositiveIntegerField("Sends", default=1)
    status = models.CharField(
        "Status", max_length=16, choices=STATUS_CHOICES, default=PENDING, db_index=True
    )
    created_at = models.DateTimeField("Created at", auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField("Expires at", db_index=True)
    last_sent_at = models.DateTimeField("Last sent at", default=timezone.now)
    used_at = models.DateTimeField("Used at", null=True, blank=True)

    class Meta:
        db_table = "auth_email_otp"
        verbose_name = "Email OTP"
        verbose_name_plural = "Email OTPs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "expires_at"]),
        ]

    def __str__(self):
        return f"EmailOtp({self.user_id} · {self.status})"

    # ── Creación ────────────────────────────────────────────────────────────
    @staticmethod
    def generate_code():
        """Código numérico de CODE_LENGTH dígitos, uniforme y sin sesgo."""
        upper = 10**EmailOtp.CODE_LENGTH
        return str(secrets.randbelow(upper)).zfill(EmailOtp.CODE_LENGTH)

    @classmethod
    def issue(cls, user, application_code=""):
        """Cancela los pendientes del usuario y crea uno nuevo.

        Devuelve ``(otp, codigo_en_claro)``. El código en claro solo existe aquí
        y en el correo: en la fila queda el hash.
        """
        cls.objects.filter(user=user, status=cls.PENDING).update(
            status=cls.CANCELLED
        )
        code = cls.generate_code()
        otp = cls.objects.create(
            user=user,
            application_code=application_code or "",
            code_hash=make_password(code),
            expires_at=timezone.now() + timedelta(seconds=cls.TTL_SECONDS),
        )
        return otp, code

    def apply_code(self, code):
        """Fija un código ya entregado: mismo registro, caducidad nueva.

        Recibe el código en vez de generarlo para que el envío ocurra ANTES de
        matar el anterior: si el correo falla, el usuario conserva el que sí le
        llegó en lugar de quedarse sin ninguno.

        Los intentos NO se reinician: si no, pedir reenvío sería una forma
        gratuita de resetear el contador y volver a tener 5 tiros por código.
        """
        self.code_hash = make_password(code)
        self.sends += 1
        self.last_sent_at = timezone.now()
        self.expires_at = timezone.now() + timedelta(seconds=self.TTL_SECONDS)
        self.save(update_fields=["code_hash", "sends", "last_sent_at", "expires_at"])
        return code

    # ── Estado ──────────────────────────────────────────────────────────────
    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_active(self):
        return self.status == self.PENDING and not self.is_expired

    @property
    def attempts_left(self):
        return max(0, self.MAX_ATTEMPTS - self.attempts)

    @property
    def can_resend(self):
        return self.sends < self.MAX_SENDS and self.resend_in == 0

    @property
    def resend_in(self):
        """Segundos que faltan para poder reenviar; 0 si ya se puede."""
        elapsed = (timezone.now() - self.last_sent_at).total_seconds()
        return max(0, int(self.RESEND_COOLDOWN_SECONDS - elapsed))

    # ── Verificación ────────────────────────────────────────────────────────
    def claim_attempt(self):
        """Reclama un intento de forma atómica. Devuelve False si no quedaba.

        Leer, sumar uno y guardar desde Python es un lost update de manual: con
        peticiones simultáneas todas leen el mismo valor y el tope de 5 intentos
        se convierte en cientos. El UPDATE condicional deja que la base de datos
        arbitre, y la comparación PBKDF2 (~200 ms) mantiene la ventana abierta
        el tiempo suficiente como para que esto no sea teórico.
        """
        claimed = (
            type(self)
            .objects.filter(
                pk=self.pk,
                status=self.PENDING,
                attempts__lt=self.MAX_ATTEMPTS,
                expires_at__gt=timezone.now(),
            )
            .update(attempts=models.F("attempts") + 1)
        )
        if not claimed:
            return False
        self.refresh_from_db(fields=["attempts", "status", "expires_at", "code_hash"])
        return True

    def consume(self):
        """Marca el código como usado exactamente una vez.

        Que dos peticiones con el código correcto lleguen a la vez y las dos
        reciban tokens no rompe nada hoy, pero convierte un código de un solo
        uso en uno de varios. El UPDATE condicional lo cierra.
        """
        return (
            type(self)
            .objects.filter(pk=self.pk, status=self.PENDING)
            .update(status=self.USED, used_at=timezone.now())
            == 1
        )

    def check_code(self, raw_code):
        return check_password(raw_code or "", self.code_hash)

    def mark_used(self):
        self.status = self.USED
        self.used_at = timezone.now()
        self.save(update_fields=["status", "used_at"])

    def mark_cancelled(self):
        self.status = self.CANCELLED
        self.save(update_fields=["status"])


class TrustedDevice(models.Model):
    """Equipo donde el segundo factor ya se superó, válido TTL_DAYS días.

    El secreto lo emite el servidor y solo se guarda su hash: el cliente
    presenta el valor en claro en el login y aquí se resuelve por hash. Nunca se
    confía en un sello escrito por el cliente (que es exactamente el defecto de
    la válvula de escape del PasskeyGate).
    """

    TTL_DAYS = 30

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trusted_devices",
        verbose_name="User",
    )
    application_code = models.CharField("Application code", max_length=50, blank=True)
    token_hash = models.CharField(
        "Token hash", max_length=64, unique=True, db_index=True
    )
    device_name = models.CharField("Device name", max_length=255, blank=True)
    user_agent = models.TextField("User agent", blank=True)
    ip_address = models.GenericIPAddressField("IP address", null=True, blank=True)
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    last_used_at = models.DateTimeField("Last used at", default=timezone.now)
    expires_at = models.DateTimeField("Expires at", db_index=True)
    revoked_at = models.DateTimeField("Revoked at", null=True, blank=True)

    class Meta:
        db_table = "auth_trusted_device"
        verbose_name = "Trusted device"
        verbose_name_plural = "Trusted devices"
        ordering = ["-last_used_at"]
        indexes = [models.Index(fields=["user", "revoked_at"])]

    def __str__(self):
        return f"TrustedDevice({self.user_id} · {self.device_name or 'sin nombre'})"

    @classmethod
    def issue(cls, user, application_code="", device_name="", user_agent="", ip=None):
        """Crea el registro y devuelve ``(instancia, token_en_claro)``."""
        raw = secrets.token_urlsafe(32)
        device = cls.objects.create(
            user=user,
            application_code=application_code or "",
            token_hash=hash_opaque_token(raw),
            device_name=(device_name or "")[:255],
            user_agent=user_agent or "",
            ip_address=ip,
            expires_at=timezone.now() + timedelta(days=cls.TTL_DAYS),
        )
        return device, raw

    @classmethod
    def resolve(cls, raw_token, user, application_code=""):
        """Devuelve el dispositivo vivo de ESE usuario, o None.

        Atar la búsqueda al usuario evita que un token robado sirva para otra
        cuenta, y filtrar por producto evita que la confianza ganada en un
        producto abra otro.
        """
        # Un cliente puede mandar cualquier cosa en el JSON: sin este guardia,
        # un `device_token` que sea lista o diccionario revienta el login con un
        # 500 al llamar a .encode().
        if not raw_token or not isinstance(raw_token, str):
            return None
        try:
            device = cls.objects.get(token_hash=hash_opaque_token(raw_token))
        except cls.DoesNotExist:
            return None
        if device.user_id != user.id:
            return None
        # Se comparan SIEMPRE, normalizados: si solo se comprobara cuando el
        # producto que pregunta trae código, una Application sin `code` haría
        # que la confianza ganada en un producto valiera en todos.
        if (device.application_code or "") != (application_code or ""):
            return None
        if not device.is_valid:
            return None
        return device

    @property
    def is_valid(self):
        return self.revoked_at is None and timezone.now() < self.expires_at

    def touch(self, ip=None, user_agent=""):
        self.last_used_at = timezone.now()
        fields = ["last_used_at"]
        if ip:
            self.ip_address = ip
            fields.append("ip_address")
        if user_agent:
            self.user_agent = user_agent
            fields.append("user_agent")
        self.save(update_fields=fields)

    def revoke(self):
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])

    @classmethod
    def revoke_all_for(cls, user):
        """Se llama al cambiar o resetear la contraseña.

        Si no, quien controla el buzón resetea la contraseña y conserva un
        equipo de confianza renovable indefinidamente.
        """
        return cls.objects.filter(user=user, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )


class PushApprover(models.Model):
    """App instalada que puede autorizar inicios de sesión de su dueño.

    Authent no sabe entregar notificaciones: no conoce tokens de Expo ni de
    FCM. Lo único que guarda aquí es que ESE usuario tiene un aprobador vivo en
    ESE producto, más una referencia opaca (``delivery_ref``) que solo el
    producto sabe resolver. Así el segundo factor por push se decide en el
    login, que es donde vive la autoridad, y la entrega la hace quien tiene los
    tokens.

    Sin filas activas aquí no existe el método push: el login cae al código por
    correo. Por eso un usuario que nunca ha instalado la app no puede quedarse
    fuera de su cuenta.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_approvers",
        verbose_name="User",
    )
    application_code = models.CharField("Application code", max_length=50, blank=True)
    delivery_ref = models.CharField(
        "Delivery reference",
        max_length=255,
        help_text="Identificador opaco que el producto usa para entregar el aviso.",
    )
    device_label = models.CharField("Device label", max_length=255, blank=True)
    platform = models.CharField("Platform", max_length=20, blank=True)
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    last_used_at = models.DateTimeField("Last used at", null=True, blank=True)
    revoked_at = models.DateTimeField("Revoked at", null=True, blank=True)

    class Meta:
        db_table = "auth_push_approver"
        verbose_name = "Push approver"
        verbose_name_plural = "Push approvers"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "revoked_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "application_code", "delivery_ref"],
                condition=models.Q(revoked_at__isnull=True),
                name="uniq_active_push_approver",
            )
        ]

    def __str__(self):
        return f"PushApprover({self.user_id} · {self.device_label or self.delivery_ref})"

    @property
    def is_active(self):
        return self.revoked_at is None

    @classmethod
    def active_for(cls, user, application_code=""):
        """El aprobador vigente del usuario en ese producto, o None.

        Se queda con el más reciente: cambiar de teléfono es reenrolar, y el
        aparato viejo no debería seguir siendo la llave de la cuenta.
        """
        qs = cls.objects.filter(user=user, revoked_at__isnull=True)
        if application_code:
            qs = qs.filter(application_code=application_code)
        return qs.order_by("-created_at").first()

    def touch(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])

    def revoke(self):
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])

    @classmethod
    def revoke_all_for(cls, user):
        return cls.objects.filter(user=user, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )


class LoginApproval(models.Model):
    """Un intento de login esperando el visto bueno del teléfono.

    Lleva tres números: el navegador enseña el que toca y la app pide elegirlo
    entre los tres. Es lo que impide aprobar a ciegas — sin la pantalla delante
    la probabilidad de acertar es 1 de 3, y fallar tumba el intento.
    """

    TTL_SECONDS = 120
    NUMBER_CHOICES = 3

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    USED = "used"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (DENIED, "Denied"),
        (USED, "Used"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="login_approvals",
        verbose_name="User",
    )
    approver = models.ForeignKey(
        PushApprover,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approvals",
        verbose_name="Approver",
    )
    application_code = models.CharField("Application code", max_length=50, blank=True)
    status = models.CharField(
        "Status", max_length=16, choices=STATUS_CHOICES, default=PENDING, db_index=True
    )
    numbers = models.JSONField("Numbers", default=list)
    expected_number = models.PositiveSmallIntegerField("Expected number")

    device_name = models.CharField("Device name", max_length=255, blank=True)
    user_agent = models.TextField("User agent", blank=True)
    ip_address = models.GenericIPAddressField("IP address", null=True, blank=True)
    location = models.CharField("Location", max_length=255, blank=True)

    created_at = models.DateTimeField("Created at", auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField("Expires at", db_index=True)
    resolved_at = models.DateTimeField("Resolved at", null=True, blank=True)
    used_at = models.DateTimeField("Used at", null=True, blank=True)

    class Meta:
        db_table = "auth_login_approval"
        verbose_name = "Login approval"
        verbose_name_plural = "Login approvals"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "expires_at"]),
        ]

    def __str__(self):
        return f"LoginApproval({self.user_id} · {self.status})"

    @staticmethod
    def generate_numbers():
        """Tres números de dos cifras distintos, y cuál es el bueno."""
        pool = list(range(10, 100))
        numbers = []
        for _ in range(LoginApproval.NUMBER_CHOICES):
            numbers.append(pool.pop(secrets.randbelow(len(pool))))
        return numbers, numbers[secrets.randbelow(len(numbers))]

    @classmethod
    def issue(cls, user, approver, application_code="", **metadata):
        """Cancela los pendientes del usuario y abre uno nuevo.

        Uno vivo a la vez: dos solicitudes simultáneas en la pantalla del
        teléfono son justo la confusión que el emparejamiento por número existe
        para evitar.
        """
        cls.objects.filter(user=user, status=cls.PENDING).update(
            status=cls.DENIED, resolved_at=timezone.now()
        )
        numbers, expected = cls.generate_numbers()
        return cls.objects.create(
            user=user,
            approver=approver,
            application_code=application_code or "",
            numbers=numbers,
            expected_number=expected,
            device_name=(metadata.get("device_name") or "")[:255],
            user_agent=metadata.get("user_agent") or "",
            ip_address=metadata.get("ip_address"),
            location=(metadata.get("location") or "")[:255],
            expires_at=timezone.now() + timedelta(seconds=cls.TTL_SECONDS),
        )

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_pending(self):
        return self.status == self.PENDING and not self.is_expired

    @property
    def expires_in(self):
        return max(0, int((self.expires_at - timezone.now()).total_seconds()))

    def approve(self, chosen_number):
        """Aprueba si el número es el que enseñaba el navegador.

        Fallar no da otra oportunidad: quien no tiene la pantalla delante está
        adivinando, y tres intentos convertirían un 33% en casi un 70%.
        """
        if not self.is_pending:
            return False
        if chosen_number != self.expected_number:
            self.deny()
            return False
        self.status = self.APPROVED
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolved_at"])
        return True

    def deny(self):
        self.status = self.DENIED
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolved_at"])

    def mark_used(self):
        self.status = self.USED
        self.used_at = timezone.now()
        self.save(update_fields=["status", "used_at"])
