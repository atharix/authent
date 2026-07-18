import logging

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count, Q

logger = logging.getLogger(__name__)
from rest_framework import status, viewsets
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth.models import Group

from .models import Business, Collaborator, Industry
from .permissions import (
    CanManageCollaborators,
    IsBusinessCollaboratorOrAdminWrite,
    is_business_collaborator,
)
from .serializers import BusinessSerializer, CollaboratorSerializer, IndustrySerializer

OWNER_GROUP_NAME = "owner"


class IsStaffOrReadOnly(BasePermission):
    """Allow read access to any authenticated user; write access restricted to staff.
    Service-to-service requests from Atlas are also allowed to write."""

    def has_permission(self, request, view):
        application = getattr(request, "application", None)
        if application and (application.code == "atlas" or application.name == "Atlas"):
            return True
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff


class IndustryViewSet(viewsets.ModelViewSet):
    """CRUD catalog of industries. Read access for all authenticated users; write for staff only."""

    serializer_class = IndustrySerializer
    permission_classes = [IsStaffOrReadOnly]

    def get_queryset(self):
        queryset = Industry.objects.filter(is_deleted=False)
        is_active = self.request.query_params.get("is_active")
        if is_active is not None and is_active != "":
            queryset = queryset.filter(
                is_active=is_active.lower() in ("1", "true", "yes")
            )
        return queryset.order_by("sort_order", "name")

    def perform_destroy(self, instance):
        instance.is_deleted = True
        update_fields = ["is_deleted"]
        if hasattr(instance, "deleted_at"):
            from django.utils import timezone

            instance.deleted_at = timezone.now()
            update_fields.append("deleted_at")
        instance.save(update_fields=update_fields)


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
        collaborator = Collaborator.objects.create(
            user=self.request.user,
            business=business,
            role=owner_group,
            is_active=True,
        )
        logger.info(
            "Collaborator created: user=%s business=%s role=%s",
            self.request.user.email,
            business.id,
            owner_group.name,
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

    @action(detail=True, methods=["get"], url_path="app-access")
    def app_access(self, request, pk=None):
        """Estado de licencia de esta empresa para el producto que llama (X-API-Key).

        Endpoint dedicado que consumen los productos (Metis/Atlas/Delta) para pintar su
        pantalla de Licenciamiento sin ser dueños del dato.
        """
        business = self.get_object()
        application = getattr(request, "application", None)
        if application is None:
            return Response(
                {"detail": "No hay contexto de Application (falta X-API-Key)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .access import app_access_state

        return Response(app_access_state(business, application))


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


class InternalCollaboratorView(APIView):
    """Service-to-service endpoint para crear/actualizar collaborators.

    Autentica únicamente vía X-API-Key (validada por APIKeyMiddleware) de la
    aplicación "Atlas". No requiere JWT del usuario, porque al aceptar una
    invitación el invitado aún no es admin/owner del business y no puede
    crear su propio Collaborator vía el endpoint normal.

    Payload:
        {
            "user_email": "user@example.com",
            "business_id": "<uuid>",
            "role_name": "admin"   # opcional; nombre de Group existente
        }

    Idempotente: si el collaborator existe se reactiva y se actualiza el rol.
    """

    permission_classes = []
    authentication_classes = []

    def post(self, request):
        application = getattr(request, "application", None)
        if not (
            application
            and (
                application.code in ("atlas", "metis")
                or application.name in ("Atlas", "Metis")
            )
        ):
            return Response(
                {"error": "Forbidden — solo un servicio de producto (Atlas/Metis) puede llamar este endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user_email = (request.data.get("user_email") or "").strip()
        business_id = request.data.get("business_id") or ""
        role_name = (request.data.get("role_name") or "").strip()

        if not user_email or not business_id:
            return Response(
                {"error": "user_email and business_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.contrib.auth import get_user_model

        UserModel = get_user_model()

        try:
            user = UserModel.objects.get(email__iexact=user_email)
        except UserModel.DoesNotExist:
            return Response(
                {"error": f"User not found in Authent: {user_email}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            business = Business.objects.get(id=business_id, is_deleted=False)
        except Business.DoesNotExist:
            return Response(
                {"error": f"Business not found: {business_id}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        role = None
        if role_name:
            try:
                role = Group.objects.get(name=role_name)
            except Group.DoesNotExist:
                logger.warning(
                    "Group '%s' not found, creating collaborator without role",
                    role_name,
                )

        with transaction.atomic():
            collab, created = Collaborator.objects.get_or_create(
                user=user,
                business=business,
                defaults={"role": role, "is_active": True},
            )
            if not created:
                update_fields = []
                if collab.is_deleted:
                    collab.is_deleted = False
                    update_fields.append("is_deleted")
                if not collab.is_active:
                    collab.is_active = True
                    update_fields.append("is_active")
                if role and collab.role_id != role.id:
                    collab.role = role
                    update_fields.append("role")
                if update_fields:
                    collab.save(update_fields=update_fields)

        return Response(
            CollaboratorSerializer(collab).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class InternalBusinessAppAccessView(APIView):
    """Service-to-service: upsert del acceso (licencia) de una empresa al producto que llama.

    Autentica únicamente vía X-API-Key (validada por APIKeyMiddleware). El producto que
    llama (`request.application`) solo puede gestionar **su propio** acceso — no el de
    otros productos. Idempotente.

    Es la vía del **backfill**: cada producto (Metis/Atlas/Delta) empuja hacia Authent —la
    fuente de verdad— la licencia que hoy tiene localmente, para poder activar el gate sin
    dejar a nadie fuera.

    Payload:
        {
            "business_id": "<uuid>",
            "license_type": "none|trial|standard|enterprise",
            "is_enabled": true,
            "expires_at": "2026-12-31" | null,
            "max_users": 10,
            "access_notice": ""      # opcional
        }
    """

    permission_classes = []
    authentication_classes = []

    def post(self, request):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.utils.dateparse import parse_date

        from .access import app_access_state
        from .models import BusinessAppAccess, LicenseType

        application = getattr(request, "application", None)
        if application is None:
            return Response(
                {"error": "Falta X-API-Key / contexto de Application."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        business_id = request.data.get("business_id") or ""
        if not business_id:
            return Response(
                {"error": "business_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            business = Business.objects.get(id=business_id, is_deleted=False)
        except (Business.DoesNotExist, DjangoValidationError, ValueError):
            return Response(
                {"error": f"Business not found: {business_id}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # license_type — validar contra el catálogo.
        license_type = (request.data.get("license_type") or LicenseType.NONE).strip()
        valid_types = {c for c, _ in LicenseType.choices}
        if license_type not in valid_types:
            return Response(
                {"error": f"license_type inválido: {license_type}. Opciones: {sorted(valid_types)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # expires_at — fecha ISO o vacío.
        expires_raw = request.data.get("expires_at")
        expires_at = None
        if expires_raw:
            expires_at = parse_date(str(expires_raw))
            if expires_at is None:
                return Response(
                    {"error": f"expires_at inválido (usa YYYY-MM-DD): {expires_raw}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # max_users — entero ≥ 0.
        try:
            max_users = int(request.data.get("max_users") or 0)
        except (TypeError, ValueError):
            return Response(
                {"error": "max_users debe ser un entero."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        max_users = max(max_users, 0)

        is_enabled = bool(request.data.get("is_enabled", True))
        access_notice = str(request.data.get("access_notice") or "")

        defaults = {
            "license_type": license_type,
            "is_enabled": is_enabled,
            "expires_at": expires_at,
            "max_users": max_users,
            "access_notice": access_notice,
        }
        obj, created = BusinessAppAccess.objects.update_or_create(
            business=business,
            application=application,
            is_deleted=False,
            defaults=defaults,
        )
        return Response(
            app_access_state(business, application),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
