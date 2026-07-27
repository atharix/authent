"""Baja de cuenta del titular (Art. 17 RGPD).

La llaman los productos (Metis, Atlas, Prometheus) después de haber suprimido sus
propios datos: primero se vacía cada producto y **al final** se anonimiza la
identidad aquí. Ese orden importa — si la identidad muriese primero, quedarían
datos en los productos sin forma de saber de quién eran.

La lógica vive en `users.deletion`; esto es solo la puerta HTTP.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..deletion import AccountDeletionError, delete_account


class DeleteAccountView(APIView):
    """`POST /api/auth/delete-account/` → anonimiza la cuenta del solicitante.

    Cuerpo: `{"password": "...", "reason": "..."}`.

    **La contraseña se vuelve a comprobar aquí** aunque el producto ya la haya
    validado. No es desconfianza del producto: es que esta operación es
    irreversible y afecta al acceso de la persona a todo el suite, así que la
    autorización no puede depender de que el llamante hiciera bien su parte.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Authentication"])
    def post(self, request):
        user = request.user
        password = request.data.get("password") or ""

        if not password:
            return Response(
                {
                    "detail": "Debes confirmar tu contraseña.",
                    "code": "password_required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.check_password(password):
            return Response(
                {"detail": "La contraseña no es correcta.", "code": "invalid_password"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            resultado = delete_account(
                user, reason=(request.data.get("reason") or "").strip()
            )
        except AccountDeletionError as exc:
            cuerpo = {"detail": exc.message, "code": exc.code}
            cuerpo.update(exc.detail)
            estado = (
                status.HTTP_409_CONFLICT
                if exc.code == "owner_with_members"
                else status.HTTP_400_BAD_REQUEST
            )
            return Response(cuerpo, status=estado)

        return Response(
            {"detail": "Tu cuenta ha sido dada de baja.", **resultado},
            status=status.HTTP_200_OK,
        )
