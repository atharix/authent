from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BusinessViewSet, CollaboratorViewSet, IndustryViewSet

app_name = "business"

router = DefaultRouter()
router.register(r"business", BusinessViewSet, basename="business")
router.register(r"collaborators", CollaboratorViewSet, basename="collaborator")
router.register(r"industries", IndustryViewSet, basename="industry")

urlpatterns = [
    path("", include(router.urls)),
]
