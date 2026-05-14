from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from ..models import Country, Location


class LocationSerializer(GeoFeatureModelSerializer):
    """Serializer for Location with GeoJSON support."""

    class Meta:
        model = Location
        geo_field = "point"
        id_field = False
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class LocationListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listings."""

    class Meta:
        model = Location
        fields = ["id", "name", "is_active", "created_at"]


class CountrySerializer(serializers.ModelSerializer):
    """Serializer for Country model with auto-translation in name field."""

    class Meta:
        model = Country
        fields = [
            "id",
            "name",
            "code_iso2",
            "code_iso3",
            "numeric_code",
            "phone_code",
            "currency_code",
            "vat_options",
            "is_active",
            "sort_order",
        ]
        read_only_fields = ["id"]

    def to_representation(self, instance):
        """Override to return translated name based on request language."""
        ret = super().to_representation(instance)

        # Get language from request headers
        request = self.context.get("request")
        if request:
            language = request.META.get("HTTP_ACCEPT_LANGUAGE", "es")[:2].lower()
            ret["name"] = instance.get_localized_name(language)
        else:
            ret["name"] = instance.name

        return ret


class CountryListSerializer(serializers.ModelSerializer):
    """Simplified serializer for country list endpoints."""

    class Meta:
        model = Country
        fields = [
            "id",
            "name",
            "code_iso2",
            "phone_code",
            "is_active",
            "sort_order",
        ]

    def to_representation(self, instance):
        """Override to return translated name based on request language."""
        ret = super().to_representation(instance)

        # Get language from request headers
        request = self.context.get("request")
        if request:
            language = request.META.get("HTTP_ACCEPT_LANGUAGE", "es")[:2].lower()
            ret["name"] = instance.get_localized_name(language)
        else:
            ret["name"] = instance.name

        return ret


class CountryCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating countries (admin only)."""

    class Meta:
        model = Country
        fields = [
            "name",
            "code_iso2",
            "code_iso3",
            "numeric_code",
            "name_pt",
            "name_en",
            "name_fr",
            "name_it",
            "phone_code",
            "currency_code",
            "vat_options",
            "is_active",
            "sort_order",
        ]

    def validate_code_iso2(self, value):
        """Validate ISO2 code format."""
        if len(value) != 2:
            raise serializers.ValidationError("ISO2 code must be exactly 2 characters")
        return value.upper()

    def validate_code_iso3(self, value):
        """Validate ISO3 code format."""
        if len(value) != 3:
            raise serializers.ValidationError("ISO3 code must be exactly 3 characters")
        return value.upper()


__all__ = [
    "CountryCreateUpdateSerializer",
    "CountryListSerializer",
    "CountrySerializer",
    "LocationListSerializer",
    "LocationSerializer",
]
