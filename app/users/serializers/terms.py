from rest_framework import serializers

from ..models import TermsAndConditions, UserTermsAcceptance


class TermsAndConditionsSerializer(serializers.ModelSerializer):
    """Serializer for legal documents (terms / privacy policy)."""

    application_name = serializers.CharField(
        source="application.name", read_only=True, default=None
    )
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = TermsAndConditions
        fields = [
            "id",
            "application",
            "application_name",
            "kind",
            "kind_display",
            "version",
            "title",
            "content",
            "is_active",
            "published_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "application_name", "kind_display"]


class UserTermsAcceptanceSerializer(serializers.ModelSerializer):
    """Read-only serializer of acceptance records."""

    terms_version = serializers.CharField(source="terms.version", read_only=True)
    terms_kind = serializers.CharField(source="terms.kind", read_only=True)
    terms_kind_display = serializers.CharField(
        source="terms.get_kind_display", read_only=True
    )
    terms_application_name = serializers.CharField(
        source="terms.application.name", read_only=True, default=None
    )

    class Meta:
        model = UserTermsAcceptance
        fields = [
            "id",
            "user",
            "terms",
            "terms_version",
            "terms_kind",
            "terms_kind_display",
            "terms_application_name",
            "accepted_at",
            "ip_address",
        ]
        read_only_fields = fields
