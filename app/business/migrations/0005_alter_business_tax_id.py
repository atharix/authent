from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("business", "0004_business_fiscal_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="business",
            name="tax_id",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
