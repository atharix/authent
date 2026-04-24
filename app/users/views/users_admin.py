from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from ..models import UserSession

User = get_user_model()


class UserAdminSerializer(serializers.ModelSerializer):
    """Serializer used by admins to list/edit users."""

    full_name = serializers.ReadOnlyField()
    active_sessions_count = serializers.IntegerField(read_only=True, required=False)
    groups = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone_number",
            "birth_date",
            "gender",
            "avatar",
            "profile_type",
            "email_verified",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
            "active_sessions_count",
            "groups",
        ]
        read_only_fields = [
            "id",
            "date_joined",
            "last_login",
            "email_verified",
            "active_sessions_count",
            "groups",
        ]

    def get_groups(self, obj):
        return [{"id": g.id, "name": g.name} for g in obj.groups.all()]


class UsersAdminViewSet(viewsets.ModelViewSet):
    """Admin-only CRUD for user management."""

    serializer_class = UserAdminSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = User.objects.all().annotate(
            active_sessions_count=Count(
                "sessions", filter=Q(sessions__is_active=True)
            )
        )

        params = self.request.query_params
        search = params.get("search", "").strip()
        profile_type = params.get("profile_type")
        is_active = params.get("is_active")

        if search:
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone_number__icontains=search)
            )

        if profile_type:
            queryset = queryset.filter(profile_type=profile_type)

        if is_active is not None and is_active != "":
            queryset = queryset.filter(is_active=is_active.lower() in ("1", "true", "yes"))

        ordering = params.get("ordering", "-date_joined")
        return queryset.order_by(ordering)

    @action(detail=True, methods=["post"], url_path="revoke-sessions")
    def revoke_sessions(self, request, pk=None):
        """Revoke all active sessions of the target user."""
        user = self.get_object()
        updated = UserSession.objects.filter(user=user, is_active=True).update(
            is_active=False
        )
        return Response(
            {"revoked": updated, "user_id": user.id},
            status=status.HTTP_200_OK,
        )
