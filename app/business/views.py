from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .models import Business, Collaborator
from .permissions import (
    CanManageCollaborators,
    IsBusinessCollaboratorOrAdminWrite,
    is_business_collaborator,
)
from .serializers import BusinessSerializer, CollaboratorSerializer

OWNER_GROUP_NAME = "owner"


class BusinessViewSet(viewsets.ModelViewSet):
    """
    Self-service CRUD of businesses.

    - Any authenticated user can create a business; they become its owner-collaborator.
    - List/retrieve return only businesses where the requester is an active collaborator.
    - Update/delete restricted to owner/admin of that business.
    - Staff users see and can mutate everything.
    """

    serializer_class = BusinessSerializer
    permission_classes = [IsBusinessCollaboratorOrAdminWrite]

    def _base_queryset(self):
        return (
            Business.objects.filter(is_deleted=False)
            .select_related("country")
            .annotate(
                collaborators_count=Count(
                    "collaborators", filter=Q(collaborators__is_active=True)
                )
            )
        )

    def get_queryset(self):
        queryset = self._base_queryset()
        user = self.request.user

        if not user.is_staff:
            collaborating_ids = Collaborator.objects.filter(
                user=user, is_active=True, is_deleted=False
            ).values_list("business_id", flat=True)
            queryset = queryset.filter(id__in=collaborating_ids)

        params = self.request.query_params
        search = params.get("search", "").strip()
        country = params.get("country")
        is_active = params.get("is_active")

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(legal_name__icontains=search)
                | Q(tax_id__icontains=search)
            )
        if country:
            queryset = queryset.filter(country_id=country)
        if is_active is not None and is_active != "":
            queryset = queryset.filter(
                is_active=is_active.lower() in ("1", "true", "yes")
            )

        ordering = params.get("ordering")
        if ordering:
            return queryset.order_by(ordering)
        return queryset.order_by("name")

    @transaction.atomic
    def perform_create(self, serializer):
        """Create the business and bind the requester as owner-collaborator."""
        business = serializer.save()
        owner_group, _ = Group.objects.get_or_create(name=OWNER_GROUP_NAME)
        Collaborator.objects.create(
            user=self.request.user,
            business=business,
            role=owner_group,
            is_active=True,
        )

    def perform_destroy(self, instance):
        """Soft delete via BaseModel."""
        instance.is_deleted = True
        update_fields = ["is_deleted"]
        if hasattr(instance, "deleted_at"):
            from django.utils import timezone

            instance.deleted_at = timezone.now()
            update_fields.append("deleted_at")
        instance.save(update_fields=update_fields)

    @action(detail=True, methods=["get"], url_path="membership")
    def membership(self, request, pk=None):
        """Return the requester's collaborator record for this business."""
        business = self.get_object()
        try:
            collab = Collaborator.objects.select_related("role").get(
                user=request.user,
                business=business,
                is_active=True,
                is_deleted=False,
            )
        except Collaborator.DoesNotExist:
            return Response(
                {"detail": "You are not a collaborator of this business."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(CollaboratorSerializer(collab).data)


class CollaboratorViewSet(viewsets.ModelViewSet):
    """
    CRUD of collaborators within businesses the requester can manage.
    Mutations require the requester to be owner/admin of the target business
    (or staff). A user is allowed to remove themselves.
    """

    serializer_class = CollaboratorSerializer
    permission_classes = [CanManageCollaborators]

    def get_queryset(self):
        user = self.request.user
        queryset = Collaborator.objects.filter(is_deleted=False).select_related(
            "user", "business", "role"
        )

        if not user.is_staff:
            visible_business_ids = Collaborator.objects.filter(
                user=user, is_active=True, is_deleted=False
            ).values_list("business_id", flat=True)
            queryset = queryset.filter(business_id__in=visible_business_ids)

        params = self.request.query_params
        business = params.get("business")
        user_param = params.get("user")
        role = params.get("role")
        is_active = params.get("is_active")

        if business:
            queryset = queryset.filter(business_id=business)
        if user_param:
            queryset = queryset.filter(user_id=user_param)
        if role:
            queryset = queryset.filter(role_id=role)
        if is_active is not None and is_active != "":
            queryset = queryset.filter(
                is_active=is_active.lower() in ("1", "true", "yes")
            )

        return queryset.order_by("-joined_at")

    def perform_create(self, serializer):
        target_business = serializer.validated_data.get("business")
        target_user = serializer.validated_data.get("user")
        if Collaborator.objects.filter(
            user=target_user, business=target_business, is_deleted=False
        ).exists():
            raise ValidationError(
                {"detail": "User is already a collaborator of this business."}
            )
        serializer.save()

    def perform_update(self, serializer):
        instance = serializer.instance
        if (
            instance.role
            and instance.role.name == OWNER_GROUP_NAME
            and serializer.validated_data.get("role")
            and serializer.validated_data["role"].name != OWNER_GROUP_NAME
        ):
            raise PermissionDenied("Cannot change the owner role of a business.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.role and instance.role.name == OWNER_GROUP_NAME:
            raise PermissionDenied("Cannot remove the owner of a business.")
        instance.is_deleted = True
        update_fields = ["is_deleted"]
        if hasattr(instance, "deleted_at"):
            from django.utils import timezone

            instance.deleted_at = timezone.now()
            update_fields.append("deleted_at")
        instance.save(update_fields=update_fields)

    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        """Return the requester's own collaborator records (across all businesses)."""
        queryset = Collaborator.objects.filter(
            user=request.user, is_active=True, is_deleted=False
        ).select_related("business", "role")
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
