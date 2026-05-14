from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("business", "0003_industry"),
        ("core", "0002_country_vat_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="fiscal_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Full legal/fiscal name as it appears on invoices",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="business",
            name="registration_number",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Mercantile / commercial registry number (optional)",
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name="business",
            name="currency",
            field=models.CharField(
                blank=True,
                default="",
                help_text="ISO 4217 currency code (e.g. EUR, USD). Defaults to country.currency_code",
                max_length=3,
            ),
        ),
        migrations.AddField(
            model_name="business",
            name="vat_regime",
            field=models.CharField(
                blank=True,
                default="",
                help_text="VAT regime code chosen from country.vat_options",
                max_length=50,
            ),
        ),
    ]
