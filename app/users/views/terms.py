from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..models import TermsAndConditions, UserTermsAcceptance
from ..serializers import TermsAndConditionsSerializer


class TermsAndConditionsViewSet(viewsets.ModelViewSet):
    """
    CRUD over legal documents (terms / privacy policies) tied to applications.

    - List/retrieve: public (AllowAny). Filter via ?application=<id>&kind=<terms|privacy>&is_active=true.
    - Create/Update/Delete: admin only.
    """

    serializer_class = TermsAndConditionsSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        queryset = TermsAndConditions.objects.select_related("application").all()
        params = self.request.query_params

        application = params.get("application")
        kind = params.get("kind")
        is_active = params.get("is_active")
        search = params.get("search", "").strip()

        if application:
            queryset = queryset.filter(application_id=application)
        if kind:
            queryset = queryset.filter(kind=kind)
        if is_active is not None and is_active != "":
            queryset = queryset.filter(
                is_active=is_active.lower() in ("1", "true", "yes")
            )
        if search:
            queryset = queryset.filter(version__icontains=search) | queryset.filter(
                title__icontains=search
            )

        ordering = params.get("ordering")
        if ordering:
            return queryset.order_by(ordering)
        return queryset.order_by("-created_at")


@extend_schema(
    description="Check if user needs to accept new terms or privacy policy",
    tags=["Authentication"],
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def check_terms_acceptance(request):
    """Check if the authenticated user needs to accept the latest active legal documents.

    Optional query params: application=<id>, kind=<terms|privacy>.
    Returns one entry per kind (terms + privacy) when no kind filter is set.
    """
    application = request.query_params.get("application")
    kind = request.query_params.get("kind")

    queryset = TermsAndConditions.objects.filter(is_active=True)
    if application:
        queryset = queryset.filter(application_id=application)
    if kind:
        queryset = queryset.filter(kind=kind)

    if not queryset.exists():
        return Response({"needs_acceptance": False, "documents": []})

    accepted_ids = set(
        request.user.terms_acceptances.filter(terms__in=queryset).values_list(
            "terms_id", flat=True
        )
    )

    documents = []
    needs_acceptance = False
    for doc in queryset.order_by("-created_at"):
        accepted = doc.id in accepted_ids
        if not accepted:
            needs_acceptance = True
        documents.append(
            {
                "id": doc.id,
                "kind": doc.kind,
                "version": doc.version,
                "title": doc.title,
                "application": doc.application_id,
                "needs_acceptance": not accepted,
                "content": None if accepted else doc.content,
            }
        )

    return Response({"needs_acceptance": needs_acceptance, "documents": documents})


@extend_schema(
    description="Accept a terms or privacy document by ID",
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def accept_terms(request):
    """Record acceptance of a specific legal document.

    Body: { "terms_id": <id> }  OR  { "version": "1.0", "kind": "terms", "application": <id|null> }
    """
    terms_id = request.data.get("terms_id")
    version = request.data.get("version")
    kind = request.data.get("kind", TermsAndConditions.KIND_TERMS)
    application = request.data.get("application")

    if terms_id:
        try:
            terms = TermsAndConditions.objects.get(pk=terms_id, is_active=True)
        except TermsAndConditions.DoesNotExist:
            return Response(
                {"error": "Invalid or inactive terms"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    elif version:
        queryset = TermsAndConditions.objects.filter(
            version=version, kind=kind, is_active=True
        )
        if application is not None:
            queryset = queryset.filter(application_id=application)
        terms = queryset.first()
        if terms is None:
            return Response(
                {"error": "Invalid or inactive terms version"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        return Response(
            {"error": "Provide terms_id or version (+kind, +application)"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if request.user.terms_acceptances.filter(terms=terms).exists():
        return Response({"message": "Terms already accepted"})

    UserTermsAcceptance.objects.create(
        user=request.user,
        terms=terms,
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
    )

    return Response({"message": "Terms accepted successfully"})
