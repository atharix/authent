from django.conf import settings
from django.db import models


class TermsAndConditions(models.Model):
    """Versioned terms & conditions document."""

    version = models.CharField(max_length=20, unique=True)
    content = models.TextField()
    is_active = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Terms and Conditions"
        verbose_name_plural = "Terms and Conditions"

    def __str__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"Terms v{self.version} ({status})"


class UserTermsAcceptance(models.Model):
    """Records a user's acceptance of a specific terms version."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="terms_acceptances",
    )
    terms = models.ForeignKey(
        TermsAndConditions,
        on_delete=models.CASCADE,
        related_name="acceptances",
    )
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        unique_together = [("user", "terms")]
        ordering = ["-accepted_at"]

    def __str__(self) -> str:
        return f"{self.user} accepted v{self.terms.version}"
