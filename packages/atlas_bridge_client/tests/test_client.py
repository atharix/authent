from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
import respx

from atlas_bridge_client import (
    AccountIn,
    AtlasBridgeClient,
    AuthError,
    ContactIn,
    EventIn,
    LeadIn,
    NotFoundError,
    PermissionError,
    ServerError,
    ValidationError,
)

BASE_URL = "https://atlas.test"
API_KEY = "atlas_testkey"


@pytest.fixture
def client():
    c = AtlasBridgeClient(
        api_key=API_KEY,
        base_url=BASE_URL,
        timeout=2.0,
        max_retries=2,
        backoff_base=0.0,  # tests sin sleep real
    )
    yield c
    c.close()


@respx.mock
def test_create_lead_success(client):
    lead_id = uuid4()
    route = respx.post(f"{BASE_URL}/api/bridge/inbound/leads/").mock(
        return_value=httpx.Response(201, json={"lead_id": str(lead_id), "created": True})
    )

    result = client.create_lead(
        LeadIn(first_name="Ana", email="ana@example.com", tags=["t1"])
    )

    assert route.called
    body = route.calls[0].request.read().decode()
    assert "ana@example.com" in body
    assert result.lead_id == lead_id
    assert result.created is True


@respx.mock
def test_create_lead_dedup_returns_200_created_false(client):
    lead_id = uuid4()
    respx.post(f"{BASE_URL}/api/bridge/inbound/leads/").mock(
        return_value=httpx.Response(200, json={"lead_id": str(lead_id), "created": False})
    )

    result = client.create_lead(LeadIn(first_name="Ana", email="ana@example.com"))
    assert result.created is False


@respx.mock
def test_upsert_contact(client):
    contact_id = uuid4()
    respx.post(f"{BASE_URL}/api/bridge/inbound/contacts/").mock(
        return_value=httpx.Response(
            201, json={"contact_id": str(contact_id), "created": True}
        )
    )
    result = client.upsert_contact(ContactIn(first_name="Bob", phone="+593999"))
    assert result.contact_id == contact_id


@respx.mock
def test_create_event(client):
    event_id = uuid4()
    contact_id = uuid4()
    respx.post(f"{BASE_URL}/api/bridge/inbound/events/").mock(
        return_value=httpx.Response(
            201, json={"event_id": str(event_id), "contact_id": str(contact_id)}
        )
    )
    result = client.create_event(
        EventIn(event_type="meeting_scheduled", contact_email="c@x.com")
    )
    assert result.event_id == event_id


@respx.mock
def test_convert_lead_to_account_success(client):
    account_id = uuid4()
    lead_id = uuid4()
    route = respx.post(f"{BASE_URL}/api/bridge/inbound/leads/convert/").mock(
        return_value=httpx.Response(
            201,
            json={
                "account_id": str(account_id),
                "lead_id": str(lead_id),
                "created": True,
            },
        )
    )

    result = client.convert_lead_to_account(
        email="ana@example.com",
        account=AccountIn(name="Ana SAS", tax_id="900", industry="Tech"),
    )

    assert route.called
    body = route.calls[0].request.read().decode()
    assert "ana@example.com" in body
    assert "Ana SAS" in body
    assert "create_if_missing" in body
    assert result.account_id == account_id
    assert result.created is True


def test_convert_requires_identifier(client):
    with pytest.raises(ValueError):
        client.convert_lead_to_account(account=AccountIn(name="x"))


# ─────────────────────── error mapping ───────────────────────


@respx.mock
def test_auth_error_not_retried(client):
    route = respx.post(f"{BASE_URL}/api/bridge/inbound/leads/").mock(
        return_value=httpx.Response(401, json={"detail": "Invalid API key."})
    )
    with pytest.raises(AuthError) as exc:
        client.create_lead(LeadIn(first_name="A", email="a@b.com"))
    assert exc.value.status_code == 401
    assert route.call_count == 1  # no retry


@respx.mock
def test_permission_error(client):
    respx.post(f"{BASE_URL}/api/bridge/inbound/leads/").mock(
        return_value=httpx.Response(403, json={"detail": "Missing scope."})
    )
    with pytest.raises(PermissionError):
        client.create_lead(LeadIn(first_name="A", email="a@b.com"))


@respx.mock
def test_not_found(client):
    respx.post(f"{BASE_URL}/api/bridge/inbound/leads/convert/").mock(
        return_value=httpx.Response(404, json={"detail": "Lead not found."})
    )
    with pytest.raises(NotFoundError):
        client.convert_lead_to_account(
            email="x@y.com",
            account=AccountIn(name="x"),
            create_if_missing=False,
        )


@respx.mock
def test_validation_error(client):
    respx.post(f"{BASE_URL}/api/bridge/inbound/leads/").mock(
        return_value=httpx.Response(400, json={"detail": "bad payload"})
    )
    with pytest.raises(ValidationError):
        client.create_lead(LeadIn(first_name="A", email="a@b.com"))


@respx.mock
def test_server_error_retries_then_succeeds(client):
    lead_id = uuid4()
    route = respx.post(f"{BASE_URL}/api/bridge/inbound/leads/").mock(
        side_effect=[
            httpx.Response(503, json={"detail": "down"}),
            httpx.Response(201, json={"lead_id": str(lead_id), "created": True}),
        ]
    )
    result = client.create_lead(LeadIn(first_name="A", email="a@b.com"))
    assert route.call_count == 2
    assert result.lead_id == lead_id


@respx.mock
def test_server_error_exhausts_retries(client):
    route = respx.post(f"{BASE_URL}/api/bridge/inbound/leads/").mock(
        return_value=httpx.Response(500, json={"detail": "boom"})
    )
    with pytest.raises(ServerError):
        client.create_lead(LeadIn(first_name="A", email="a@b.com"))
    # max_retries=2 → 3 intentos totales
    assert route.call_count == 3


def test_constructor_validates_inputs():
    with pytest.raises(ValueError):
        AtlasBridgeClient(api_key="", base_url="https://x")
    with pytest.raises(ValueError):
        AtlasBridgeClient(api_key="k", base_url="")


def test_lead_in_requires_email_or_phone():
    with pytest.raises(Exception):  # pydantic ValidationError
        LeadIn(first_name="x")


def test_event_in_requires_contact_ref():
    with pytest.raises(Exception):
        EventIn(event_type="meeting_scheduled")
