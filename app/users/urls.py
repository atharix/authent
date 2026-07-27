from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    DeleteAccountView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    TermsAndConditionsViewSet,
    TokenVerifyView,
    UserLoginView,
    UserLogoutView,
    UserProfileView,
    UserRegistrationView,
    UserUpdateView,
    accept_terms,
    check_terms_acceptance,
)
from .views.groups import GroupViewSet
from .views.session import UserSessionViewSet
from .views.users_admin import UsersAdminViewSet

app_name = "auth"

router = DefaultRouter()
router.register(r"sessions", UserSessionViewSet, basename="session")
router.register(r"users", UsersAdminViewSet, basename="user-admin")
router.register(r"groups", GroupViewSet, basename="group")
router.register(r"terms", TermsAndConditionsViewSet, basename="terms")

urlpatterns = [
    # --- Authentication ---
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("profile/", UserProfileView.as_view(), name="profile"),
    path("update-profile/", UserUpdateView.as_view(), name="update_profile"),
    # Baja de cuenta (Art. 17). La llaman los productos tras suprimir lo suyo.
    path("delete-account/", DeleteAccountView.as_view(), name="delete_account"),
    path("verify-token/", TokenVerifyView.as_view(), name="verify_token"),
    # --- Registration ---
    path("register/", UserRegistrationView.as_view(), name="register"),
    # --- Password management ---
    path(
        "password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="password_reset_request",
    ),
    path(
        "password-reset/verify/",
        PasswordResetVerifyView.as_view(),
        name="password_reset_verify",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-change/",
        PasswordChangeView.as_view(),
        name="password_change",
    ),
    # --- Terms & conditions custom actions (must come before router) ---
    path("terms/check/", check_terms_acceptance, name="terms_check"),
    path("terms/accept/", accept_terms, name="terms_accept"),
    # --- Session management ---
    path("", include(router.urls)),
]
