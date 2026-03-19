from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("beat_auth", "0003_add_role_to_user"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="role",
        ),
    ]
