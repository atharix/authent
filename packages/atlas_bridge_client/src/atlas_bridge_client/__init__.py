"""HTTP client for the Atlas inbound API."""

from .client import AtlasBridgeClient
from .exceptions import (
    AtlasBridgeError,
    AuthError,
    NetworkError,
    NotFoundError,
    PermissionError,
    ServerError,
    ValidationError,
)
from .models import (
    AccountIn,
    ContactIn,
    ContactResult,
    ConvertResult,
    EventIn,
    EventResult,
    LeadIn,
    LeadResult,
)

__version__ = "0.1.0"

__all__ = [
    "AtlasBridgeClient",
    "AccountIn",
    "ContactIn",
    "ContactResult",
    "ConvertResult",
    "EventIn",
    "EventResult",
    "LeadIn",
    "LeadResult",
    "AtlasBridgeError",
    "AuthError",
    "NetworkError",
    "NotFoundError",
    "PermissionError",
    "ServerError",
    "ValidationError",
]
