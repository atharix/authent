from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel


class Country(BaseModel):
    """
    Country model with multi-language support.

    Base language is Spanish (name field), with translations for:
    - Portuguese (pt)
    - English (en)
    - French (fr)
    - Italian (it)
    """

    # Basic country information
    name = models.CharField(
        _("Country Name"),
        max_length=100,
        unique=True,
        help_text=_("Country name in Spanish (base language)"),
    )

    code_iso2 = models.CharField(
        _("ISO 2-letter Code"),
        max_length=2,
        unique=True,
        help_text=_("ISO 3166-1 alpha-2 country code (e.g., MX, US, ES)"),
    )

    code_iso3 = models.CharField(
        _("ISO 3-letter Code"),
        max_length=3,
        unique=True,
        help_text=_("ISO 3166-1 alpha-3 country code (e.g., MEX, USA, ESP)"),
    )

    numeric_code = models.CharField(
        _("Numeric Code"),
        max_length=3,
        unique=True,
        blank=True,
        help_text=_("ISO 3166-1 numeric country code"),
    )

    # Multi-language fields
    name_pt = models.CharField(
        _("Name in Portuguese"),
        max_length=100,
        blank=True,
        help_text=_("Country name in Portuguese"),
    )

    name_en = models.CharField(
        _("Name in English"),
        max_length=100,
        blank=True,
        help_text=_("Country name in English"),
    )

    name_fr = models.CharField(
        _("Name in French"),
        max_length=100,
        blank=True,
        help_text=_("Country name in French"),
    )

    name_it = models.CharField(
        _("Name in Italian"),
        max_length=100,
        blank=True,
        help_text=_("Country name in Italian"),
    )

    # Additional fields
    phone_code = models.CharField(
        _("Phone Country Code"),
        max_length=5,
        blank=True,
        help_text=_("International dialing code (e.g., +52, +1, +34)"),
    )

    currency_code = models.CharField(
        _("Currency Code"),
        max_length=3,
        blank=True,
        help_text=_("ISO 4217 currency code (e.g., MXN, USD, EUR)"),
    )

    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        help_text=_("Whether this country is available for selection"),
    )

    sort_order = models.PositiveIntegerField(
        _("Sort Order"),
        default=0,
        help_text=_("Order for displaying countries (0 = first)"),
    )

    class Meta:
        verbose_name = _("Country")
        verbose_name_plural = _("Countries")
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["code_iso2", "is_active"]),
            models.Index(fields=["sort_order", "is_active"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code_iso2})"

    def get_localized_name(self, language_code="es"):
        """
        Get country name in specified language.
        Falls back to base name if translation not available.
        """
        language_map = {
            "pt": self.name_pt,
            "en": self.name_en,
            "fr": self.name_fr,
            "it": self.name_it,
            "es": self.name,
        }

        localized_name = language_map.get(language_code.lower(), "")
        return localized_name or self.name  # Fallback to base name

    def get_all_translations(self):
        """Get all available translations for this country."""
        return {
            "es": self.name,
            "pt": self.name_pt or self.name,
            "en": self.name_en or self.name,
            "fr": self.name_fr or self.name,
            "it": self.name_it or self.name,
        }
