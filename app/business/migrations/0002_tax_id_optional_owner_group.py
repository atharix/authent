"""Allow tax_id to be null/blank and ensure default Groups exist."""

from django.db import migrations, models


DEFAULT_GROUPS = ("owner", "admin", "manager", "sales", "collaborator")


def create_default_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in DEFAULT_GROUPS:
        Group.objects.get_or_create(name=name)


def remove_default_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=DEFAULT_GROUPS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("business", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="business",
            name="tax_id",
            field=models.CharField(
                blank=True, max_length=50, null=True, unique=True
            ),
        ),
        migrations.RunPython(create_default_groups, remove_default_groups),
    ]
