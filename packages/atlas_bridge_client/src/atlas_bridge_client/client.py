from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx

from ._http import request_with_retries
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

logger = logging.getLogger("atlas_bridge_client")


class AtlasBridgeClient:
    """Cliente sync para el inbound API de Atlas.

    Uso:
        client = AtlasBridgeClient(api_key="atlas_...", base_url="https://...")
        client.create_lead(LeadIn(first_name="Ana", email="a@b.com"))
    """

    INBOUND_PREFIX = "/api/bridge/inbound"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        user_agent: str = "atlas-bridge-client/0.1.0",
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        if not base_url:
            raise ValueError("base_url is required")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            headers={
                "X-API-Key": api_key,
                "User-Agent": user_agent,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    # ─────────────── lifecycle ───────────────

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AtlasBridgeClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ─────────────── endpoints ───────────────

    def create_lead(self, lead: LeadIn) -> LeadResult:
        data = self._post(
            f"{self.INBOUND_PREFIX}/leads/",
            lead.model_dump(mode="json", exclude_none=False),
        )
        return LeadResult.model_validate(data)

    def upsert_contact(self, contact: ContactIn) -> ContactResult:
        data = self._post(
            f"{self.INBOUND_PREFIX}/contacts/",
            contact.model_dump(mode="json", exclude_none=False),
        )
        return ContactResult.model_validate(data)

    def create_event(self, event: EventIn) -> EventResult:
        data = self._post(
            f"{self.INBOUND_PREFIX}/events/",
            event.model_dump(mode="json", exclude_none=False),
        )
        return EventResult.model_validate(data)

    def convert_lead_to_account(
        self,
        *,
        account: AccountIn,
        lead_id: UUID | str | None = None,
        email: str | None = None,
        phone: str | None = None,
        first_name: str = "",
        last_name: str = "",
        create_if_missing: bool = True,
    ) -> ConvertResult:
        if not any((lead_id, email, phone)):
            raise ValueError(
                "One of 'lead_id', 'email' or 'phone' is required."
            )
        payload: dict[str, Any] = {
            "account": account.model_dump(mode="json"),
            "create_if_missing": create_if_missing,
        }
        if lead_id is not None:
            payload["lead_id"] = str(lead_id)
        if email:
            payload["email"] = email
        if phone:
            payload["phone"] = phone
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name

        data = self._post(f"{self.INBOUND_PREFIX}/leads/convert/", payload)
        return ConvertResult.model_validate(data)

    # ─────────────── helpers ───────────────

    def _post(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        response = request_with_retries(
            self._client,
            "POST",
            path,
            json=json,
            max_retries=self._max_retries,
            backoff_base=self._backoff_base,
        )
        return response.json()
