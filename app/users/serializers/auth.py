from core.utils.s3_signed_url import get_avatar_url
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from ..models import User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer with additional user information."""

    @classmethod
    def get_token(cls, user):
        """Add custom claims to token."""
        token = super().get_token(user)

        # Add custom claims
        token["email"] = user.email
        token["first_name"] = user.first_name
        token["last_name"] = user.last_name
        token["full_name"] = user.get_full_name()
        token["is_staff"] = user.is_staff
        token["is_superuser"] = user.is_superuser
        token["email_verified"] = user.email_verified
        token["user_id"] = str(user.id)
        token["profile_type"] = user.profile_type

        return token

    @classmethod
    def _user_payload(cls, user):
        """Update last_login and return the serialized user block."""
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        avatar_url = get_avatar_url(user.avatar, expiration=1800)

        return {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.get_full_name(),
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "email_verified": user.email_verified,
            "profile_type": user.profile_type,
            "date_joined": user.date_joined,
            "last_login": user.last_login,
            "avatar": avatar_url,
        }

    @classmethod
    def build_response_for_user(cls, user):
        """Build the {access, refresh, user} payload for a user without a password.

        Shared with passwordless logins (e.g. passkeys) so their response is
        byte-for-byte identical to the password login below.
        """
        refresh = cls.get_token(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": cls._user_payload(user),
        }

    def validate(self, attrs):
        """Validate credentials and update last login."""
        data = super().validate(attrs)
        data["user"] = self._user_payload(self.user)
        return data


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login."""

    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, attrs):
        """Validate user credentials."""
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            user = authenticate(
                request=self.context.get("request"),
                email=email,
                password=password,
            )

            if not user:
                raise serializers.ValidationError(
                    "Invalid email or password.", code="authorization"
                )

            if not user.is_active:
                raise serializers.ValidationError(
                    "User account is disabled.", code="authorization"
                )

            attrs["user"] = user
            return attrs
        else:
            raise serializers.ValidationError(
                'Must include "email" and "password".', code="authorization"
            )


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile information."""

    full_name = serializers.SerializerMethodField()
    avatar_path = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "birth_date",
            "phone_number",
            "gender",
            "avatar_path",
            "email_verified",
            "profile_type",
            "is_superuser",
            "date_joined",
            "last_login",
        ]
        read_only_fields = [
            "id",
            "email",
            "email_verified",
            "profile_type",
            "is_superuser",
            "date_joined",
            "last_login",
            "avatar_path",
        ]

    def get_full_name(self, obj):
        """Return user's full name."""
        return obj.get_full_name()

    def get_avatar_path(self, obj):
        """Return avatar file path for use with signed URL endpoint."""
        if obj.avatar:
            return obj.avatar.name
        return None
