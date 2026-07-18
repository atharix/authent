"""Acceso por empresa↔producto: la fuente de verdad de qué software puede usar cada empresa.

**Se deniega por defecto**: sin una fila `BusinessAppAccess` válida para (empresa,
producto), no hay acceso. Este módulo centraliza:

- `valid_app_codes_for_user`: los productos que un usuario puede usar (para el claim
  `app_access` del JWT y el rechazo de login/request).
- `app_access_state`: el estado detallado de licencia de una empresa para un producto
  (para que los productos —Metis/Atlas/Delta— pinten su pantalla de Licenciamiento sin
  ser dueños del dato).

Los códigos de bloqueo replican los que ya usa Metis para que el frontend no tenga que
cambiar de contrato.
"""

from __future__ import annotations

# ─── Códigos de bloqueo (mismos que Metis) ───────────────────────────────────
NO_LICENSE_CODE = "no_license"
LICENSE_EXPIRED_CODE = "license_expired"
BUSINESS_DISABLED_CODE = "business_disabled"

BLOCK_MESSAGES = {
    NO_LICENSE_CODE: (
        "Tu empresa no tiene una licencia de {product} asignada. "
        "Comunícate con el administrador para activarla."
    ),
    LICENSE_EXPIRED_CODE: (
        "La licencia de {product} de tu empresa venció. "
        "Comunícate con el administrador para renovarla."
    ),
    BUSINESS_DISABLED_CODE: (
        "El acceso a {product} está suspendido para tu empresa. "
        "Comunícate con el administrador para reactivarlo."
    ),
}


def _get_access(business, application):
    """La fila `BusinessAppAccess` viva de (empresa, producto), o `None`."""
    from .models import BusinessAppAccess

    return (
        BusinessAppAccess.objects.filter(
            business=business, application=application, is_deleted=False
        )
        .select_related("application")
        .first()
    )


def block_code(business, application) -> str | None:
    """Por qué NO puede entrar esta empresa a este producto, o `None` si sí puede.

    Se deniega por defecto: sin fila o con licencia `NONE` → `no_license`.
    """
    from .models import LicenseType

    access = _get_access(business, application)
    if access is None or access.license_type == LicenseType.NONE:
        return NO_LICENSE_CODE
    if access.is_expired:
        return LICENSE_EXPIRED_CODE
    if not access.is_enabled:
        return BUSINESS_DISABLED_CODE
    return None


def has_access(business, application) -> bool:
    """¿La empresa tiene acceso válido a este producto?"""
    if application is None or not getattr(application, "is_active", False):
        return False
    return block_code(business, application) is None


def valid_app_codes_for_user(user) -> list[str]:
    """Códigos de los productos que el usuario puede usar: tiene ≥1 colaboración
    activa en una empresa con un `BusinessAppAccess` válido para ese producto.

    Es lo que se hornea en el claim `app_access` del JWT y lo que consulta el rechazo
    de login/request.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    from .models import BusinessAppAccess

    accesses = (
        BusinessAppAccess.objects.filter(
            is_deleted=False,
            business__is_deleted=False,
            business__collaborators__user=user,
            business__collaborators__is_active=True,
            business__collaborators__is_deleted=False,
        )
        .select_related("application")
        .distinct()
    )
    codes = {
        access.application.code
        for access in accesses
        if access.is_valid and access.application.is_active and access.application.code
    }
    return sorted(codes)


def app_access_state(business, application) -> dict:
    """Estado detallado de la licencia de una empresa para un producto.

    Fuente única que consumen los productos para decidir entre dejar entrar o pintar la
    pantalla de bloqueo (incluye asientos, vencimiento y motivo). Aditivo: no rompe
    consumidores existentes.
    """
    access = _get_access(business, application)
    code = block_code(business, application)
    product = getattr(application, "name", "") or getattr(application, "code", "") or ""
    active_collaborators = business.collaborators.filter(
        is_active=True, is_deleted=False
    ).count()
    max_users = access.max_users if access else 0
    return {
        "application": getattr(application, "code", None),
        "application_name": product,
        "has_access": code is None,
        "block_code": code,
        "message": (BLOCK_MESSAGES.get(code, "").format(product=product) if code else ""),
        "notice": (access.access_notice if access else ""),
        "is_enabled": bool(access.is_enabled) if access else False,
        "license": {
            "type": access.license_type if access else "none",
            "has_license": bool(access and access.license_type != "none"),
            "expires_at": (
                access.expires_at.isoformat() if access and access.expires_at else None
            ),
            "is_expired": bool(access.is_expired) if access else False,
        },
        "seats": {
            "max_users": max_users,
            "active_collaborators": active_collaborators,
            "available": max(max_users - active_collaborators, 0),
            "is_full": active_collaborators >= max_users,
            "is_over_limit": active_collaborators > max_users,
        },
    }
