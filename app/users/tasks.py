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
