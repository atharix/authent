"""Borra los Groups huérfanos creados por el viejo fixture `groups.json`.

Histórico:
- 2026-03-19: se introdujo `fixtures/groups.json` cargado por `start-web.sh`
  con 5 grupos (`admin`, `admin-business`, `assistant`, `specialist`, `owner`).
- 2026-04-25: migración 0002 hizo `get_or_create("owner","admin","manager",
  "sales","collaborator")`. Coexistían 8 groups; 3 quedaron sin uso real
  (`admin-business`, `assistant`, `specialist` — sin permissions y sin
  Collaborators que los referencien).

Esta migración deja `auth_group` con los 5 nombres canónicos. La eliminación
del fixture (mismo commit) impide que vuelvan a aparecer en arranques
posteriores.

Reverse: recrea los 3 groups vacíos para permitir rollback completo a
v1.1.7 sin estado divergente.
"""

from django.db import migrations


ORPHAN_GROUPS = ("admin-business", "assistant", "specialist")


def remove_orphan_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Collaborator = apps.get_model("business", "Collaborator")
    qs = Group.objects.filter(name__in=ORPHAN_GROUPS)
    # Fail-closed: si por cualquier motivo alguien ya asignó esos roles,
    # mejor abortar la migración que cortar el rol a un Collaborator vivo.
    in_use = (
        Collaborator.objects.filter(role__in=qs).exclude(is_deleted=True).count()
    )
    if in_use:
        raise RuntimeError(
            f"No puedo borrar groups huérfanos: {in_use} Collaborators activos "
            f"siguen apuntando a alguno de {ORPHAN_GROUPS}. Reasigna antes de migrar."
        )
    qs.delete()


def restore_orphan_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ORPHAN_GROUPS:
        Group.objects.get_or_create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ("business", "0005_alter_business_tax_id"),
    ]

    operations = [
        migrations.RunPython(remove_orphan_groups, restore_orphan_groups),
    ]
