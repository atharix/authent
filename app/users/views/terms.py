from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..models import TermsAndConditions, UserTermsAcceptance
from ..serializers import TermsAndConditionsSerializer


@extend_schema_view(
    get=extend_schema(
        description="Get current active terms and conditions", tags=["Authentication"]
    )
)
class TermsAndConditionsView(generics.ListAPIView):
    """Get current active terms and conditions."""

    serializer_class = TermsAndConditionsSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return TermsAndConditions.objects.filter(is_active=True)


@extend_schema(
    description="Check if user needs to accept new terms", tags=["Authentication"]
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def check_terms_acceptance(request):
    """Check if the authenticated user needs to accept the latest active terms."""
    latest_terms = (
        TermsAndConditions.objects.filter(is_active=True)
        .order_by("-created_at")
        .first()
    )

    if latest_terms is None:
        return Response({"needs_acceptance": False, "message": "No active terms found"})

    has_accepted = request.user.terms_acceptances.filter(terms=latest_terms).exists()

    return Response(
        {
            "needs_acceptance": not has_accepted,
            "latest_version": latest_terms.version,
            "terms_content": latest_terms.content if not has_accepted else None,
        }
    )


@extend_schema(
    description="Accept current terms and conditions", tags=["Authentication"]
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def accept_terms(request):
    """Record the authenticated user's acceptance of a specific terms version."""
    version = request.data.get("version")

    if not version:
        return Response(
            {"error": "Version is required"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        terms = TermsAndConditions.objects.get(version=version, is_active=True)
    except TermsAndConditions.DoesNotExist:
        return Response(
            {"error": "Invalid or inactive terms version"},
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
