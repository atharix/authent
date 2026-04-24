from rest_framework import serializers

from .models import Business, Collaborator


class BusinessSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)
    collaborators_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Business
        fields = [
            "id",
            "name",
            "legal_name",
            "tax_id",
            "country",
            "country_name",
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
            "collaborators_count",
        ]


class CollaboratorSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)
    business_name = serializers.CharField(source="business.name", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)

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
            "role_name",
        ]
