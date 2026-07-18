"""Puebla `Application.code` a partir del `name` para las Applications existentes.

Deja el acceso por producto listo para comparar por `code` (metis/atlas/delta) en vez
de por `name`. No activa `enforce_app_access` (eso es una decisión de rollout que exige
antes el backfill de `BusinessAppAccess`).
"""

from django.db import migrations
from django.utils.text import slugify


def populate_code(apps, schema_editor):
    Application = apps.get_model("apps", "Application")
    seen = set()
    for app in Application.objects.all():
        if app.code:
            seen.add(app.code)
            continue
        base = slugify(app.name) or f"app-{str(app.pk)}"
        code = base
        i = 2
        while code in seen:
            code = f"{base}-{i}"
            i += 1
        seen.add(code)
        app.code = code
        app.save(update_fields=["code"])


def reverse_noop(apps, schema_editor):
    # No revertimos: dejar `code` no rompe nada.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("apps", "0002_application_code_application_enforce_app_access"),
    ]

    operations = [
        migrations.RunPython(populate_code, reverse_noop),
    ]
