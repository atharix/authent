from django.db.models import Count, Q
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from .models import Business, Collaborator
from .serializers import BusinessSerializer, CollaboratorSerializer


class BusinessViewSet(viewsets.ModelViewSet):
    """CRUD of businesses. Admin required for write; authenticated for read."""

    serializer_class = BusinessSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        queryset = (
            Business.objects.filter(is_deleted=False)
            .select_related("country")
            .annotate(
                collaborators_count=Count(
                    "collaborators", filter=Q(collaborators__is_active=True)
                )
            )
        )

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
            queryset = queryset.filter(is_active=is_active.lower() in ("1", "true", "yes"))

        return queryset.order_by("name")

    def perform_destroy(self, instance):
        """Soft delete via BaseModel."""
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted", "deleted_at"] if hasattr(instance, "deleted_at") else ["is_deleted"])


class CollaboratorViewSet(viewsets.ModelViewSet):
    """CRUD of collaborators. Admin only."""

    serializer_class = CollaboratorSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = (
            Collaborator.objects.filter(is_deleted=False)
            .select_related("user", "business", "role")
        )

        params = self.request.query_params
        business = params.get("business")
        user = params.get("user")
        role = params.get("role")
        is_active = params.get("is_active")

        if business:
            queryset = queryset.filter(business_id=business)
        if user:
            queryset = queryset.filter(user_id=user)
        if role:
            queryset = queryset.filter(role_id=role)
        if is_active is not None and is_active != "":
            queryset = queryset.filter(is_active=is_active.lower() in ("1", "true", "yes"))

        return queryset.order_by("-joined_at")

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted", "deleted_at"] if hasattr(instance, "deleted_at") else ["is_deleted"])
