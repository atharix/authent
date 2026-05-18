"""Signals que disparan la sincronización con Atlas en signup y creación de business."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from business.models import Business, Collaborator

from .tasks import (
    atlas_convert_lead_to_account_for_business,
    atlas_create_lead_for_user,
)

logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(post_save, sender=User, dispatch_uid="integrations.atlas_lead_on_user_create")
def on_user_created(sender, instance, created, **kwargs):
    if not created:
        return
    if not getattr(settings, "ATLAS_BRIDGE_ENABLED", False):
        return

    user_id = str(instance.id)
    transaction.on_commit(
        lambda: atlas_create_lead_for_user.delay(user_id)
    )


@receiver(
    post_save,
    sender=Business,
    dispatch_uid="integrations.atlas_account_on_business_create",
)
def on_business_created(sender, instance, created, **kwargs):
    if not created:
        return
    if not getattr(settings, "ATLAS_BRIDGE_ENABLED", False):
        return

    business_id = str(instance.id)

    def _enqueue():
        # El Collaborator owner se crea dentro de la misma transacción que el Business.
        # Después de on_commit ya debe existir.
        owner = (
            Collaborator.objects.filter(
                business_id=business_id,
                role__name="owner",
                is_active=True,
                is_deleted=False,
            )
            .select_related("user")
            .first()
        )
        if not owner:
            logger.warning(
                "Business %s created without owner collaborator; "
                "skipping Atlas conversion",
                business_id,
            )
            return
        atlas_convert_lead_to_account_for_business.delay(
            business_id=business_id,
            user_email=owner.user.email,
        )

    transaction.on_commit(_enqueue)
