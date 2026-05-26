"""Smoke tests del catálogo VAT por país.

Garantiza que después de aplicar las migraciones 0002 y 0003 los países
objetivo tienen un catálogo con shape válido y exactamente una opción
marcada como `is_default`. No valida tasas específicas — esas pueden
cambiar y se cubren en la migración correspondiente.
"""

from __future__ import annotations

import pytest

from core.models import Country


TARGET_COUNTRIES = ("ES", "EC", "FR", "US", "CL", "BR", "AR", "PT")


@pytest.mark.django_db
@pytest.mark.parametrize("code", TARGET_COUNTRIES)
def test_country_has_vat_options_seeded(code):
    country = Country.objects.filter(code_iso2=code).first()
    assert country is not None, f"País {code} no existe en fixtures"
    assert country.vat_options, f"{code} tiene vat_options vacío"


@pytest.mark.django_db
@pytest.mark.parametrize("code", TARGET_COUNTRIES)
def test_country_vat_options_shape(code):
    country = Country.objects.get(code_iso2=code)
    for opt in country.vat_options:
        for key in ("code", "label", "rate"):
            assert key in opt, f"{code}: opción mal-formada (falta {key}): {opt}"
        assert opt["code"].startswith(f"{code}_"), (
            f"{code}: el campo 'code' debe tener prefijo país (got {opt['code']})"
        )
        assert isinstance(opt["rate"], (int, float)), (
            f"{code}: rate debe ser numérico (got {type(opt['rate']).__name__})"
        )


@pytest.mark.django_db
@pytest.mark.parametrize("code", TARGET_COUNTRIES)
def test_country_has_exactly_one_default(code):
    country = Country.objects.get(code_iso2=code)
    defaults = [o for o in country.vat_options if o.get("is_default")]
    assert len(defaults) == 1, (
        f"{code} debe tener exactamente un is_default (got {len(defaults)})"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("code", TARGET_COUNTRIES)
def test_country_vat_codes_unique(code):
    country = Country.objects.get(code_iso2=code)
    codes = [o["code"] for o in country.vat_options]
    assert len(codes) == len(set(codes)), (
        f"{code}: códigos VAT duplicados {codes}"
    )
