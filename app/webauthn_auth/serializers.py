from rest_framework import serializers

from .models import WebAuthnCredential


class WebAuthnCredentialSerializer(serializers.ModelSerializer):
    """Safe public summary of an enrolled passkey (no public_key / raw id)."""

    class Meta:
        model = WebAuthnCredential
        fields = [
            "id",
            "friendly_name",
            "transports",
            "backup_eligible",
            "backup_state",
            "created_at",
            "last_used_at",
        ]


class RegisterVerifyInputSerializer(serializers.Serializer):
    credential = serializers.JSONField()
    friendly_name = serializers.CharField(
        required=False, allow_blank=True, max_length=120
    )


class AuthenticateVerifyInputSerializer(serializers.Serializer):
    state = serializers.CharField(max_length=64)
    credential = serializers.JSONField()
