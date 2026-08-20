from django.contrib.auth.models import Group
from rest_framework import serializers

from .models import Business, Collaborator, Industry


class IndustrySerializer(serializers.ModelSerializer):
    localized_name = serializers.SerializerMethodField()
    translations = serializers.SerializerMethodField()

    class Meta:
        model = Industry
        fields = [
            "id",
            "code",
            "name",
            "description",
            "icon",
            "is_active",
            "sort_order",
            "name_pt",
            "name_en",
            "name_fr",
            "name_it",
            "localized_name",
            "translations",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "localized_name", "translations"]

    def get_localized_name(self, obj):
        request = self.context.get("request")
        if request:
            language = request.META.get("HTTP_ACCEPT_LANGUAGE", "es")[:2].lower()
            return obj.get_localized_name(language)
        return obj.name

    def get_translations(self, obj):
        return obj.get_all_translations()


class BusinessSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)
    country_code_iso2 = serializers.CharField(source="country.code_iso2", read_only=True)
    country_currency_code = serializers.CharField(
        source="country.currency_code", read_only=True
    )
    country_vat_options = serializers.JSONField(
        source="country.vat_options", read_only=True
    )
    collaborators_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Business
        fields = [
            "id",
            "name",
            "legal_name",
            "tax_id",
            "fiscal_name",
            "registration_number",
            "country",
            "country_name",
            "country_code_iso2",
            "country_currency_code",
            "country_vat_options",
            "currency",
            "vat_regime",
            "industry",
            "website",
            "phone",
            "email",
            "address",
            "logo",
            "is_active",
            "created_at",
            "updated_at",
            "collaborators_count",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "country_name",
            "country_code_iso2",
            "country_currency_code",
            "country_vat_options",
            "collaborators_count",
        ]

    def validate(self, attrs):
        """If currency is empty but country is set, fall back to country.currency_code."""
        country = attrs.get("country") or getattr(self.instance, "country", None)
        if country and not attrs.get("currency"):
            attrs["currency"] = country.currency_code or attrs.get("currency", "")
        if attrs.get("vat_regime") and country and country.vat_options:
            valid_codes = {opt.get("code") for opt in country.vat_options}
            if attrs["vat_regime"] not in valid_codes:
                raise serializers.ValidationError(
                    {"vat_regime": "Not a valid option for the selected country."}
                )
        return attrs


class CollaboratorSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)
    business_name = serializers.CharField(source="business.name", read_only=True)
    # Escribible: los productos identifican el rol por nombre, no por el PK
    # entero del Group (que es un detalle interno de esta base). Un nombre
    # inexistente ahora es error de validación — antes se ignoraba en
    # silencio y el PATCH devolvía 200 sin cambiar nada.
    role_name = serializers.SlugRelatedField(
        source="role",
        slug_field="name",
        queryset=Group.objects.all(),
        required=False,
    )

    class Meta:
        model = Collaborator
        fields = [
            "id",
            "user",
            "user_email",
            "user_full_name",
            "business",
            "business_name",
            "role",
            "role_name",
            "title",
            "is_active",
            "joined_at",
        ]
        read_only_fields = [
            "id",
            "joined_at",
            "user_email",
            "user_full_name",
            "business_name",
        ]
