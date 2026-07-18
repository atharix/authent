from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.utils import timezone

from core.models import BaseModel


class LicenseType(models.TextChoices):
    """Qué tiene contratado una empresa para un producto. `NONE` es el default y
    **bloquea** el acceso: una empresa sin licencia no entra hasta que se provisiona."""

    NONE = "none", "Sin licencia"
    TRIAL = "trial", "Prueba"
    STANDARD = "standard", "Estándar"
    ENTERPRISE = "enterprise", "Enterprise"


class Industry(BaseModel):
    """Catalog of business industries / areas."""

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    icon = models.CharField(max_length=50, blank=True, default="")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    name_pt = models.CharField(max_length=100, blank=True, default="")
    name_en = models.CharField(max_length=100, blank=True, default="")
    name_fr = models.CharField(max_length=100, blank=True, default="")
    name_it = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        db_table = "industry"
        ordering = ["sort_order", "name"]
        verbose_name = "Industry"
        verbose_name_plural = "Industries"

    def __str__(self) -> str:
        return self.name

    def get_localized_name(self, language_code: str = "es") -> str:
        language_map = {
            "pt": self.name_pt,
            "en": self.name_en,
            "fr": self.name_fr,
            "it": self.name_it,
            "es": self.name,
        }
        return language_map.get(language_code.lower(), "") or self.name

    def get_all_translations(self) -> dict:
        return {
            "es": self.name,
            "pt": self.name_pt or self.name,
            "en": self.name_en or self.name,
            "fr": self.name_fr or self.name,
            "it": self.name_it or self.name,
        }


class Business(BaseModel):
    """A company/organization within the Atharix ecosystem."""

    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True, default="")
    tax_id = models.CharField(max_length=50, null=True, blank=True)
    fiscal_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Full legal/fiscal name as it appears on invoices",
    )
    registration_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Mercantile / commercial registry number (optional)",
    )
    country = models.ForeignKey(
        "core.Country",
        on_delete=models.SET_NULL,
        related_name="businesses",
        null=True,
        blank=True,
    )
    currency = models.CharField(
        max_length=3,
        blank=True,
        default="",
        help_text="ISO 4217 currency code (e.g. EUR, USD). Defaults to country.currency_code",
    )
    vat_regime = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="VAT regime code chosen from country.vat_options",
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


class BusinessAppAccess(BaseModel):
    """Qué producto (Application) tiene contratado una empresa (Business), con su licencia.

    **Fuente de verdad del acceso por empresa↔producto** para todo el ecosistema
    (Metis / Atlas / Delta). Absorbe el licenciamiento que antes vivía dentro de
    cada producto (tipo, vencimiento, asientos, on/off).

    **Se deniega por defecto**: sin una fila válida para (empresa, producto), la
    empresa no tiene acceso a ese producto. Un olvido deja la puerta cerrada.
    """

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="app_accesses",
    )
    application = models.ForeignKey(
        "apps.Application",
        on_delete=models.PROTECT,
        related_name="business_accesses",
    )
    license_type = models.CharField(
        max_length=20,
        choices=LicenseType.choices,
        default=LicenseType.NONE,
        help_text="«Sin licencia» bloquea el acceso de toda la empresa a este producto.",
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Interruptor manual, por encima de la licencia. Desactívalo para cortar "
            "en seco el acceso aunque la licencia siga vigente."
        ),
    )
    expires_at = models.DateField(
        null=True,
        blank=True,
        help_text="Pasada esta fecha la empresa queda bloqueada. Vacío = no caduca.",
    )
    max_users = models.PositiveIntegerField(
        default=0,
        help_text="Asientos contratados para este producto. 0 = no cabe nadie nuevo.",
    )
    access_notice = models.TextField(
        blank=True,
        default="",
        help_text="Mensaje opcional para la pantalla de bloqueo del producto.",
    )

    class Meta:
        db_table = "business_app_access"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "application"],
                condition=models.Q(is_deleted=False),
                name="uniq_business_application_active",
            ),
        ]
        verbose_name = "Acceso a producto"
        verbose_name_plural = "Accesos a productos"

    def __str__(self) -> str:
        return f"{self.business} → {self.application} ({self.license_type})"

    @property
    def is_expired(self) -> bool:
        """Vacío = no caduca. Vence al TERMINAR el día indicado (`<`, no `<=`)."""
        if self.expires_at is None:
            return False
        return self.expires_at < timezone.localdate()

    @property
    def is_valid(self) -> bool:
        """Acceso efectivo: licencia asignada (≠ NONE), habilitada y no vencida."""
        return (
            not self.is_deleted
            and self.license_type != LicenseType.NONE
            and self.is_enabled
            and not self.is_expired
        )
