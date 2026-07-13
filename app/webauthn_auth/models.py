import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

CHALLENGE_TTL_SECONDS = 300


def generate_state() -> str:
    return secrets.token_urlsafe(32)


def default_challenge_expiry():
    return timezone.now() + timedelta(seconds=CHALLENGE_TTL_SECONDS)


class WebAuthnCredential(models.Model):
    """A passkey (WebAuthn public-key credential) enrolled by a user.

    ``credential_id`` and ``public_key`` are stored base64url-encoded: that is
    how py_webauthn exchanges them and it lets the authentication ceremony
    resolve the credential directly from the assertion's ``rawId``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="webauthn_credentials",
    )
    # RP ID con el que se creó la credencial. El autenticador la guarda atada a
    # ese dominio y NO la ofrece para otro, así que al cambiar WEBAUTHN_RP_ID
    # todas las anteriores quedan muertas — aunque su fila siga aquí.
    #
    # Sin este campo el sistema no distingue vivas de zombis: el listado decía
    # "ya tienes passkey", la UI no ofrecía registrar una nueva, y el usuario se
    # quedaba sin poder entrar y sin forma de arreglarlo. Guardarlo hace que un
    # cambio de RP ID se cure solo: las viejas dejan de contar y la app pide
    # registrar de nuevo.
    rp_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    credential_id = models.CharField(max_length=512, unique=True, db_index=True)
    public_key = models.TextField()
    sign_count = models.BigIntegerField(default=0)
    aaguid = models.CharField(max_length=36, blank=True, default="")
    transports = models.JSONField(default=list, blank=True)
    friendly_name = models.CharField(max_length=120, blank=True, default="")
    backup_eligible = models.BooleanField(default=False)
    backup_state = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "webauthn_credential"
        verbose_name = "WebAuthn Credential"
        verbose_name_plural = "WebAuthn Credentials"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "created_at"])]

    def __str__(self):
        return f"{self.friendly_name or 'passkey'} · {self.user_id}"


class WebAuthnChallenge(models.Model):
    """Short-lived, single-use challenge for a registration/authentication ceremony.

    Stored in the database (not the cache) because the dev environment uses
    DummyCache, which silently discards writes and would break the flow.
    """

    CEREMONY_REGISTRATION = "registration"
    CEREMONY_AUTHENTICATION = "authentication"
    CEREMONY_CHOICES = [
        (CEREMONY_REGISTRATION, "Registration"),
        (CEREMONY_AUTHENTICATION, "Authentication"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.CharField(
        max_length=64, unique=True, db_index=True, default=generate_state
    )
    ceremony = models.CharField(max_length=20, choices=CEREMONY_CHOICES)
    challenge = models.TextField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="webauthn_challenges",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_challenge_expiry, db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "webauthn_challenge"
        indexes = [models.Index(fields=["state", "expires_at"])]

    @property
    def is_valid(self) -> bool:
        return self.consumed_at is None and self.expires_at > timezone.now()

    def consume(self):
        self.consumed_at = timezone.now()
        self.save(update_fields=["consumed_at"])
