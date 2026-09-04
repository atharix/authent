from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    DeleteAccountView,
    MfaResendView,
    MfaVerifyView,
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
from .views.mfa import (
    LoginApprovalViewSet,
    MfaApprovalFallbackView,
    MfaApprovalStatusView,
    PushApproverViewSet,
    TrustedDeviceViewSet,
)
from .views.session import UserSessionViewSet
from .views.users_admin import UsersAdminViewSet

app_name = "auth"

router = DefaultRouter()
router.register(r"sessions", UserSessionViewSet, basename="session")
router.register(
    r"trusted-devices", TrustedDeviceViewSet, basename="trusted-device"
)
router.register(
    r"mfa/approvals", LoginApprovalViewSet, basename="login-approval"
)
router.register(
    r"mfa/approvers", PushApproverViewSet, basename="push-approver"
)
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
    # --- Segundo factor por correo (paso 2 del login) ---
    path("mfa/verify/", MfaVerifyView.as_view(), name="mfa_verify"),
    path("mfa/resend/", MfaResendView.as_view(), name="mfa_resend"),
    # --- Aprobación desde la app (paso 2 cuando el factor es el teléfono) ---
    path(
        "mfa/approval/status/",
        MfaApprovalStatusView.as_view(),
        name="mfa_approval_status",
    ),
    # Salida cuando el teléfono ya no está: el código vuelve al correo.
    path(
        "mfa/approval/fallback/",
        MfaApprovalFallbackView.as_view(),
        name="mfa_approval_fallback",
    ),
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
