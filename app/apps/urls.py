from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api import APIKeyViewSet, ApplicationViewSet

app_name = "apps"

router = DefaultRouter()
router.register(r"applications", ApplicationViewSet, basename="application")
router.register(r"api-keys", APIKeyViewSet, basename="api-key")

urlpatterns = [
    path("", include(router.urls)),
]
