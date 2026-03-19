from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("beat_auth", "0002_rename_user_sessions_user_active_idx_user_sessio_user_id_bb1b83_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="role",
            field=models.CharField(
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
    ]
