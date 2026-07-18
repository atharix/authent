import jwt
from django.conf import settings
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from ..serializers import CustomTokenObtainPairSerializer, UserProfileSerializer


@extend_schema_view(
    post=extend_schema(
        description="Login with email and password", tags=["Authentication"]
    )
)
class UserLoginView(TokenObtainPairView):
    """User login endpoint with JWT tokens."""

    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
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
