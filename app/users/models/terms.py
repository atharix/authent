from django.conf import settings
from django.db import models


class TermsAndConditions(models.Model):
    """Versioned legal document (terms or privacy policy) tied to an application."""

    KIND_TERMS = "terms"
    KIND_PRIVACY = "privacy"
    KIND_CHOICES = [
        (KIND_TERMS, "Términos y Condiciones"),
        (KIND_PRIVACY, "Política de Privacidad"),
    ]

    application = models.ForeignKey(
        "apps.Application",
        on_delete=models.CASCADE,
        related_name="legal_documents",
        null=True,
        blank=True,
        help_text="Application this document belongs to. NULL = global / cross-app.",
    )
    kind = models.CharField(
        max_length=20,
        choices=KIND_CHOICES,
        default=KIND_TERMS,
    )
    version = models.CharField(max_length=20)
    title = models.CharField(max_length=255, blank=True, default="")
    content = models.TextField()
    is_active = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Legal document"
        verbose_name_plural = "Legal documents"
        constraints = [
            models.UniqueConstraint(
                fields=["application", "kind", "version"],
                name="uniq_legal_doc_app_kind_version",
            ),
        ]

    def __str__(self) -> str:
        scope = self.application.name if self.application_id else "global"
        return f"{self.get_kind_display()} v{self.version} ({scope})"


class UserTermsAcceptance(models.Model):
    """Records a user's acceptance of a specific legal document version."""

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
        return f"{self.user} accepted {self.terms}"
