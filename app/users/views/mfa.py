"""Segundo paso del login: código por correo o aprobación desde la app.

Los tokens se acuñan AQUÍ, no en ``/login/``. Mientras el segundo factor no se
resuelve, el usuario tiene una contraseña válida y nada más.
"""

import logging

import jwt
from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models.mfa import EmailOtp, LoginApproval, PushApprover, TrustedDevice
from ..serializers import CustomTokenObtainPairSerializer
from ..serializers.mfa import (
    LoginApprovalApproveSerializer,
    LoginApprovalSerializer,
    MfaApprovalFallbackSerializer,
    MfaApprovalStatusSerializer,
    MfaResendSerializer,
    MfaVerifySerializer,
    PushApproverCreateSerializer,
    PushApproverSerializer,
    TrustedDeviceSerializer,
)
from ..utils.mfa import (
    application_code_of,
    challenge_payload,
    read_approval_token,
    read_mfa_token,
    send_otp_email,
    start_email_otp,
)

logger = logging.getLogger(__name__)

# Un solo cuerpo para "token inválido", "caducado" y "sin intentos": son el
# mismo callejón sin salida para el cliente (volver a empezar) y distinguirlos
# solo le daría señal a quien esté probando códigos.
_RESTART = {
    "detail": "El código ha caducado o ya no es válido. Vuelve a iniciar sesión.",
    "code": "mfa_restart",
}


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _load_otp(token, application_code=None):
    """Resuelve el desafío del token firmado, o None si ya no sirve."""
    otp_id = read_mfa_token(token)
    if not otp_id:
        return None
    otp = (
        EmailOtp.objects.select_related("user")
        .filter(id=otp_id, status=EmailOtp.PENDING)
        .first()
    )
    if otp is not None and application_code is not None:
        # Un desafío abierto desde un producto no se canjea desde otro: si no,
        # la API key de cualquier producto sirve para cerrar el login de todos.
        if (otp.application_code or "") != (application_code or ""):
            return None
    if otp is None or not otp.is_active or otp.attempts_left == 0:
        return None
    return otp


@extend_schema_view(
    post=extend_schema(
        description="Verify the emailed MFA code and issue tokens",
        tags=["Authentication"],
    )
)
class MfaVerifyView(APIView):
    """Canjea ``mfa_token`` + código por access/refresh."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        from users.utils.session import create_session

        serializer = MfaVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        otp = _load_otp(data["mfa_token"], application_code_of(request))
        if otp is None:
            return Response(_RESTART, status=status.HTTP_401_UNAUTHORIZED)

        # El intento se reclama en la base de datos antes de comparar nada: si no
        # quedaba presupuesto, aquí se acaba el desafío.
        if not otp.claim_attempt():
            otp.mark_cancelled()
            return Response(_RESTART, status=status.HTTP_401_UNAUTHORIZED)

        if not otp.check_code(data["code"]):
            if otp.attempts_left == 0:
                otp.mark_cancelled()
                return Response(_RESTART, status=status.HTTP_401_UNAUTHORIZED)
            return Response(
                {
                    "detail": "El código no es correcto.",
                    "code": "mfa_invalid_code",
                    "attempts_left": otp.attempts_left,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = otp.user
        if not user.is_active:
            otp.mark_cancelled()
            return Response(_RESTART, status=status.HTTP_401_UNAUTHORIZED)

        # Quemar el código gana la carrera o no hay tokens: dos peticiones con el
        # mismo código correcto no pueden acabar las dos en sesión.
        if not otp.consume():
            return Response(_RESTART, status=status.HTTP_401_UNAUTHORIZED)

        payload = CustomTokenObtainPairSerializer.build_response_for_user(user)

        try:
            decoded = jwt.decode(
                payload["access"], settings.SECRET_KEY, algorithms=["HS256"]
            )
            create_session(user, decoded, payload["refresh"], request)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to create session record (MFA login): %s", exc)

        if data.get("remember_device"):
            _, raw_token = TrustedDevice.issue(
                user,
                application_code=application_code_of(request),
                device_name=data.get("device_name", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                ip=_client_ip(request),
            )
            payload["device_token"] = raw_token
            payload["device_trusted_days"] = TrustedDevice.TTL_DAYS

        return Response(payload, status=status.HTTP_200_OK)


@extend_schema_view(
    post=extend_schema(
        description="Resend the MFA code for an open challenge",
        tags=["Authentication"],
    )
)
class MfaResendView(APIView):
    """Reenvía el código del desafío en curso, con cooldown y tope de envíos."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = MfaResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        otp = _load_otp(
            serializer.validated_data["mfa_token"], application_code_of(request)
        )
        if otp is None:
            return Response(_RESTART, status=status.HTTP_401_UNAUTHORIZED)

        if otp.resend_in > 0:
            return Response(
                {
                    "detail": "Espera un momento antes de pedir otro código.",
                    "code": "mfa_resend_cooldown",
                    "resend_in": otp.resend_in,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if otp.sends >= EmailOtp.MAX_SENDS:
            otp.mark_cancelled()
            return Response(_RESTART, status=status.HTTP_401_UNAUTHORIZED)

        code = EmailOtp.generate_code()
        if not send_otp_email(otp.user, code, otp):
            # El código anterior sigue vivo: no se mata lo que sí llegó por un
            # envío que ha fallado.
            return Response(
                {
                    "detail": "No pudimos enviarte el código. Inténtalo de nuevo.",
                    "code": "mfa_email_failed",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        otp.apply_code(code)

        return Response(
            {
                "sent": True,
                "expires_in": EmailOtp.TTL_SECONDS,
                "resend_in": otp.resend_in,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    list=extend_schema(
        description="List the current user's trusted devices", tags=["Authentication"]
    ),
    destroy=extend_schema(
        description="Revoke one trusted device", tags=["Authentication"]
    ),
)
class TrustedDeviceViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    """Equipos que se saltan el código, visibles y revocables por su dueño."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TrustedDeviceSerializer

    def get_queryset(self):
        return TrustedDevice.objects.filter(
            user=self.request.user, revoked_at__isnull=True
        ).order_by("-last_used_at")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["current_device_token"] = self.request.headers.get("X-Device-Token")
        return context

    def destroy(self, request, pk=None):
        device = self.get_queryset().filter(pk=pk).first()
        if device is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        device.revoke()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="revoke-all")
    def revoke_all(self, request):
        revoked = TrustedDevice.revoke_all_for(request.user)
        return Response({"revoked": revoked}, status=status.HTTP_200_OK)


# ── Aprobación desde la app ─────────────────────────────────────────────────


def _load_approval(token):
    """Resuelve la solicitud del token firmado, sin filtrar por estado.

    El sondeo necesita ver también las rechazadas y caducadas: son respuestas
    legítimas para quien espera, no errores.
    """
    approval_id = read_approval_token(token)
    if not approval_id:
        return None
    return (
        LoginApproval.objects.select_related("user", "approver")
        .filter(id=approval_id)
        .first()
    )


@extend_schema_view(
    post=extend_schema(
        description="Abandon a push approval and receive an emailed code instead",
        tags=["Authentication"],
    )
)
class MfaApprovalFallbackView(APIView):
    """Cambia el desafío de la app por un código al correo.

    Sin esta salida, un teléfono perdido, formateado o con la app desinstalada
    deja al dueño fuera de su cuenta: el aprobador sigue vivo, el login siempre
    elige la app y no hay otro camino. Ni siquiera resetear la contraseña sirve,
    porque el segundo factor se exige igual.

    No debilita el factor: quien llama ya acertó la contraseña —el token del
    desafío lo demuestra— y el correo es exactamente el segundo paso que le
    habría tocado de no tener la app enrolada.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = MfaApprovalFallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        approval = _load_approval(serializer.validated_data["mfa_token"])
        if approval is None or not approval.is_pending:
            return Response(_RESTART, status=status.HTTP_401_UNAUTHORIZED)

        user = approval.user
        if not user.is_active:
            approval.deny()
            return Response(_RESTART, status=status.HTTP_401_UNAUTHORIZED)

        # `start_email_otp` devuelve un resultado, no un booleano: "failed" y
        # "rate_limited" son cadenas y ambas son truthy, así que hay que
        # compararlas de verdad o el fallo de correo se cuela como éxito.
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
            # El desafío de la app sigue en pie: matarlo sin relevo dejaría al
            # usuario sin ningún camino abierto.
            return Response(
                {
                    "detail": "No pudimos enviarte el código. Inténtalo de nuevo.",
                    "code": "mfa_email_failed",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # El intento por app muere aquí: un push que llegue tarde no puede
        # aprobar un desafío que su dueño ya abandonó.
        approval.deny()

        return Response(challenge_payload(otp, user), status=status.HTTP_200_OK)


@extend_schema_view(
    post=extend_schema(
        description="Poll a push login approval and claim tokens once approved",
        tags=["Authentication"],
    )
)
class MfaApprovalStatusView(APIView):
    """Sondeo de la pantalla que pide entrar.

    Devuelve 200 en todos los desenlaces —incluido el rechazo— porque para el
    cliente son estados del desafío, no fallos de la petición. Los tokens se
    entregan en el primer sondeo que ve la aprobación y la solicitud queda
    consumida ahí mismo.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        from users.utils.session import create_session

        serializer = MfaApprovalStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        approval = _load_approval(data["mfa_token"])
        if approval is None or approval.status == LoginApproval.USED:
            return Response(_RESTART, status=status.HTTP_401_UNAUTHORIZED)

        if approval.status == LoginApproval.DENIED:
            return Response({"status": "denied"}, status=status.HTTP_200_OK)

        if approval.status == LoginApproval.PENDING:
            if approval.is_expired:
                return Response({"status": "expired"}, status=status.HTTP_200_OK)
            return Response(
                {"status": "pending", "expires_in": approval.expires_in},
                status=status.HTTP_200_OK,
            )

        user = approval.user
        if not user.is_active:
            approval.deny()
            return Response(_RESTART, status=status.HTTP_401_UNAUTHORIZED)

        approval.mark_used()

        payload = CustomTokenObtainPairSerializer.build_response_for_user(user)
        payload["status"] = "approved"

        try:
            decoded = jwt.decode(
                payload["access"], settings.SECRET_KEY, algorithms=["HS256"]
            )
            create_session(user, decoded, payload["refresh"], request)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to create session record (push approval): %s", exc)

        if data.get("remember_device"):
            _, raw_token = TrustedDevice.issue(
                user,
                application_code=application_code_of(request),
                device_name=data.get("device_name", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                ip=_client_ip(request),
            )
            payload["device_token"] = raw_token
            payload["device_trusted_days"] = TrustedDevice.TTL_DAYS

        return Response(payload, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        description="Login approvals waiting for this user's phone",
        tags=["Authentication"],
    ),
    retrieve=extend_schema(
        description="One pending login approval, with the numbers to choose from",
        tags=["Authentication"],
    ),
)
class LoginApprovalViewSet(
    viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin
):
    """Lo que la app abre al tocar el aviso — o al entrar y encontrarlo esperando.

    La lista existe porque el push no es fiable: si no llegó, la app enseña la
    solicitud igual en cuanto el usuario la abre.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LoginApprovalSerializer

    def get_queryset(self):
        return LoginApproval.objects.filter(
            user=self.request.user,
            status=LoginApproval.PENDING,
            expires_at__gt=timezone.now(),
        ).order_by("-created_at")

    def _owned(self, pk):
        """Cualquier solicitud del usuario, viva o no: rechazar tarde vale igual."""
        return LoginApproval.objects.filter(user=self.request.user, pk=pk).first()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        approval = self._owned(pk)
        if approval is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not approval.is_pending:
            return Response(
                {"status": approval.status, "code": "approval_not_pending"},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = LoginApprovalApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not approval.approve(serializer.validated_data["number"]):
            return Response(
                {
                    "detail": "Ese no es el número que aparece en la pantalla.",
                    "code": "approval_number_mismatch",
                    "status": approval.status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if approval.approver is not None:
            approval.approver.touch()
        return Response({"status": approval.status}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def deny(self, request, pk=None):
        approval = self._owned(pk)
        if approval is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if approval.is_pending:
            approval.deny()
        return Response({"status": approval.status}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        description="Devices allowed to approve this user's logins",
        tags=["Authentication"],
    ),
    create=extend_schema(
        description="Enrol the calling device as a login approver",
        tags=["Authentication"],
    ),
    destroy=extend_schema(
        description="Revoke one approver device", tags=["Authentication"]
    ),
)
class PushApproverViewSet(
    viewsets.GenericViewSet, mixins.ListModelMixin, mixins.CreateModelMixin
):
    """Alta y baja del teléfono que autoriza.

    Solo se enrola desde una sesión ya iniciada en el propio teléfono: eso es lo
    que ata el factor a un aparato concreto y lo que hace imposible que alguien
    acabe con un aprobador que nunca ha tenido en la mano.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PushApproverSerializer

    def get_queryset(self):
        return PushApprover.objects.filter(
            user=self.request.user, revoked_at__isnull=True
        ).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        serializer = PushApproverCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        approver, _created = PushApprover.objects.update_or_create(
            user=request.user,
            application_code=application_code_of(request),
            delivery_ref=data["delivery_ref"],
            revoked_at=None,
            defaults={
                "device_label": data.get("device_label", ""),
                "platform": data.get("platform", ""),
            },
        )
        return Response(
            PushApproverSerializer(approver).data, status=status.HTTP_201_CREATED
        )

    def destroy(self, request, pk=None):
        approver = self.get_queryset().filter(pk=pk).first()
        if approver is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        approver.revoke()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="revoke-all")
    def revoke_all(self, request):
        revoked = PushApprover.revoke_all_for(request.user)
        return Response({"revoked": revoked}, status=status.HTTP_200_OK)
