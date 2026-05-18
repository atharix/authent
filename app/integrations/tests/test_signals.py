"""Verifica que los post_save signals encolan las Celery tasks correctas."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

from business.models import Business, Collaborator

User = get_user_model()


@pytest.fixture
def enable_atlas(settings):
    settings.ATLAS_BRIDGE_ENABLED = True
    settings.ATLAS_BRIDGE_API_KEY = "atlas_testkey"
    settings.ATLAS_BRIDGE_BASE_URL = "https://atlas.test"


@pytest.fixture
def disable_atlas(settings):
    settings.ATLAS_BRIDGE_ENABLED = False


@pytest.mark.django_db(transaction=True)
def test_user_signup_enqueues_create_lead_task(enable_atlas):
    with patch(
        "integrations.signals.atlas_create_lead_for_user.delay"
    ) as mock_delay:
        user = User.objects.create_user(
            email="ana@example.com",
            password="x",
            first_name="Ana",
            last_name="P",
        )

    mock_delay.assert_called_once_with(str(user.id))


@pytest.mark.django_db(transaction=True)
def test_user_signup_skipped_when_disabled(disable_atlas):
    with patch(
        "integrations.signals.atlas_create_lead_for_user.delay"
    ) as mock_delay:
        User.objects.create_user(email="ana@example.com", password="x")

    mock_delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_business_create_enqueues_convert_task_with_owner_email(enable_atlas):
    owner = User.objects.create_user(
        email="owner@example.com", password="x", first_name="Owner"
    )
    owner_group, _ = Group.objects.get_or_create(name="owner")

    # Replicamos el patrón real de BusinessViewSet.perform_create:
    # Business + Collaborator se crean en la MISMA transacción atómica,
    # así on_commit dispara cuando ambos ya están persistidos.
    with patch(
        "integrations.signals.atlas_convert_lead_to_account_for_business.delay"
    ) as mock_delay:
        with transaction.atomic():
            biz = Business.objects.create(name="Smoke SAS")
            Collaborator.objects.create(
                user=owner, business=biz, role=owner_group, is_active=True
            )

    assert mock_delay.call_count == 1
    args, kwargs = mock_delay.call_args
    assert kwargs["business_id"] == str(biz.id)
    assert kwargs["user_email"] == "owner@example.com"


@pytest.mark.django_db(transaction=True)
def test_business_create_without_owner_does_not_enqueue(enable_atlas):
    with patch(
        "integrations.signals.atlas_convert_lead_to_account_for_business.delay"
    ) as mock_delay:
        with transaction.atomic():
            Business.objects.create(name="Lonely SAS")
    mock_delay.assert_not_called()
