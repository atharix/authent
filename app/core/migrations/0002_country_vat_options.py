from django.db import migrations, models


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

ECUADOR_FIXTURE = {
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
}


def forwards(apps, schema_editor):
    Country = apps.get_model("core", "Country")
    Country.objects.filter(code_iso2="ES").update(vat_options=SPAIN_VAT_OPTIONS)
    Country.objects.update_or_create(
        code_iso2="EC",
        defaults={k: v for k, v in ECUADOR_FIXTURE.items() if k != "id"},
    )


def backwards(apps, schema_editor):
    Country = apps.get_model("core", "Country")
    Country.objects.filter(code_iso2__in=["ES", "EC"]).update(vat_options=[])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="country",
            name="vat_options",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "List of VAT regimes available in this country, each as "
                    "{code, label, rate, is_default}. The frontend uses this to "
                    "populate the fiscal regime selector when this country is chosen."
                ),
                verbose_name="VAT Options",
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
