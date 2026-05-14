# Generated manually

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("business", "0002_tax_id_optional_owner_group"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Industry",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        help_text="Unique identifier for this record",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, db_index=True, verbose_name="Created at"
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, db_index=True, verbose_name="Updated at"
                    ),
                ),
                (
                    "is_deleted",
                    models.BooleanField(
                        db_index=True, default=False, verbose_name="Is deleted"
                    ),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, db_index=True, null=True, verbose_name="Deleted at"
                    ),
                ),
                (
                    "version",
                    models.PositiveIntegerField(
                        default=1,
                        help_text="Record version for optimistic locking",
                        verbose_name="Version",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        help_text="Optional notes about changes",
                        verbose_name="Notes",
                    ),
                ),
                ("code", models.CharField(max_length=20, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True, default="")),
                ("icon", models.CharField(blank=True, default="", max_length=50)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("name_pt", models.CharField(blank=True, default="", max_length=100)),
                ("name_en", models.CharField(blank=True, default="", max_length=100)),
                ("name_fr", models.CharField(blank=True, default="", max_length=100)),
                ("name_it", models.CharField(blank=True, default="", max_length=100)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="User who created this record",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created by",
                    ),
                ),
                (
                    "deleted_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="User who deleted this record",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_deleted",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Deleted by",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="User who last updated this record",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_updated",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Updated by",
                    ),
                ),
            ],
            options={
                "verbose_name": "Industry",
                "verbose_name_plural": "Industries",
                "db_table": "industry",
                "ordering": ["sort_order", "name"],
            },
        ),
    ]
