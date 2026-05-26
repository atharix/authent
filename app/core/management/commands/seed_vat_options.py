"""Re-aplica los catálogos `Country.vat_options` para los países conocidos.

Idempotente: solo escribe sobre countries con `vat_options=[]`. Sirve como
salvaguarda en bootstrap (start-web.sh) cuando las migraciones de datos
0002/0003 corrieron antes de cargar los fixtures de countries — caso
típico en entornos fresh donde el orden es `migrate` → `loaddata`.

Lee las constantes directamente de las migraciones existentes para que
el seed nunca se desincronice con la fuente canónica. Si se agregan más
países en una migración nueva, basta con incluir su nombre en `MIGRATIONS`.
"""

from __future__ import annotations

import importlib

from django.core.management.base import BaseCommand

from core.models import Country


MIGRATIONS = (
    "core.migrations.0002_country_vat_options",
    "core.migrations.0003_extended_vat_options",
)


class Command(BaseCommand):
    help = "Re-aplica vat_options por país de forma idempotente (solo donde está vacío)."

    def handle(self, *args, **options):
        total = 0
        for migname in MIGRATIONS:
            mod = importlib.import_module(migname)
            mapping = getattr(mod, "VAT_OPTIONS_BY_ISO2", None)
            if mapping is None:
                # 0002 tiene SPAIN_VAT_OPTIONS y ECUADOR_VAT_OPTIONS sueltos.
                mapping = {}
                if hasattr(mod, "SPAIN_VAT_OPTIONS"):
                    mapping["ES"] = mod.SPAIN_VAT_OPTIONS
                if hasattr(mod, "ECUADOR_VAT_OPTIONS"):
                    mapping["EC"] = mod.ECUADOR_VAT_OPTIONS
            for code, opts in mapping.items():
                updated = Country.objects.filter(
                    code_iso2=code, vat_options=[]
                ).update(vat_options=opts)
                if updated:
                    self.stdout.write(f"  {code}: poblado ({len(opts)} opciones)")
                total += updated
        if total == 0:
            self.stdout.write("Sin cambios — todos los países ya tienen vat_options.")
        else:
            self.stdout.write(self.style.SUCCESS(f"vat_options actualizados en {total} países."))
