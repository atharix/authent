import jwt
from django.conf import settings
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from ..models.mfa import TrustedDevice
from ..serializers import CustomTokenObtainPairSerializer, UserProfileSerializer
from ..utils.mfa import (
    application_code_of,
    challenge_payload,
    mfa_enforced,
    push_challenge_payload,
    resolve_push_approver,
    start_email_otp,
    start_push_approval,
)


@extend_schema_view(
    post=extend_schema(
        description="Login with email and password", tags=["Authentication"]
    )
)
class UserLoginView(TokenObtainPairView):
    """User login endpoint with JWT tokens."""

    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        """Login por contraseña.

        Con MFA activo en el producto que llama, esto NO devuelve tokens: valida
        la contraseña, abre el desafío y lo devuelve. Los tokens se acuñan en
        ``/mfa/verify/`` (código) o en ``/mfa/approval/status/`` (app). Sin MFA
        activo, el camino es el de siempre, byte a byte, para no tocar a los
        productos que aún no lo implementan.
        """
        if mfa_enforced(request):
            return self._login_with_mfa(request)

        return self._login_and_issue_tokens(request, *args, **kwargs)

    # ── Camino con segundo factor ───────────────────────────────────────────
    def _login_with_mfa(self, request):
        from django.contrib.auth import authenticate

        from users.utils.session import create_session

        email = (request.data.get("email") or "").strip()
        password = request.data.get("password") or ""
        user = authenticate(request=request, email=email, password=password)

        if user is None or not user.is_active:
            # Mismo cuerpo que devuelve SimpleJWT: para el cliente, una
            # contraseña incorrecta se sigue viendo exactamente igual.
            return Response(
                {
                    "detail": "No active account found with the given credentials",
                    "code": "no_active_account",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        denied = self._app_access_denied(request, user)
        if denied is not None:
            # Se rechaza ANTES de mandar el correo: quien no tiene acceso al
            # producto no debe recibir un código que no le va a servir.
            return denied

        if user.is_review_account:
            # Cuenta de revisión de tienda: entra con contraseña. Se deja rastro
            # en el log porque es la única vía por la que alguien entra a Atlas
            # sin segundo factor.
            import logging

            logging.getLogger(__name__).warning(
                "Login sin segundo factor por cuenta de revisión: %s (hasta %s, motivo: %s)",
                user.email,
                user.review_account_until,
                user.review_account_reason or "sin motivo",
            )
            return self._issue_session(request, user)

        device = TrustedDevice.resolve(
            request.data.get("device_token"), user, application_code_of(request)
        )
        if device is not None:
            device.touch(
                ip=self._client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            return self._issue_session(request, user)

        approver = resolve_push_approver(user, request)
        if approver is not None:
            approval = start_push_approval(user, approver, request)
            return Response(
                push_challenge_payload(approval, approver),
                status=status.HTTP_200_OK,
            )

        otp, outcome = start_email_otp(user, request)

        if outcome == "rate_limited":
            return Response(
                {
                    "detail": (
                        "Has pedido demasiados códigos. Espera un rato antes de "
                        "volver a intentarlo."
                    ),
                    "code": "mfa_rate_limited",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if outcome == "failed":
            return Response(
                {
                    "detail": "No pudimos enviarte el código. Inténtalo de nuevo.",
                    "code": "mfa_email_failed",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(challenge_payload(otp, user), status=status.HTTP_200_OK)

    def _issue_session(self, request, user):
        """Acuña los tokens y registra la sesión. Único punto de emisión del
        camino con MFA: lo comparten la exención y el equipo de confianza."""
        from users.utils.session import create_session

        payload = CustomTokenObtainPairSerializer.build_response_for_user(user)
        try:
            decoded = jwt.decode(
                payload["access"], settings.SECRET_KEY, algorithms=["HS256"]
            )
            create_session(user, decoded, payload["refresh"], request)
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).error(
                "Failed to create session record (MFA bypass path): %s", exc
            )
        return Response(payload, status=status.HTTP_200_OK)

    def _app_access_denied(self, request, user):
        """Mismo gate de producto que el camino clásico, sin token que decodificar."""
        application = getattr(request, "application", None)
        if application is None or not getattr(application, "enforce_app_access", False):
            return None
        if user.is_superuser:
            return None
        try:
            from business.access import valid_app_codes_for_user

            granted = valid_app_codes_for_user(user) or []
        except Exception:  # noqa: BLE001
            # Igual que en get_token: si el cálculo falla no se echa a nadie.
            return None
        if application.code in granted:
            return None
        return Response(
            {
                "detail": (
                    f"No tienes acceso a {application.name}. "
                    "Comunícate con el administrador de tu empresa para habilitarlo."
                ),
                "code": "no_app_access",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    @staticmethod
    def _client_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    # ── Camino clásico (productos sin MFA) ──────────────────────────────────
    def _login_and_issue_tokens(self, request, *args, **kwargs):
        """Login user and create session record."""

        from users.utils.session import create_session

        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            # Get tokens from response
            access_token_str = response.data.get("access")
            refresh_token_str = response.data.get("refresh")

            # Decode access token to get JTI and user info
            try:
                access_token = jwt.decode(
                    access_token_str,
                    settings.SECRET_KEY,
                    algorithms=["HS256"],
                )
            except Exception:
                access_token = None

            # ── Gate de acceso por producto (rechazo en el login mismo) ──────────
            # Si el producto que llama (identificado por su X-API-Key → Application)
            # exige acceso y el usuario no lo tiene, se rechaza el login con 403 y un
            # mensaje claro. Gated por producto para no afectar a Atlas/Delta hasta su
            # backfill. Los superusuarios (equipo Atharix) nunca se bloquean.
            application = getattr(request, "application", None)
            if (
                access_token is not None
                and application is not None
                and getattr(application, "enforce_app_access", False)
            ):
                granted = access_token.get("app_access") or []
                if (
                    application.code not in granted
                    and not access_token.get("is_superuser")
                ):
                    return Response(
                        {
                            "detail": (
                                f"No tienes acceso a {application.name}. "
                                "Comunícate con el administrador de tu empresa para "
                                "habilitarlo."
                            ),
                            "code": "no_app_access",
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

            # Create session record (los errores no rompen el login)
            if access_token is not None:
                try:
                    from users.models import User

                    user = User.objects.get(id=access_token["user_id"])
                    create_session(user, access_token, refresh_token_str, request)
                except Exception as e:
                    # Log error but don't fail the login
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to create session record: {e}")

        return response


@extend_schema_view(
    get=extend_schema(description="Get current user profile", tags=["Authentication"]),
    put=extend_schema(
        description="Update current user profile", tags=["Authentication"]
    ),
    patch=extend_schema(
        description="Partially update current user profile",
        tags=["Authentication"],
    ),
)
class UserProfileView(generics.RetrieveUpdateAPIView):
    """User profile endpoint."""

    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Return current authenticated user."""
        return self.request.user


@extend_schema_view(
    post=extend_schema(
        description="Logout user and blacklist tokens", tags=["Authentication"]
    )
)
class UserLogoutView(APIView):
    """User logout endpoint."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Logout user by blacklisting the refresh token."""
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            from rest_framework_simplejwt.tokens import RefreshToken

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {"message": "Successfully logged out"},
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {"error": "Something went wrong during logout"},
                status=status.HTTP_400_BAD_REQUEST,
            )


@extend_schema_view(
    get=extend_schema(
        description="Verify if user token is still valid",
        tags=["Authentication"],
    )
)
class TokenVerifyView(APIView):
    """Token verification endpoint."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Verify that the token is still valid."""
        user = request.user

        # Acceso por producto: se devuelve el claim `app_access` horneado en el token
        # (los productos —Metis/Atlas/Delta— lo leen para rechazar en cada request).
        # Fallback: si el token es viejo y no trae el claim, se recalcula en vivo para
        # no expulsar sesiones ya abiertas durante el rollout.
        app_access = None
        if request.auth is not None:
            try:
                app_access = request.auth.get("app_access")
            except Exception:  # noqa: BLE001
                app_access = None
        if app_access is None:
            # Defensivo: no romper verify-token de ningún producto si el cálculo falla.
            try:
                from business.access import valid_app_codes_for_user

                app_access = valid_app_codes_for_user(user)
            except Exception:  # noqa: BLE001
                app_access = None

        return Response(
            {
                "valid": True,
                "user": UserProfileSerializer(user, context={"request": request}).data,
                "app_access": app_access,
            },
            status=status.HTTP_200_OK,
        )
