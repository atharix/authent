from rest_framework import serializers

from ..models import TermsAndConditions, UserTermsAcceptance


class TermsAndConditionsSerializer(serializers.ModelSerializer):
    """Serializer for active/inactive terms documents."""

    class Meta:
        model = TermsAndConditions
        fields = ["id", "version", "content", "is_active", "published_at", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserTermsAcceptanceSerializer(serializers.ModelSerializer):
    """Read-only serializer of acceptance records."""

    class Meta:
        model = UserTermsAcceptance
        fields = ["id", "user", "terms", "accepted_at", "ip_address"]
        read_only_fields = fields
