"""Añade los Groups de rol que Atlas ya usa y Authent no tenía.

Contexto: los roles viven en `auth_group` (sin permissions asociadas — son
etiquetas que cada producto interpreta). El vocabulario de Atlas había
divergido del de Authent: `consultant`, `specialist`, `distributor` y
`atharix_support` existen en `business.Collaborator.role` de Atlas pero no
como Group aquí. Consecuencia observable: `InternalCollaboratorView` hace
`Group.objects.get(name=role_name)`, no lo encuentra, loguea "creating
collaborator without role" y **crea el colaborador sin rol** — sin error para
quien invita.

`specialist` fue borrado por 0006 como huérfano (entonces no lo usaba nadie).
Vuelve aquí porque Atlas sí lo usa: no es una regresión de 0006.

Aditiva: los groups existentes no se tocan (5 en producción, 7 en algunos
entornos locales que además tienen `employee` y `viewer`).
"""

from django.db import migrations


NEW_GROUPS = (
    "consultant",
    "specialist",
    "distributor",
    "atharix_support",
    # `viewer` existe en las choices de Atlas y en su UI, pero NO como Group en
    # producción (allí solo hay admin/owner/manager/sales/collaborator). Sin
    # esta fila, asignar "Viewer" crearía al colaborador sin rol.
    "viewer",
)


def create_product_role_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in NEW_GROUPS:
        Group.objects.get_or_create(name=name)


def remove_product_role_groups(apps, schema_editor):
    """Reverse fail-closed: nunca cortar el rol a un Collaborator vivo."""
    Group = apps.get_model("auth", "Group")
    Collaborator = apps.get_model("business", "Collaborator")
    qs = Group.objects.filter(name__in=NEW_GROUPS)
    in_use = Collaborator.objects.filter(role__in=qs).exclude(is_deleted=True).count()
    if in_use:
        raise RuntimeError(
            f"No puedo borrar los groups de producto: {in_use} Collaborators "
            f"activos siguen apuntando a alguno de {NEW_GROUPS}. Reasigna antes "
            f"de revertir."
        )
    qs.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("business", "0007_businessappaccess"),
    ]

    operations = [
        migrations.RunPython(create_product_role_groups, remove_product_role_groups),
    ]
