import logging

import jwt
from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from webauthn.helpers import bytes_to_base64url

from users.serializers.auth import CustomTokenObtainPairSerializer
from users.utils.session import create_session

from . import ceremonies
from .models import WebAuthnChallenge, WebAuthnCredential
from .serializers import (
    AuthenticateVerifyInputSerializer,
    RegisterVerifyInputSerializer,
    WebAuthnCredentialSerializer,
)
from .throttles import WebAuthnAuthOptionsThrottle, WebAuthnAuthVerifyThrottle

logger = logging.getLogger(__name__)

_GENERIC_AUTH_ERROR = {"error": "Authentication failed.", "code": "authentication_failed"}


def current_rp_credentials():
    """Credenciales que AÚN pueden usarse: las del RP ID vigente.

    Una passkey vive en el autenticador atada al RP ID con el que se creó, y no
    se ofrece para otro dominio. Al cambiar `WEBAUTHN_RP_ID`, las anteriores
    quedan muertas aunque su fila siga en la base. Filtrar por aquí es lo que
    hace que el sistema se cure solo: dejan de contarse, el listado del usuario
    sale vacío, y la app le pide registrar una nueva en vez de dejarlo fuera con
    una passkey que nunca va a funcionar.
    """
    return WebAuthnCredential.objects.filter(rp_id=settings.WEBAUTHN_RP_ID)


def _transports_of(credential) -> list:
    response_block = credential.get("response") or {}
    if isinstance(response_block, dict):
        return response_block.get("transports") or []
    return []


@extend_schema_view(
    post=extend_schema(
        description="Generate passkey registration options", tags=["WebAuthn"]
    )
)
class RegisterOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        WebAuthnChallenge.objects.filter(
            user=user, ceremony=WebAuthnChallenge.CEREMONY_REGISTRATION
        ).delete()
        # `excludeCredentials` evita registrar dos veces el mismo autenticador.
        # Solo tiene sentido con las del RP vigente: excluir una credencial de
        # otro RP impediría re-registrar el mismo dispositivo tras cambiar el
        # RP ID — justo lo que el usuario necesita hacer.
        existing = list(
            current_rp_credentials().filter(user=user).values_list(
                "credential_id", flat=True
            )
        )
        options, challenge = ceremonies.build_registration_options(user, existing)
        WebAuthnChallenge.objects.create(
            ceremony=WebAuthnChallenge.CEREMONY_REGISTRATION,
            challenge=challenge,
            user=user,
        )
        return Response({"options": options})


@extend_schema_view(
    post=extend_schema(
        description="Verify and store a newly registered passkey", tags=["WebAuthn"]
    )
)
class RegisterVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RegisterVerifyInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user

        challenge = (
            WebAuthnChallenge.objects.filter(
                user=user, ceremony=WebAuthnChallenge.CEREMONY_REGISTRATION
            )
            .order_by("-created_at")
            .first()
        )
        if challenge is None or not challenge.is_valid:
            return Response(
                {
                    "error": "Registration challenge missing or expired.",
                    "code": "challenge_invalid",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        credential = serializer.validated_data["credential"]
        try:
            verification = ceremonies.verify_registration(credential, challenge.challenge)
        except Exception as exc:
            logger.warning("Passkey registration verification failed: %s", exc)
            return Response(
                {"error": "Could not verify passkey.", "code": "verification_failed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        challenge.consume()

        try:
            cred = WebAuthnCredential.objects.create(
                user=user,
                # Se sella con el RP vigente: es lo que la ata a este dominio.
                rp_id=settings.WEBAUTHN_RP_ID,
                credential_id=bytes_to_base64url(verification.credential_id),
                public_key=bytes_to_base64url(verification.credential_public_key),
                sign_count=verification.sign_count,
                aaguid=getattr(verification, "aaguid", "") or "",
                transports=_transports_of(credential),
                friendly_name=serializer.validated_data.get("friendly_name", "") or "",
                backup_eligible=getattr(verification, "credential_device_type", "")
                == "multi_device",
                backup_state=getattr(verification, "credential_backed_up", False),
            )
        except IntegrityError:
            return Response(
                {
                    "error": "This passkey is already registered.",
                    "code": "already_registered",
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {"credential": WebAuthnCredentialSerializer(cred).data},
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    post=extend_schema(
        description="Generate usernameless passkey authentication options",
        tags=["WebAuthn"],
    )
)
class AuthenticateOptionsView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [WebAuthnAuthOptionsThrottle]

    def post(self, request):
        options, challenge = ceremonies.build_authentication_options()
        row = WebAuthnChallenge.objects.create(
            ceremony=WebAuthnChallenge.CEREMONY_AUTHENTICATION,
            challenge=challenge,
            user=None,
        )
        return Response({"state": row.state, "options": options})


@extend_schema_view(
    post=extend_schema(
        description="Verify a passkey assertion and issue JWT tokens",
        tags=["WebAuthn"],
    )
)
class AuthenticateVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [WebAuthnAuthVerifyThrottle]

    def post(self, request):
        serializer = AuthenticateVerifyInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        state = serializer.validated_data["state"]
        credential = serializer.validated_data["credential"]

        challenge = WebAuthnChallenge.objects.filter(
            state=state, ceremony=WebAuthnChallenge.CEREMONY_AUTHENTICATION
        ).first()
        if challenge is None or not challenge.is_valid:
            return Response(
                {
                    "error": "Authentication challenge missing or expired.",
                    "code": "challenge_invalid",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_id = credential.get("rawId") or credential.get("id")
        cred = None
        if raw_id:
            # Filtrado por RP vigente: una credencial de otro RP no puede
            # autenticar aquí. En la práctica el autenticador ni la ofrecería,
            # pero el backend no debe fiarse de eso — quien envía el assertion es
            # el cliente.
            cred = (
                current_rp_credentials()
                .select_related("user")
                .filter(credential_id=raw_id)
                .first()
            )
        if cred is None:
            return Response(_GENERIC_AUTH_ERROR, status=status.HTTP_401_UNAUTHORIZED)

        try:
            verification = ceremonies.verify_authentication(
                credential, challenge.challenge, cred.public_key, cred.sign_count
            )
        except Exception as exc:
            logger.warning("Passkey authentication verification failed: %s", exc)
            return Response(_GENERIC_AUTH_ERROR, status=status.HTTP_401_UNAUTHORIZED)

        new_count = verification.new_sign_count
        if cred.sign_count and new_count and new_count <= cred.sign_count:
            logger.error("Passkey sign-counter regression for credential %s", cred.id)
            return Response(_GENERIC_AUTH_ERROR, status=status.HTTP_401_UNAUTHORIZED)

        if not cred.user.is_active:
            return Response(_GENERIC_AUTH_ERROR, status=status.HTTP_401_UNAUTHORIZED)

        challenge.consume()
        cred.sign_count = new_count
        cred.backup_state = getattr(
            verification, "credential_backed_up", cred.backup_state
        )
        cred.last_used_at = timezone.now()
        cred.save(update_fields=["sign_count", "backup_state", "last_used_at"])

        payload = CustomTokenObtainPairSerializer.build_response_for_user(cred.user)

        try:
            decoded = jwt.decode(
                payload["access"], settings.SECRET_KEY, algorithms=["HS256"]
            )
            create_session(cred.user, decoded, payload["refresh"], request)
        except Exception as exc:
            logger.error("Failed to create session record (passkey login): %s", exc)

        return Response(payload)


@extend_schema_view(
    get=extend_schema(description="List the current user's passkeys", tags=["WebAuthn"])
)
class CredentialListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Solo las usables. Es el endpoint del que se fía la app para decidir si
        # pedirte registrar una passkey: si aquí se colasen las de un RP viejo,
        # creería que ya tienes una y te dejaría fuera sin ofrecerte arreglarlo.
        qs = current_rp_credentials().filter(user=request.user)
        return Response({"results": WebAuthnCredentialSerializer(qs, many=True).data})


@extend_schema_view(
    delete=extend_schema(description="Delete one of the user's passkeys", tags=["WebAuthn"])
)
class CredentialDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, credential_id):
        deleted = WebAuthnCredential.objects.filter(
            id=credential_id, user=request.user
        ).delete()[0]
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
