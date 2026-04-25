from django.contrib.auth.models import Group, Permission
from django.db.models import Count
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response


class PermissionSerializer(serializers.ModelSerializer):
    app_label = serializers.CharField(source="content_type.app_label", read_only=True)
    model = serializers.CharField(source="content_type.model", read_only=True)

    class Meta:
        model = Permission
        fields = ["id", "codename", "name", "app_label", "model"]
        read_only_fields = fields


class GroupSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True, read_only=True)
    permission_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.all(),
        source="permissions",
        write_only=True,
        required=False,
    )
    users_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Group
        fields = ["id", "name", "permissions", "permission_ids", "users_count"]


class GroupViewSet(viewsets.ModelViewSet):
    """Admin-only CRUD for groups (roles) + helper action to list available permissions."""

    serializer_class = GroupSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = Group.objects.all().annotate(users_count=Count("beat_user"))
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset.order_by("name")

    @action(detail=False, methods=["get"], url_path="permissions")
    def list_permissions(self, request):
        """Return all available Django permissions for role assignment."""
        queryset = Permission.objects.select_related("content_type").order_by(
            "content_type__app_label", "content_type__model", "codename"
        )
        serializer = PermissionSerializer(queryset, many=True)
        return Response(serializer.data)
