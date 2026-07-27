"""Baja de cuenta en Authent: el eslabón que cierra el Art. 17 RGPD.

Authent es la fuente de verdad de la identidad de todo el suite, así que la
supresión de los productos (Metis, Atlas, Prometheus) queda incompleta si aquí
sobreviven el email, el teléfono, la fecha de nacimiento y el avatar. Este módulo
es lo que convierte «borré mis datos de Metis» en «ya no estoy».

## Por qué se anonimiza en vez de borrar

Un `user.delete()` **no puede funcionar**: hay 21 relaciones con
`on_delete=PROTECT` (`created_by`, `updated_by`, `deleted_by` de cada modelo que
hereda de `BaseModel`). En cuanto la persona ha creado cualquier cosa, el borrado
duro salta con `ProtectedError`.

Y está bien que sea así. Esas columnas son la trazabilidad de quién hizo qué, que
tiene su propia finalidad y sus propios plazos. Lo que exige el Art. 17 es que el
dato deje de identificar a nadie, no que desaparezca la fila: una vez anonimizado
el usuario, `created_by` apunta a un registro que ya no dice quién es.

## Qué se hace con cada cosa

- **Identidad** (email, nombre, teléfono, nacimiento, género, avatar): se
  anonimiza. El email pasa a un valor único e inválido porque la columna es
  `unique` y no admite vaciarla.
- **Credenciales y sesiones** (sesiones, restablecimientos, passkeys, retos,
  tokens vivos): se **borran**. Son acceso, no historia, y dejarlas vivas tras
  una baja es un agujero de seguridad.
- **Aceptaciones de términos**: la fila se **conserva** —es la prueba de que
  hubo contrato, Art. 17.3.e— pero se le quitan la IP y el user-agent, que
  identifican y ya no cumplen ninguna finalidad.
- **Colaboraciones y notificaciones**: se borran. La persona ya no pertenece a
  ninguna empresa y las notificaciones son contenido dirigido a ella.
"""

from __future__ import annotations

import logging
import uuid

from django.db import transaction

logger = logging.getLogger(__name__)

#: Dominio reservado (RFC 2606) para el email de una cuenta anonimizada. No es
#: enrutable, así que ningún correo puede acabar en manos de nadie.
_DOMINIO_ANONIMO = "deleted.invalid"

#: Nombre del grupo que marca a la persona dueña de una empresa.
_ROL_OWNER = "owner"


class AccountDeletionError(Exception):
    """Error que el titular puede corregir. Se traduce a un 4xx."""

    def __init__(self, message: str, *, code: str = "", detail=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.detail = detail or {}


def ownership_blocks(user) -> list[dict]:
    """Empresas donde es dueño y quedaría gente dentro.

    Es la misma guarda que aplica cada producto, repetida aquí a propósito:
    Authent no puede fiarse de que quien le llama ya la haya comprobado. Si el
    dueño desaparece y quedan personas dentro, la empresa se queda sin nadie que
    gestione sus accesos ni atienda sus derechos.
    """
    from business.models import Collaborator

    bloqueos = []
    propias = Collaborator.objects.filter(
        user=user, is_active=True, is_deleted=False, role__name=_ROL_OWNER
    ).select_related("business")

    for collab in propias:
        otros = (
            Collaborator.objects.filter(
                business=collab.business, is_active=True, is_deleted=False
            )
            .exclude(user=user)
            .count()
        )
        if otros:
            bloqueos.append(
                {
                    "business_id": str(collab.business_id),
                    "business_name": getattr(collab.business, "name", ""),
                    "remaining_members": otros,
                }
            )
    return bloqueos


def _anonimizar_identidad(user) -> None:
    """Deja la fila sin capacidad de identificar a nadie."""
    marca = uuid.uuid4().hex[:12]

    if user.avatar:
        # El fichero vive fuera de la base de datos: borrar la referencia no lo
        # borra a él. Sin esto quedaría una foto de la persona en el almacén.
        try:
            user.avatar.delete(save=False)
        except Exception:  # noqa: BLE001 — un fichero ausente no bloquea la baja
            logger.warning("No se pudo borrar el avatar.", exc_info=True)

    user.email = f"deleted-{marca}@{_DOMINIO_ANONIMO}"
    user.first_name = ""
    user.last_name = ""
    user.birth_date = None
    user.phone_number = ""
    user.gender = ""
    user.avatar = None
    user.is_active = False
    user.email_verified = False
    user.set_unusable_password()
    user.save()


def _purgar(queryset) -> int:
    """Borra de verdad, no lógicamente, y devuelve cuántas filas cayeron.

    Los modelos que heredan de `core.BaseModel` sobrescriben `delete()` para
    marcar `is_deleted=True` y devuelven un `int` en vez de la tupla de Django.
    En una supresión del Art. 17 eso no sirve: el dato seguiría en la tabla. Por
    eso se usa `hard_delete()` cuando existe.
    """
    borrado = (
        queryset.hard_delete if hasattr(queryset, "hard_delete") else queryset.delete
    )
    resultado = borrado()
    # `delete()` devuelve `(total, {modelo: n})`; el soft-delete de BaseModel, un int.
    return resultado[0] if isinstance(resultado, tuple) else int(resultado or 0)


def _borrar_credenciales(user) -> dict[str, int]:
    """Elimina todo lo que permitiría volver a entrar."""
    borrados: dict[str, int] = {}

    def _borra(etiqueta, queryset):
        try:
            borrados[etiqueta] = _purgar(queryset)
        except Exception:  # noqa: BLE001 — un modelo ausente no aborta la baja
            logger.warning("No se pudo limpiar %s en la baja.", etiqueta, exc_info=True)

    from users.models import PasswordReset, UserSession

    _borra("sesiones", UserSession.objects.filter(user=user))
    _borra("restablecimientos", PasswordReset.objects.filter(user=user))

    try:
        from webauthn_auth.models import WebAuthnChallenge, WebAuthnCredential

        _borra("passkeys", WebAuthnCredential.objects.filter(user=user))
        _borra("retos_webauthn", WebAuthnChallenge.objects.filter(user=user))
    except ImportError:
        pass

    try:
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

        _borra("tokens_vivos", OutstandingToken.objects.filter(user=user))
    except ImportError:
        pass

    return borrados


def _limpiar_rastro(user) -> dict[str, int]:
    """Notificaciones y colaboraciones fuera; aceptaciones de términos, escurridas."""
    resultado: dict[str, int] = {}

    try:
        from core.models import Notification

        # `all_objects` si existe: el manager por defecto filtra las ya marcadas
        # como borradas, y esas también tienen que irse de verdad.
        gestor = getattr(Notification, "all_objects", Notification.objects)
        resultado["notificaciones"] = _purgar(gestor.filter(user=user))
    except Exception:  # noqa: BLE001
        logger.warning("No se pudieron borrar las notificaciones.", exc_info=True)

    try:
        from business.models import Collaborator

        gestor = getattr(Collaborator, "all_objects", Collaborator.objects)
        resultado["colaboraciones"] = _purgar(gestor.filter(user=user))
    except Exception:  # noqa: BLE001
        logger.warning("No se pudieron borrar las colaboraciones.", exc_info=True)

    try:
        from users.models import UserTermsAcceptance

        # La fila se queda: prueba que hubo aceptación y de qué versión, que es
        # defensa de reclamaciones (Art. 17.3.e). Lo que se va es lo que
        # identifica: la IP y el navegador ya no sirven a ninguna finalidad
        # cuando el titular ha dejado de existir.
        resultado["aceptaciones_escurridas"] = UserTermsAcceptance.objects.filter(
            user=user
        ).update(ip_address=None, user_agent="")
    except Exception:  # noqa: BLE001
        logger.warning("No se pudieron escurrir las aceptaciones.", exc_info=True)

    return resultado


@transaction.atomic
def delete_account(user, *, reason: str = "") -> dict:
    """Anonimiza la cuenta y borra credenciales. Irreversible.

    Va en una transacción: una baja a medias —identidad anonimizada pero passkeys
    vivas, o al revés— sería peor que no haberla intentado.
    """
    bloqueos = ownership_blocks(user)
    if bloqueos:
        raise AccountDeletionError(
            "Eres propietario de una empresa con más personas dentro. "
            "Transfiere la propiedad o cierra la empresa antes de darte de baja.",
            code="owner_with_members",
            detail={"businesses": bloqueos},
        )

    email_original = user.email
    credenciales = _borrar_credenciales(user)
    rastro = _limpiar_rastro(user)
    _anonimizar_identidad(user)

    logger.info(
        "Cuenta dada de baja (anonimizada). motivo=%r credenciales=%s rastro=%s",
        reason or "no indicado",
        credenciales,
        rastro,
    )

    return {
        "anonymized": True,
        "previous_email_domain": (
            email_original.split("@")[-1] if "@" in email_original else ""
        ),
        "credentials_removed": credenciales,
        "traces_removed": rastro,
    }
