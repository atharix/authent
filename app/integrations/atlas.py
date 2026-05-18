"""Factory del cliente Atlas Bridge para reutilizar conexiones HTTP."""

from __future__ import annotations

import logging
import threading

from django.conf import settings

from atlas_bridge_client import AtlasBridgeClient

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_instance: AtlasBridgeClient | None = None


def get_atlas_client() -> AtlasBridgeClient:
    """Singleton lazy del cliente. Reusa el pool de conexiones httpx."""
    global _instance
    if _instance is not None:
        return _instance
    with _lock:
        if _instance is None:
            _instance = AtlasBridgeClient(
                api_key=settings.ATLAS_BRIDGE_API_KEY,
                base_url=settings.ATLAS_BRIDGE_BASE_URL,
                timeout=settings.ATLAS_BRIDGE_TIMEOUT,
                max_retries=settings.ATLAS_BRIDGE_MAX_RETRIES,
            )
    return _instance


def reset_atlas_client() -> None:
    """Reset singleton (útil para tests)."""
    global _instance
    with _lock:
        if _instance is not None:
            try:
                _instance.close()
            except Exception:
                logger.exception("Error closing Atlas client")
        _instance = None
