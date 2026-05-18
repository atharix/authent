from __future__ import annotations


class AtlasBridgeError(Exception):
    """Base de todas las excepciones del cliente."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


class NetworkError(AtlasBridgeError):
    """Timeout, DNS, conexión rechazada, etc. Reintentable."""


class ServerError(AtlasBridgeError):
    """5xx del servidor. Reintentable."""


class AuthError(AtlasBridgeError):
    """401 — API key inválida o expirada. NO reintentable."""


class PermissionError(AtlasBridgeError):
    """403 — la API key no tiene el scope requerido. NO reintentable."""


class NotFoundError(AtlasBridgeError):
    """404 — recurso no encontrado. NO reintentable."""


class ValidationError(AtlasBridgeError):
    """400/422 — payload mal formado. NO reintentable."""
