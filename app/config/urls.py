from core.health import health_check, live_check, ready_check
from core.views import home_view
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("", home_view, name="home"),
    path("admin/", admin.site.urls),
    # Health checks
    path("health/", health_check, name="health"),
    path("ready/", ready_check, name="ready"),
    path("live/", live_check, name="live"),
    # API endpoints
    path("api/health/", health_check, name="api-health"),
    path("api/auth/", include("users.urls")),
    path("api/auth/", include("apps.urls")),
    path("api/core/", include("core.urls")),
    path("api/core/", include("business.urls")),
    # API Schema & Docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

# Error handlers
handler500 = "core.middleware_errors.custom_500_view"
handler404 = "core.middleware_errors.custom_404_view"
handler400 = "core.middleware_errors.custom_400_view"
handler403 = "core.middleware_errors.custom_403_view"

if settings.DEBUG:
    # Serve media files in development
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
