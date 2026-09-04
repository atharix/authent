import logging

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from ..models import PasswordReset, User
from ..tasks import send_password_reset_email

logger = logging.getLogger(__name__)


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request."""

    email = serializers.EmailField()

    def validate_email(self, value):
        """Validate that user exists."""
        try:
            User.objects.get(email__iexact=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist")
        return value

    def save(self):
        """Create password reset request and send email."""
        email = self.validated_data["email"]
        user = User.objects.get(email__iexact=email, is_active=True)

        # Create reset request
        reset = PasswordReset.objects.create(
            user=user,
            hash_token=PasswordReset.generate_hash(),
            pin=PasswordReset.generate_pin(),
        )

        # Send reset email directly
        try:
            send_password_reset_email(
                user.email, user.first_name, reset.pin, reset.hash_token
            )
            logger.info("Password reset email sent for %s", user.email)
        except Exception as exc:
            logger.error(
                "Failed to send password reset email for %s: %s",
                user.email,
                exc,
            )

        return {"hash_token": reset.hash_token}


class PasswordResetVerifySerializer(serializers.Serializer):
    """Serializer for PIN verification."""

    email = serializers.EmailField()
    hash_token = serializers.CharField(max_length=64)
    pin = serializers.CharField(max_length=4, min_length=4)

    def validate(self, attrs):
        """Validate hash token and PIN combination."""
        try:
            reset = PasswordReset.objects.get(
                user__email__iexact=attrs["email"],
                hash_token=attrs["hash_token"],
                pin=attrs["pin"],
            )

            if not reset.is_valid():
                raise serializers.ValidationError(
                    "Reset request has expired or already used"
                )

            attrs["reset"] = reset

        except PasswordReset.DoesNotExist:
            raise serializers.ValidationError("Invalid reset credentials")

        return attrs


class SimplePinVerifySerializer(serializers.Serializer):
    """Simplified serializer for PIN verification (only email and code)."""

    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=4)

    def validate(self, attrs):
        """Validate email and PIN combination without requiring hash_token."""
        try:
            reset = PasswordReset.objects.get(
                user__email__iexact=attrs["email"],
                pin=attrs["code"],
            )

            if not reset.is_valid():
                raise serializers.ValidationError(
                    "Reset request has expired or already used"
                )

            attrs["reset"] = reset

        except PasswordReset.DoesNotExist:
            raise serializers.ValidationError("Invalid PIN or email")

        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation."""

    email = serializers.EmailField()
    hash_token = serializers.CharField(max_length=64)
    pin = serializers.CharField(max_length=4, min_length=4)
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()

    def validate(self, attrs):
        """Validate all parameters and password confirmation."""
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError("Passwords don't match")

        try:
            reset = PasswordReset.objects.get(
                user__email__iexact=attrs["email"],
                hash_token=attrs["hash_token"],
                pin=attrs["pin"],
            )

            if not reset.is_valid():
                raise serializers.ValidationError(
                    "Reset request has expired or already used"
                )

            attrs["reset"] = reset

        except PasswordReset.DoesNotExist:
            raise serializers.ValidationError("Invalid reset credentials")

        return attrs

    def save(self):
        """Reset password and mark request as used."""
        reset = self.validated_data["reset"]
        new_password = self.validated_data["new_password"]

        # Update password
        user = reset.user
        user.set_password(new_password)
        user.save()

        # Mark reset as used
        reset.mark_as_used()
        revoke_trust_after_password_change(user)

        return user


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for changing password when logged in."""

    current_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()

    def __init__(self, *args, **kwargs):
        """Initialize with user instance."""
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def validate_current_password(self, value):
        """Validate current password."""
        if not self.user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect")
        return value

    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError("New passwords don't match")
        return attrs

    def save(self):
        """Change user password."""
        self.user.set_password(self.validated_data["new_password"])
        self.user.save()
        revoke_trust_after_password_change(self.user)
        return self.user


class SimplePasswordResetSerializer(serializers.Serializer):
    """Simplified serializer for password reset with PIN (email + code + newPassword)."""

    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=4)
    newPassword = serializers.CharField(validators=[validate_password])

    def validate(self, attrs):
        """Validate email and PIN combination."""
        try:
            reset = PasswordReset.objects.get(
                user__email__iexact=attrs["email"],
                pin=attrs["code"],
            )

            if not reset.is_valid():
                raise serializers.ValidationError(
                    "Reset request has expired or already used"
                )

            attrs["reset"] = reset

        except PasswordReset.DoesNotExist:
            raise serializers.ValidationError("Invalid PIN or email")

        return attrs

    def save(self):
        """Reset password and mark request as used."""
        reset = self.validated_data["reset"]
        new_password = self.validated_data["newPassword"]

        # Update password
        user = reset.user
        user.set_password(new_password)
        user.save()

        # Mark reset as used
        reset.mark_as_used()
        revoke_trust_after_password_change(user)

        return user


def revoke_trust_after_password_change(user):
    """Un cambio de contraseña tira todos los equipos de confianza.

    Sin esto, quien controla el buzón resetea la contraseña y conserva un
    dispositivo que se salta el segundo factor de forma renovable.
    """
    from ..models.mfa import EmailOtp, TrustedDevice

    TrustedDevice.revoke_all_for(user)
    EmailOtp.objects.filter(user=user, status=EmailOtp.PENDING).update(
        status=EmailOtp.CANCELLED
    )
