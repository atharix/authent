from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAdminUser

from .models import APIKey, Application


class ApplicationSerializer(serializers.ModelSerializer):
    api_keys_count = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
            "api_keys_count",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "api_keys_count"]

    def get_api_keys_count(self, obj):
        return obj.api_keys.count()


class APIKeyListSerializer(serializers.ModelSerializer):
    """Read-only serializer: hides the raw key, exposes a masked preview."""

    application_name = serializers.CharField(source="application.name", read_only=True)
    masked_key = serializers.SerializerMethodField()

    class Meta:
        model = APIKey
        fields = [
            "id",
            "application",
            "application_name",
            "name",
            "masked_key",
            "is_active",
            "expires_at",
            "last_used_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_masked_key(self, obj):
        if not obj.key:
            return ""
        return f"{obj.key[:6]}••••{obj.key[-4:]}"


class APIKeyCreateSerializer(serializers.ModelSerializer):
    """Write serializer: returns the full raw key exactly once upon creation."""

    key = serializers.CharField(read_only=True)

    class Meta:
        model = APIKey
        fields = ["id", "application", "name", "is_active", "expires_at", "key"]
        read_only_fields = ["id", "key"]


class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = Application.objects.all()
        search = self.request.query_params.get("search", "").strip()
        is_active = self.request.query_params.get("is_active")
        if search:
            queryset = queryset.filter(name__icontains=search)
        if is_active is not None and is_active != "":
            queryset = queryset.filter(is_active=is_active.lower() in ("1", "true", "yes"))
        return queryset.order_by("name")


class APIKeyViewSet(viewsets.ModelViewSet):
    queryset = APIKey.objects.select_related("application").all()
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action == "create":
            return APIKeyCreateSerializer
        return APIKeyListSerializer

    def get_queryset(self):
        queryset = APIKey.objects.select_related("application").all()
        params = self.request.query_params
        application = params.get("application")
        is_active = params.get("is_active")
        if application:
            queryset = queryset.filter(application_id=application)
        if is_active is not None and is_active != "":
            queryset = queryset.filter(is_active=is_active.lower() in ("1", "true", "yes"))
        return queryset.order_by("-created_at")
