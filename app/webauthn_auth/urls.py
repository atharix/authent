from django.urls import path

from .views import (
    AuthenticateOptionsView,
    AuthenticateVerifyView,
    CredentialDeleteView,
    CredentialListView,
    RegisterOptionsView,
    RegisterVerifyView,
)

app_name = "webauthn_auth"

urlpatterns = [
    path("register/options/", RegisterOptionsView.as_view(), name="register_options"),
    path("register/verify/", RegisterVerifyView.as_view(), name="register_verify"),
    path(
        "authenticate/options/",
        AuthenticateOptionsView.as_view(),
        name="authenticate_options",
    ),
    path(
        "authenticate/verify/",
        AuthenticateVerifyView.as_view(),
        name="authenticate_verify",
    ),
    path("credentials/", CredentialListView.as_view(), name="credentials"),
    path(
        "credentials/<uuid:credential_id>/",
        CredentialDeleteView.as_view(),
        name="credential_delete",
    ),
]
