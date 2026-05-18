import logging

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import PasswordReset, TermsAndConditions, User, UserTermsAcceptance
from .tasks import send_password_reset_email

logger = logging.getLogger(__name__)


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    terms_version = serializers.BooleanField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
            "birth_date",
            "phone",
            "gender",
            "avatar",
            "terms_version",
        ]
        extra_kwargs = {
            "avatar": {"required": False},
        }

    def validate(self, attrs):
        """Validate password confirmation and terms acceptance."""
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError("Passwords don't match")

        if attrs["terms_version"] is not True:
            raise serializers.ValidationError("Invalid or inactive terms version")

        attrs["terms"] = TermsAndConditions.objects.filter(is_active=True).last()

        return attrs

    def create(self, validated_data):
        """Create user and record terms acceptance."""
        validated_data.pop("password_confirm")
        terms = validated_data.pop("terms")
        validated_data.pop("terms_version")

        user = User.objects.create_user(**validated_data)

        # Record terms acceptance
        UserTermsAcceptance.objects.create(
            user=user,
            terms=terms,
            ip_address=self.context.get("request").META.get("REMOTE_ADDR"),
        )

        return user


class UserLoginSerializer(TokenObtainPairSerializer):
    """Custom login serializer with email as username."""

    username_field = "email"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"] = serializers.EmailField()
        self.fields.pop("username", None)

    def validate(self, attrs):
        """Validate credentials and return user data."""
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            user = authenticate(
                request=self.context.get("request"),
                email=email,
                password=password,
            )

            if not user:
                raise serializers.ValidationError("Invalid email or password")

            if not user.is_active:
                raise serializers.ValidationError("User account is disabled")

            attrs["user"] = user

        # Get JWT tokens
        refresh = self.get_token(user)
        attrs["refresh"] = str(refresh)
        attrs["access"] = str(refresh.access_token)

        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile."""

    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "birth_date",
            "phone",
            "gender",
            "avatar",
            "date_joined",
            "email_verified",
        ]
        read_only_fields = ["id", "email", "date_joined", "email_verified"]


class UserBasicSerializer(serializers.ModelSerializer):
    """
    Basic user serializer for nested representations.
    Includes essential user information including avatar.
    """

    full_name = serializers.ReadOnlyField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "avatar",
            "avatar_url",
            "phone",
        ]
        read_only_fields = fields

    def get_avatar_url(self, obj):
        """Return avatar URL or None if no avatar."""
        if obj.avatar:
            request = self.context.get("request")
            if request is not None:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request."""

    email = serializers.EmailField()

    def validate_email(self, value):
        """Validate that user exists."""
        try:
            User.objects.get(email__iexact=value, is_active=True)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError(
                "No active account found with this email"
            ) from exc
        return value

    def create(self, validated_data):
        """Create password reset request and send email."""
        email = validated_data["email"]
        user = User.objects.get(email__iexact=email)

        # Deactivate any existing reset requests
        PasswordReset.objects.filter(user=user, is_active=True).update(is_active=False)

        # Create new reset request
        reset = PasswordReset.objects.create(
            user=user,
            hash_token=PasswordReset.generate_hash(),
            pin=PasswordReset.generate_pin(),
        )

        # Send email with PIN asynchronously via Celery
        send_password_reset_email.delay(
            user.email, user.first_name, reset.pin, reset.hash_token
        )
        logger.info("Password reset email task queued for %s", user.email)

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
                user__email=attrs["email"],
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
                user__email=attrs["email"],
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

        return user


class SimplePinVerifySerializer(serializers.Serializer):
    """Simplified serializer for PIN verification (only email and code)."""

    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=4)

    def validate(self, attrs):
        """Validate email and PIN combination without requiring hash_token."""
        try:
            reset = PasswordReset.objects.get(
                user__email=attrs["email"],
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


class TermsAndConditionsSerializer(serializers.ModelSerializer):
    """Serializer for terms and conditions."""

    class Meta:
        model = TermsAndConditions
        fields = ["id", "version", "content", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
