# Generated migration for beat_auth app (users)

import uuid

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("apps", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                (
                    "last_login",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="last login"
                    ),
                ),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        max_length=254,
                        unique=True,
                        verbose_name="Email address",
                    ),
                ),
                (
                    "first_name",
                    models.CharField(max_length=150, verbose_name="First name"),
                ),
                (
                    "last_name",
                    models.CharField(max_length=150, verbose_name="Last name"),
                ),
                (
                    "birth_date",
                    models.DateField(blank=True, null=True, verbose_name="Birth date"),
                ),
                (
                    "phone_number",
                    models.CharField(
                        blank=True,
                        max_length=17,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Phone number must be entered in format: '+999999999'. Up to 15 digits allowed.",
                                regex="^\\+?1?\\d{9,15}$",
                            )
                        ],
                        verbose_name="Phone number",
                    ),
                ),
                (
                    "gender",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("M", "Male"),
                            ("F", "Female"),
                            ("O", "Other"),
                            ("P", "Prefer not to say"),
                        ],
                        max_length=1,
                        verbose_name="Gender",
                    ),
                ),
                (
                    "avatar",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="avatars/",
                        verbose_name="Avatar",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="Active")),
                (
                    "is_staff",
                    models.BooleanField(default=False, verbose_name="Staff status"),
                ),
                (
                    "date_joined",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="Date joined"
                    ),
                ),
                (
                    "email_verified",
                    models.BooleanField(default=False, verbose_name="Email verified"),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("user", "User"),
                            ("admin", "Admin"),
                            ("moderator", "Moderator"),
                        ],
                        default="user",
                        max_length=20,
                        verbose_name="Role",
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to.",
                        related_name="beat_user_set",
                        related_query_name="beat_user",
                        to="auth.group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="beat_user_set",
                        related_query_name="beat_user",
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "verbose_name": "User",
                "verbose_name_plural": "Users",
                "db_table": "beat_auth_user",
            },
        ),
        migrations.CreateModel(
            name="PasswordReset",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="password_resets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "hash_token",
                    models.CharField(max_length=64, verbose_name="Hash token"),
                ),
                ("pin", models.CharField(max_length=4, verbose_name="PIN")),
                ("is_active", models.BooleanField(default=True, verbose_name="Active")),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created at"),
                ),
                (
                    "expires_at",
                    models.DateTimeField(verbose_name="Expires at"),
                ),
                (
                    "used_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Used at"),
                ),
            ],
            options={
                "verbose_name": "Password Reset",
                "verbose_name_plural": "Password Resets",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="UserSession",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "api_key",
                    models.ForeignKey(
                        blank=True,
                        help_text="API key used to create this session",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sessions",
                        to="apps.apikey",
                        verbose_name="API Key",
                    ),
                ),
                (
                    "jti",
                    models.CharField(
                        help_text="Unique JWT token identifier",
                        max_length=255,
                        unique=True,
                        verbose_name="JWT ID",
                    ),
                ),
                (
                    "refresh_token_hash",
                    models.CharField(
                        help_text="Hash of refresh token for revocation",
                        max_length=255,
                    ),
                ),
                (
                    "device_name",
                    models.CharField(
                        blank=True,
                        help_text="User-friendly device name",
                        max_length=100,
                    ),
                ),
                (
                    "device_type",
                    models.CharField(
                        choices=[
                            ("mobile", "Mobile"),
                            ("tablet", "Tablet"),
                            ("desktop", "Desktop"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=20,
                    ),
                ),
                (
                    "os_name",
                    models.CharField(blank=True, max_length=50, verbose_name="OS Name"),
                ),
                (
                    "os_version",
                    models.CharField(
                        blank=True, max_length=50, verbose_name="OS Version"
                    ),
                ),
                ("browser", models.CharField(blank=True, max_length=50)),
                ("browser_version", models.CharField(blank=True, max_length=50)),
                (
                    "user_agent",
                    models.TextField(help_text="Full User-Agent string"),
                ),
                ("ip_address", models.GenericIPAddressField()),
                ("country", models.CharField(blank=True, max_length=100)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_activity", models.DateTimeField(auto_now=True)),
                (
                    "expires_at",
                    models.DateTimeField(help_text="When the access token expires"),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "fcm_token",
                    models.CharField(
                        blank=True,
                        max_length=500,
                        null=True,
                        verbose_name="FCM Token",
                    ),
                ),
                (
                    "fcm_token_updated_at",
                    models.DateTimeField(blank=True, null=True),
                ),
            ],
            options={
                "verbose_name": "User Session",
                "verbose_name_plural": "User Sessions",
                "db_table": "user_sessions",
                "ordering": ["-last_activity"],
            },
        ),
        migrations.AddIndex(
            model_name="usersession",
            index=models.Index(
                fields=["user", "is_active"], name="user_sessions_user_active_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="usersession",
            index=models.Index(fields=["jti"], name="user_sessions_jti_idx"),
        ),
        migrations.AddIndex(
            model_name="usersession",
            index=models.Index(
                fields=["last_activity"], name="user_sessions_last_activity_idx"
            ),
        ),
    ]
