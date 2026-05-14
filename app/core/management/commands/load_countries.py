"""
Management command to load countries data directly (without fixtures).
"""

import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Country


SPAIN_VAT_OPTIONS = [
    {"code": "ES_GENERAL", "label": "General (21%)", "rate": 21, "is_default": True},
    {"code": "ES_REDUCED", "label": "Reducido (10%)", "rate": 10, "is_default": False},
    {"code": "ES_SUPER_REDUCED", "label": "Super reducido (4%)", "rate": 4, "is_default": False},
    {"code": "ES_EXEMPT", "label": "Exento", "rate": 0, "is_default": False},
]

ECUADOR_VAT_OPTIONS = [
    {"code": "EC_GENERAL", "label": "IVA 15%", "rate": 15, "is_default": True},
    {"code": "EC_REDUCED", "label": "IVA 5%", "rate": 5, "is_default": False},
    {"code": "EC_ZERO", "label": "IVA 0%", "rate": 0, "is_default": False},
    {"code": "EC_EXEMPT", "label": "Exento", "rate": 0, "is_default": False},
]


class Command(BaseCommand):
    help = "Load countries data into the database"

    def handle(self, *args, **options):
        """Execute the command."""
        self.stdout.write(self.style.SUCCESS("Loading countries..."))

        countries_data = [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "name": "España",
                "code_iso2": "ES",
                "code_iso3": "ESP",
                "numeric_code": "724",
                "name_pt": "Espanha",
                "name_en": "Spain",
                "name_fr": "Espagne",
                "name_it": "Spagna",
                "phone_code": "+34",
                "currency_code": "EUR",
                "vat_options": SPAIN_VAT_OPTIONS,
                "is_active": True,
                "sort_order": 1,
            },
            {
                "id": "00000000-0000-0000-0000-000000000002",
                "name": "Portugal",
                "code_iso2": "PT",
                "code_iso3": "PRT",
                "numeric_code": "620",
                "name_pt": "Portugal",
                "name_en": "Portugal",
                "name_fr": "Portugal",
                "name_it": "Portogallo",
                "phone_code": "+351",
                "currency_code": "EUR",
                "vat_options": [],
                "is_active": True,
                "sort_order": 2,
            },
            {
                "id": "00000000-0000-0000-0000-000000000003",
                "name": "México",
                "code_iso2": "MX",
                "code_iso3": "MEX",
                "numeric_code": "484",
                "name_pt": "México",
                "name_en": "Mexico",
                "name_fr": "Mexique",
                "name_it": "Messico",
                "phone_code": "+52",
                "currency_code": "MXN",
                "vat_options": [],
                "is_active": True,
                "sort_order": 3,
            },
            {
                "id": "00000000-0000-0000-0000-000000000004",
                "name": "Ecuador",
                "code_iso2": "EC",
                "code_iso3": "ECU",
                "numeric_code": "218",
                "name_pt": "Equador",
                "name_en": "Ecuador",
                "name_fr": "Équateur",
                "name_it": "Ecuador",
                "phone_code": "+593",
                "currency_code": "USD",
                "vat_options": ECUADOR_VAT_OPTIONS,
                "is_active": True,
                "sort_order": 4,
            },
        ]

        created_count = 0
        updated_count = 0

        for country_data in countries_data:
            country_id = uuid.UUID(country_data.pop("id"))

            country, created = Country.objects.update_or_create(
                id=country_id,
                defaults={
                    **country_data,
                    "created_at": timezone.now(),
                    "updated_at": timezone.now(),
                },
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Created: {country.name} ({country.code_iso2})"
                    )
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"🔄 Updated: {country.name} ({country.code_iso2})"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Done! Created: {created_count}, Updated: {updated_count}"
            )
        )
