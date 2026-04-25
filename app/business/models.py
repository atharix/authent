from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models

from core.models import BaseModel


class Business(BaseModel):
    """A company/organization within the Atharix ecosystem."""

    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True, default="")
    tax_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    country = models.ForeignKey(
        "core.Country",
        on_delete=models.SET_NULL,
        related_name="businesses",
        null=True,
        blank=True,
    )
    industry = models.CharField(max_length=120, blank=True, default="")
    website = models.URLField(blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    address = models.TextField(blank=True, default="")
    logo = models.ImageField(upload_to="business/logos/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "business"
        ordering = ["name"]
        verbose_name = "Business"
        verbose_name_plural = "Businesses"

    def __str__(self) -> str:
        return self.name


class Collaborator(BaseModel):
    """User ↔ Business relationship with a role (Group)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="collaborations",
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="collaborators",
    )
    role = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        related_name="collaborators",
        null=True,
        blank=True,
    )
    title = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Free-text job title (independent from the role/Group).",
    )
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "business_collaborator"
        unique_together = [("user", "business")]
        ordering = ["-joined_at"]
        verbose_name = "Collaborator"
        verbose_name_plural = "Collaborators"

    def __str__(self) -> str:
        role_name = self.role.name if self.role else "no role"
        return f"{self.user} @ {self.business} ({role_name})"
