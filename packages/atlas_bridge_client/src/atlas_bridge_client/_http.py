from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .exceptions import (
    AtlasBridgeError,
    AuthError,
    NetworkError,
    NotFoundError,
    PermissionError,
    ServerError,
    ValidationError,
)

logger = logging.getLogger("atlas_bridge_client")


def _parse_error_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
        if isinstance(data, dict):
            return data
        return {"detail": data}
    except Exception:
        return {"detail": response.text[:500]}


def _raise_for_status(response: httpx.Response) -> None:
    code = response.status_code
    if code < 400:
        return
    payload = _parse_error_payload(response)
    message = str(payload.get("detail") or payload)[:500]

    if code == 401:
        raise AuthError(message, status_code=code, payload=payload)
    if code == 403:
        raise PermissionError(message, status_code=code, payload=payload)
    if code == 404:
        raise NotFoundError(message, status_code=code, payload=payload)
    if code in (400, 422):
        raise ValidationError(message, status_code=code, payload=payload)
    if 500 <= code < 600:
        raise ServerError(message, status_code=code, payload=payload)
    raise AtlasBridgeError(message, status_code=code, payload=payload)


def request_with_retries(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    json: dict[str, Any] | None = None,
    max_retries: int = 3,
    backoff_base: float = 1.0,
) -> httpx.Response:
    """Realiza el request con reintentos en NetworkError/ServerError.

    Reintenta hasta `max_retries` veces con backoff exponencial
    (`backoff_base * 2^attempt`). Solo reintenta errores transitorios.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = client.request(method, url, json=json)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = NetworkError(f"{type(exc).__name__}: {exc}")
        else:
            try:
                _raise_for_status(response)
                return response
            except ServerError as exc:
                last_exc = exc
            except AtlasBridgeError:
                # Errores 4xx no se reintentan
                raise

        if attempt < max_retries:
            sleep_s = backoff_base * (2**attempt)
            logger.warning(
                "atlas_bridge retry %s/%s after %.1fs: %s",
                attempt + 1,
                max_retries,
                sleep_s,
                last_exc,
            )
            time.sleep(sleep_s)

    assert last_exc is not None
    raise last_exc
