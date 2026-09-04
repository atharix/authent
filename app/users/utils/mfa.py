"""Piezas de apoyo del segundo factor.

Aquí vive lo que no es ni modelo ni vista: los tokens firmados que unen los dos
pasos del login, el enmascarado del correo, el arranque/reenvío del código y la
elección del método (app o correo) para cada intento.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.utils import timezone

from users.models.mfa import EmailOtp, LoginApproval, PushApprover

logger = logging.getLogger(__name__)

MFA_TOKEN_SALT = "authent.mfa.email"
# Techo de correos por usuario y hora. Sin él, quien tenga la contraseña puede
# repetir el login cada 61 s indefinidamente: bombardea el buzón de su víctima y
# se come el presupuesto de envío, cuyo primer síntoma es que dejan de llegar
# NUESTROS propios códigos por reputación del dominio.
MAX_OTPS_PER_HOUR = 5
# El token del paso 1 vive lo mismo que el código: si caduca uno, el otro no
# sirve para nada. Un pelín más para absorber relojes desalineados.
MFA_TOKEN_MAX_AGE = EmailOtp.TTL_SECONDS + 60


def make_mfa_token(otp_id):
    """Token opaco y firmado que el cliente devuelve en el paso 2.

    Firmado en vez de un id crudo para que el cliente no pueda apuntar a otro
    registro ni enumerar los ajenos.
    """
    return signing.dumps({"otp": str(otp_id)}, salt=MFA_TOKEN_SALT)


def read_mfa_token(token):
    """Devuelve el id del OTP o None si el token es inválido o caducó."""
    try:
        payload = signing.loads(token, salt=MFA_TOKEN_SALT, max_age=MFA_TOKEN_MAX_AGE)
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict):
        return None
    return payload.get("otp")


def mask_email(email):
    """``lmendoza@projects.ec`` → ``l*******a@projects.ec``.

    Basta para que el usuario reconozca su buzón sin publicar la dirección
    entera en una pantalla que puede quedar a la vista de otros.
    """
    email = (email or "").strip()
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local[:1]}*@{domain}"
    return f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}@{domain}"


def application_code_of(request):
    """Discriminante estable del producto que llama.

    Se prefiere ``code``, pero no todas las Application lo tienen (en local,
    Atlas, Hub e Iris lo tienen a NULL). Cayendo al id se evita que tres
    productos sin código compartan el mismo discriminante y que un equipo de
    confianza o un desafío de uno valgan en otro.
    """
    application = getattr(request, "application", None)
    if application is None:
        return ""
    return getattr(application, "code", None) or str(getattr(application, "id", "") or "")


def mfa_enforced(request):
    """¿El producto que llama exige segundo factor?

    Se decide por Application (igual que ``enforce_app_access``) para poder
    encenderlo en Atlas sin romper a Metis ni Prometheus, cuyos frontales aún
    no saben leer una respuesta de dos pasos.
    """
    application = getattr(request, "application", None)
    return bool(getattr(application, "enforce_mfa", False))


def start_email_otp(user, request):
    """Emite el código y lo envía.

    Devuelve ``(otp, resultado)`` con resultado en
    ``sent | reused | rate_limited | failed``.

    Si el usuario ya tiene un código vivo dentro de la ventana de reenvío, se
    reutiliza sin mandar otro correo: con la contraseña correcta en la mano,
    repetir el login sería si no una forma de bombardear un buzón ajeno (y de
    quemar cuota de Resend, que acaba pasándole factura a la reputación del
    dominio y por tanto a la entrega de nuestros propios códigos).
    """
    live = (
        EmailOtp.objects.filter(user=user, status=EmailOtp.PENDING)
        .order_by("-created_at")
        .first()
    )
    if live and live.is_active and live.attempts_left > 0 and live.resend_in > 0:
        return live, "reused"

    recent = EmailOtp.objects.filter(
        user=user, created_at__gte=timezone.now() - timedelta(hours=1)
    ).count()
    if recent >= MAX_OTPS_PER_HOUR:
        return live, "rate_limited"

    otp, code = EmailOtp.issue(user, application_code=application_code_of(request))
    if not send_otp_email(user, code, otp):
        # Sin correo entregado no hay segundo paso posible: se anula el registro
        # para que el siguiente intento emita uno nuevo en vez de chocar contra
        # el cooldown de un código que nunca llegó.
        otp.mark_cancelled()
        return otp, "failed"
    return otp, "sent"


def send_otp_email(user, code, otp):
    """Envía el código. Nunca revienta el login: devuelve False si falla."""
    from users.tasks import send_mfa_code_email

    try:
        send_mfa_code_email(user, code, otp)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("No se pudo enviar el código MFA a %s: %s", user.email, exc)
        return False


def challenge_payload(otp, user, delivered=True):
    """Cuerpo del paso 1 del login. Sin tokens: aún no hay sesión."""
    return {
        "mfa_required": True,
        "mfa_method": "email",
        "mfa_token": make_mfa_token(otp.id),
        "email_hint": mask_email(user.email),
        "code_length": EmailOtp.CODE_LENGTH,
        "expires_in": EmailOtp.TTL_SECONDS,
        "resend_in": otp.resend_in,
        "delivered": delivered,
    }


# ── Aprobación desde la app (segundo factor por push) ───────────────────────

APPROVAL_TOKEN_SALT = "authent.mfa.push"
APPROVAL_TOKEN_MAX_AGE = LoginApproval.TTL_SECONDS + 60


def make_approval_token(approval_id):
    """Token opaco del paso 1 cuando el factor es la app."""
    return signing.dumps({"apr": str(approval_id)}, salt=APPROVAL_TOKEN_SALT)


def read_approval_token(token):
    try:
        payload = signing.loads(
            token, salt=APPROVAL_TOKEN_SALT, max_age=APPROVAL_TOKEN_MAX_AGE
        )
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict):
        return None
    return payload.get("apr")


def push_approval_enabled():
    """Interruptor de despliegue, independiente de que haya aprobadores.

    Existe para poder tener el código en producción antes que las apps en las
    tiendas: mientras esté apagado, un aprobador enrolado tampoco cambia nada.
    """
    return bool(getattr(settings, "PUSH_APPROVAL_ENABLED", False))


def resolve_push_approver(user, request):
    """El aprobador que atenderá este login, o None para caer al correo.

    Devolver None es el camino normal de casi todo el mundo: sin app instalada
    y enrolada no hay push que mandar, así que el segundo factor sigue siendo
    el código por correo de siempre.
    """
    if not push_approval_enabled():
        return None
    return PushApprover.active_for(user, application_code_of(request))


def start_push_approval(user, approver, request):
    """Abre la solicitud que el teléfono tendrá que aprobar."""
    return LoginApproval.issue(
        user,
        approver,
        application_code=application_code_of(request),
        device_name=describe_login_device(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        ip_address=client_ip(request),
    )


def describe_login_device(request):
    """Etiqueta corta del equipo que pide entrar, para enseñarla en el móvil."""
    from users.utils.session import parse_user_agent

    info = parse_user_agent(request.META.get("HTTP_USER_AGENT", ""))
    browser = info.get("browser") or ""
    os_name = info.get("os_name") or ""
    return " · ".join(part for part in (browser, os_name) if part and part != "Other")


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def push_challenge_payload(approval, approver):
    """Cuerpo del paso 1 cuando aprueba la app.

    ``expected_number`` es para la pantalla que pide entrar: es el número que
    hay que enseñar. Los tres candidatos NO salen de aquí — los pide la app con
    su propia sesión, para que ni el navegador ni el push los conozcan.

    ``delivery`` es para el producto que entrega el aviso, no para el
    navegador: el proxy lo consume y lo quita antes de responder al cliente.
    """
    return {
        "mfa_required": True,
        "mfa_method": "push",
        "mfa_token": make_approval_token(approval.id),
        "expected_number": approval.expected_number,
        "expires_in": approval.expires_in,
        "approver_label": approver.device_label,
        "delivered": True,
        "delivery": {
            "approval_id": str(approval.id),
            "approver_ref": approver.delivery_ref,
            "device_name": approval.device_name,
            "location": approval.location,
        },
    }
