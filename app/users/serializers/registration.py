import logging

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from ..models import User

logger = logging.getLogger(__name__)


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords don't match"}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        user = User.objects.create_user(email_verified=True, **validated_data)
        logger.info("New user registered: %s", user.email)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "birth_date",
            "phone_number",
            "gender",
            "avatar",
        ]

    def validate_phone_number(self, value):
        if (
            value
            and not value.replace("+", "").replace("-", "").replace(" ", "").isdigit()
        ):
            raise serializers.ValidationError("Invalid phone number format")
        return value


logger = logging.getLogger(__name__)

VERIFICATION_SALT = "email-verification"
REGISTRATION_SALT = "registration-otp"
