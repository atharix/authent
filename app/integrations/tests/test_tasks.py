"""Verifica el mapeo User→LeadIn y Business→AccountIn, y short-circuit cuando
ATLAS_BRIDGE_ENABLED=False."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model

from atlas_bridge_client import ConvertResult, LeadResult
from business.models import Business
from integrations.tasks import (
    atlas_convert_lead_to_account_for_business,
    atlas_create_lead_for_user,
)

User = get_user_model()


@pytest.fixture
def enable_atlas(settings):
    settings.ATLAS_BRIDGE_ENABLED = True
    settings.ATLAS_BRIDGE_API_KEY = "atlas_testkey"
    settings.ATLAS_BRIDGE_BASE_URL = "https://atlas.test"
    settings.ATLAS_BRIDGE_TIMEOUT = 5.0
    settings.ATLAS_BRIDGE_MAX_RETRIES = 1


@pytest.mark.django_db
def test_create_lead_task_maps_user_to_leadin(enable_atlas):
    user = User.objects.create_user(
        email="ana@example.com",
        password="x",
        first_name="Ana",
        last_name="Pérez",
    )

    fake_client = MagicMock()
    fake_client.create_lead.return_value = LeadResult(
        lead_id=uuid4(), created=True
    )
    with patch("integrations.tasks.get_atlas_client", return_value=fake_client):
        atlas_create_lead_for_user(str(user.id))

    fake_client.create_lead.assert_called_once()
    payload = fake_client.create_lead.call_args.args[0]
    assert payload.email == "ana@example.com"
    assert payload.first_name == "Ana"
    assert payload.last_name == "Pérez"
    assert payload.source_detail == "authent.signup"
    assert "authent" in payload.tags


@pytest.mark.django_db
def test_create_lead_task_no_op_when_disabled(settings):
    settings.ATLAS_BRIDGE_ENABLED = False
    with patch("integrations.tasks.get_atlas_client") as mock_factory:
        atlas_create_lead_for_user(str(uuid4()))
    mock_factory.assert_not_called()


@pytest.mark.django_db
def test_create_lead_task_no_op_when_user_missing(enable_atlas):
    with patch("integrations.tasks.get_atlas_client") as mock_factory:
        atlas_create_lead_for_user(str(uuid4()))
    mock_factory.assert_not_called()


@pytest.mark.django_db
def test_convert_task_maps_business_to_accountin(enable_atlas):
    biz = Business.objects.create(
        name="Smoke",
        legal_name="Smoke SAS",
        tax_id="900123",
        industry="Tech",
        phone="+593999",
        email="hi@smoke.test",
    )

    fake_client = MagicMock()
    fake_client.convert_lead_to_account.return_value = ConvertResult(
        account_id=uuid4(), lead_id=uuid4(), created=True
    )
    with patch("integrations.tasks.get_atlas_client", return_value=fake_client):
        atlas_convert_lead_to_account_for_business(
            str(biz.id), "owner@example.com"
        )

    fake_client.convert_lead_to_account.assert_called_once()
    kwargs = fake_client.convert_lead_to_account.call_args.kwargs
    assert kwargs["email"] == "owner@example.com"
    assert kwargs["create_if_missing"] is True
    account = kwargs["account"]
    assert account.name == "Smoke SAS"  # legal_name preferido
    assert account.trade_name == "Smoke"
    assert account.tax_id == "900123"
    assert account.industry == "Tech"
    assert account.customer_entity_type == "company"


@pytest.mark.django_db
def test_convert_task_uses_name_when_no_legal_name(enable_atlas):
    biz = Business.objects.create(name="Solo Name")

    fake_client = MagicMock()
    fake_client.convert_lead_to_account.return_value = ConvertResult(
        account_id=uuid4(), lead_id=uuid4(), created=False
    )
    with patch("integrations.tasks.get_atlas_client", return_value=fake_client):
        atlas_convert_lead_to_account_for_business(
            str(biz.id), "owner@example.com"
        )

    account = fake_client.convert_lead_to_account.call_args.kwargs["account"]
    assert account.name == "Solo Name"
    assert account.trade_name == ""
