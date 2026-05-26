"""Seed extendido de `Country.vat_options` para FR, US, CL, BR, AR, PT.

La migración 0002 cubre solo España y Ecuador. Esta agrega los catálogos
de los siguientes países donde Atharix opera o tiene customers activos.

Tasas vigentes a la fecha de creación de la migración (2026). Si la
autoridad fiscal del país actualiza tasas, crear una migración nueva
(no editar esta) para preservar la auditabilidad de los cambios.

US: no aplica IVA federal. Catálogo simbólico (US_NONE + US_OTHER) para
que el TaxCodePicker no quede bloqueado; el sales tax estatal se gestiona
fuera del sistema (típicamente vía Avalara/TaxJar post-checkout).

Idempotente: solo escribe sobre países cuyo `vat_options` esté vacío,
nunca sobre ediciones manuales del admin ni sobre sync re-aplicado.
"""

from django.db import migrations


FRANCE_VAT_OPTIONS = [
    {"code": "FR_NORMAL",       "label": "Normal (20%)",        "rate": 20,  "is_default": True},
    {"code": "FR_INTERMEDIATE", "label": "Intermedio (10%)",    "rate": 10,  "is_default": False},
    {"code": "FR_REDUCED",      "label": "Reducido (5.5%)",     "rate": 5.5, "is_default": False},
    {"code": "FR_SPECIAL",      "label": "Especial (2.1%)",     "rate": 2.1, "is_default": False},
    {"code": "FR_EXEMPT",       "label": "Exento",              "rate": 0,   "is_default": False},
]

USA_VAT_OPTIONS = [
    {"code": "US_NONE",  "label": "Sin impuesto federal",                    "rate": 0, "is_default": True},
    {"code": "US_OTHER", "label": "Otro (sales tax local fuera del sistema)", "rate": 0, "is_default": False},
]

CHILE_VAT_OPTIONS = [
    {"code": "CL_IVA",    "label": "IVA (19%)", "rate": 19, "is_default": True},
    {"code": "CL_EXEMPT", "label": "Exento",    "rate": 0,  "is_default": False},
]

BRAZIL_VAT_OPTIONS = [
    {"code": "BR_ICMS_17", "label": "ICMS general (17%)",  "rate": 17, "is_default": True},
    {"code": "BR_ICMS_18", "label": "ICMS SP/RJ/MG (18%)", "rate": 18, "is_default": False},
    {"code": "BR_ISS_5",   "label": "ISS servicios (5%)",  "rate": 5,  "is_default": False},
    {"code": "BR_EXEMPT",  "label": "Isento",              "rate": 0,  "is_default": False},
]

ARGENTINA_VAT_OPTIONS = [
    {"code": "AR_GENERAL",   "label": "IVA general (21%)",    "rate": 21,   "is_default": True},
    {"code": "AR_REDUCED",   "label": "IVA reducido (10.5%)", "rate": 10.5, "is_default": False},
    {"code": "AR_AUGMENTED", "label": "IVA aumentado (27%)",  "rate": 27,   "is_default": False},
    {"code": "AR_EXEMPT",    "label": "Exento",               "rate": 0,    "is_default": False},
]

PORTUGAL_VAT_OPTIONS = [
    {"code": "PT_NORMAL",       "label": "Normal (23%)",     "rate": 23, "is_default": True},
    {"code": "PT_INTERMEDIATE", "label": "Intermedio (13%)", "rate": 13, "is_default": False},
    {"code": "PT_REDUCED",      "label": "Reducido (6%)",    "rate": 6,  "is_default": False},
    {"code": "PT_EXEMPT",       "label": "Isento",           "rate": 0,  "is_default": False},
]

VAT_OPTIONS_BY_ISO2 = {
    "FR": FRANCE_VAT_OPTIONS,
    "US": USA_VAT_OPTIONS,
    "CL": CHILE_VAT_OPTIONS,
    "BR": BRAZIL_VAT_OPTIONS,
    "AR": ARGENTINA_VAT_OPTIONS,
    "PT": PORTUGAL_VAT_OPTIONS,
}


def forwards(apps, schema_editor):
    Country = apps.get_model("core", "Country")
    for code, options in VAT_OPTIONS_BY_ISO2.items():
        Country.objects.filter(code_iso2=code, vat_options=[]).update(
            vat_options=options
        )


def backwards(apps, schema_editor):
    Country = apps.get_model("core", "Country")
    Country.objects.filter(code_iso2__in=list(VAT_OPTIONS_BY_ISO2.keys())).update(
        vat_options=[]
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_country_vat_options"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
