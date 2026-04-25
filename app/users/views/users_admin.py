from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Count, Q
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import UserSession, UserTermsAcceptance
from ..permissions import IsAdminOrDeveloper
from ..serializers.session import UserSessionSerializer
from ..serializers.terms import UserTermsAcceptanceSerializer

User = get_user_model()


class UserAdminSerializer(serializers.ModelSerializer):
    """Serializer used by admins to list/edit/create users."""

    full_name = serializers.ReadOnlyField()
    active_sessions_count = serializers.IntegerField(read_only=True, required=False)
    groups = serializers.SerializerMethodField()
    group_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Group.objects.all(),
        source="groups",
        write_only=True,
        required=False,
    )
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "password",
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
            "group_ids",
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

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        groups = validated_data.pop("groups", None)
        if not password:
            raise serializers.ValidationError(
                {"password": "Password is required when creating a user."}
            )
        user = User.objects.create_user(password=password, **validated_data)
        if groups is not None:
            user.groups.set(groups)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        groups = validated_data.pop("groups", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if groups is not None:
            instance.groups.set(groups)
        return instance


class UsersAdminViewSet(viewsets.ModelViewSet):
    """Admin-only CRUD for user management."""

    serializer_class = UserAdminSerializer
    permission_classes = [IsAdminOrDeveloper]

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

        ordering = params.get("ordering")
        if ordering:
            return queryset.order_by(ordering)
        return queryset.order_by("first_name", "last_name")

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

    @action(detail=True, methods=["get"], url_path="sessions")
    def list_sessions(self, request, pk=None):
        """List all active sessions of the target user."""
        user = self.get_object()
        sessions = UserSession.objects.filter(user=user).order_by("-last_activity")
        serializer = UserSessionSerializer(sessions, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"sessions/(?P<session_id>[^/.]+)",
    )
    def revoke_session(self, request, pk=None, session_id=None):
        """Revoke a single session of the target user."""
        user = self.get_object()
        try:
            session = UserSession.objects.get(pk=session_id, user=user)
        except UserSession.DoesNotExist:
            return Response(
                {"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND
            )
        session.is_active = False
        session.save(update_fields=["is_active"])
        return Response(
            {"revoked": True, "session_id": session.id},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="terms-acceptances")
    def list_terms_acceptances(self, request, pk=None):
        """List all legal documents accepted by the target user."""
        user = self.get_object()
        acceptances = (
            UserTermsAcceptance.objects.filter(user=user)
            .select_related("terms", "terms__application")
            .order_by("-accepted_at")
        )
        serializer = UserTermsAcceptanceSerializer(
            acceptances, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
