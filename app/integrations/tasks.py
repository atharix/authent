"""Celery tasks para sincronizar Authent → Atlas (lead/account)."""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model

from atlas_bridge_client import (
    AccountIn,
    LeadIn,
    NetworkError,
    ServerError,
)

from .atlas import get_atlas_client

logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task(
    bind=True,
    name="integrations.atlas_create_lead_for_user",
    autoretry_for=(NetworkError, ServerError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def atlas_create_lead_for_user(self, user_id: str) -> None:
    """Crea un Lead en Atlas a partir del User recién registrado."""
    if not settings.ATLAS_BRIDGE_ENABLED:
        return
    if not settings.ATLAS_BRIDGE_API_KEY or not settings.ATLAS_BRIDGE_BASE_URL:
        logger.warning(
            "ATLAS_BRIDGE not configured; skipping lead creation for user=%s",
            user_id,
        )
        return

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.warning("User %s no longer exists; skipping Atlas lead", user_id)
        return

    client = get_atlas_client()
    first_name = (user.first_name or user.email.split("@")[0])[:150]
    payload = LeadIn(
        first_name=first_name,
        last_name=(user.last_name or "")[:150],
        email=user.email,
        source_detail="authent.signup",
        tags=["authent", "signup"],
    )
    result = client.create_lead(payload)
    logger.info(
        "Atlas lead synced user=%s lead_id=%s created=%s",
        user.email,
        result.lead_id,
        result.created,
    )


@shared_task(
    bind=True,
    name="integrations.atlas_convert_lead_to_account_for_business",
    autoretry_for=(NetworkError, ServerError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def atlas_convert_lead_to_account_for_business(
    self, business_id: str, user_email: str
) -> None:
    """Convierte el Lead del creador del business en un Account en Atlas."""
    if not settings.ATLAS_BRIDGE_ENABLED:
        return
    if not settings.ATLAS_BRIDGE_API_KEY or not settings.ATLAS_BRIDGE_BASE_URL:
        logger.warning(
            "ATLAS_BRIDGE not configured; skipping account conversion for business=%s",
            business_id,
        )
        return

    # Import local para evitar problemas de orden de carga
    from business.models import Business

    try:
        business = Business.objects.get(id=business_id)
    except Business.DoesNotExist:
        logger.warning(
            "Business %s no longer exists; skipping Atlas conversion", business_id
        )
        return

    client = get_atlas_client()
    account_name = business.legal_name or business.name
    trade_name = business.name if business.legal_name else ""

    account = AccountIn(
        name=account_name[:255],
        trade_name=trade_name[:255],
        tax_id=(business.tax_id or "")[:50],
        industry=(business.industry or "")[:100],
        customer_entity_type="company",
        phone=(business.phone or "")[:30],
        email=business.email or "",
        website=business.website or "",
        address=(business.address or "")[:300],
    )

    result = client.convert_lead_to_account(
        email=user_email,
        account=account,
        create_if_missing=True,
    )
    logger.info(
        "Atlas account synced business=%s account_id=%s lead_id=%s created=%s",
        business.id,
        result.account_id,
        result.lead_id,
        result.created,
    )
