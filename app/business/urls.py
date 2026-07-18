from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BusinessViewSet,
    CollaboratorViewSet,
    IndustryViewSet,
    InternalBusinessAppAccessView,
    InternalCollaboratorView,
)

app_name = "business"

router = DefaultRouter()
router.register(r"business", BusinessViewSet, basename="business")
router.register(r"collaborators", CollaboratorViewSet, basename="collaborator")
router.register(r"industries", IndustryViewSet, basename="industry")

urlpatterns = [
    path(
        "internal/collaborators/",
        InternalCollaboratorView.as_view(),
        name="internal_collaborator",
    ),
    path(
        "internal/business-app-access/",
        InternalBusinessAppAccessView.as_view(),
        name="internal_business_app_access",
    ),
    path("", include(router.urls)),
]
