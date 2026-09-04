"""Serializers del segundo factor: código por correo y aprobación desde la app."""

from rest_framework import serializers

from ..models.mfa import EmailOtp, LoginApproval, PushApprover, TrustedDevice


class MfaVerifySerializer(serializers.Serializer):
    """Paso 2 del login: canjear el código por los tokens."""

    mfa_token = serializers.CharField()
    code = serializers.CharField(
        min_length=EmailOtp.CODE_LENGTH, max_length=EmailOtp.CODE_LENGTH
    )
    remember_device = serializers.BooleanField(required=False, default=False)
    device_name = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )

    def validate_code(self, value):
        code = (value or "").strip()
        if not code.isdigit():
            raise serializers.ValidationError("El código solo admite dígitos.")
        return code


class MfaResendSerializer(serializers.Serializer):
    """Reenvío del código dentro del mismo desafío."""

    mfa_token = serializers.CharField()


class TrustedDeviceSerializer(serializers.ModelSerializer):
    """Lectura para la pantalla de Seguridad: qué equipos se saltan el código."""

    is_current = serializers.SerializerMethodField()

    class Meta:
        model = TrustedDevice
        fields = [
            "id",
            "device_name",
            "application_code",
            "user_agent",
            "ip_address",
            "created_at",
            "last_used_at",
            "expires_at",
            "is_current",
        ]
        read_only_fields = fields

    def get_is_current(self, obj):
        raw = self.context.get("current_device_token")
        if not raw:
            return False
        from ..models.mfa import hash_opaque_token

        return obj.token_hash == hash_opaque_token(raw)


class MfaApprovalStatusSerializer(serializers.Serializer):
    """Sondeo del navegador mientras espera al teléfono."""

    mfa_token = serializers.CharField()
    remember_device = serializers.BooleanField(required=False, default=False)
    device_name = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )


class MfaApprovalFallbackSerializer(serializers.Serializer):
    """Abandono del desafío por app para recibir el código en el correo."""

    mfa_token = serializers.CharField()


class LoginApprovalSerializer(serializers.ModelSerializer):
    """Lo que ve la app: quién pide entrar y entre qué números elegir."""

    expires_in = serializers.IntegerField(read_only=True)

    class Meta:
        model = LoginApproval
        fields = [
            "id",
            "status",
            "numbers",
            "device_name",
            "location",
            "ip_address",
            "created_at",
            "expires_at",
            "expires_in",
        ]
        read_only_fields = fields


class LoginApprovalApproveSerializer(serializers.Serializer):
    """Confirmación con el número que el navegador enseñaba."""

    number = serializers.IntegerField(min_value=10, max_value=99)


class PushApproverSerializer(serializers.ModelSerializer):
    """Teléfonos que pueden autorizar, para la pantalla de Seguridad."""

    class Meta:
        model = PushApprover
        fields = [
            "id",
            "device_label",
            "platform",
            "application_code",
            "created_at",
            "last_used_at",
        ]
        read_only_fields = fields


class PushApproverCreateSerializer(serializers.Serializer):
    """Alta del aprobador. ``delivery_ref`` lo resuelve el producto, no Authent."""

    delivery_ref = serializers.CharField(max_length=255)
    device_label = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
    platform = serializers.CharField(required=False, allow_blank=True, max_length=20)
