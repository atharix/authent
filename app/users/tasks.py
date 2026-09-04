import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_password_reset_email(user_email, user_name, pin_code, hash_token):
    """Send password reset email with PIN code."""
    subject = "Restablecer contraseña - Authent"
    context = {
        "user_name": user_name,
        "pin_code": pin_code,
        "hash_token": hash_token,
        "site_name": "Authent",
    }
    html_message = render_to_string("auth/emails/password_reset.html", context)
    text_message = render_to_string("auth/emails/password_reset.txt", context)
    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user_email],
        fail_silently=False,
    )
    logger.info("Password reset email sent to %s", user_email)


def send_mfa_code_email(user, code, otp):
    """Envía el código de verificación en dos pasos del login.

    Síncrono como el resto de correos de la app: el usuario está esperando en la
    pantalla del código, así que un envío diferido solo trasladaría el fallo a un
    punto donde ya no se lo podemos contar.
    """
    subject = "Tu código de acceso - Authent"
    context = {
        "user_name": user.get_full_name() or user.email,
        "pin_code": code,
        "code_length": otp.CODE_LENGTH,
        "expires_minutes": otp.TTL_SECONDS // 60,
        "max_attempts": otp.MAX_ATTEMPTS,
        "site_name": "Authent",
    }
    html_message = render_to_string("auth/emails/mfa_code.html", context)
    text_message = render_to_string("auth/emails/mfa_code.txt", context)
    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    logger.info("MFA code email sent to %s", user.email)
