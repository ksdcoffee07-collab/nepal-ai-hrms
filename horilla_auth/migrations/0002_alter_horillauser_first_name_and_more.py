from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("horilla_auth", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="horillauser",
            name="first_name",
            field=models.CharField(
                blank=True, max_length=200, verbose_name="first name"
            ),
        ),
        migrations.AlterField(
            model_name="horillauser",
            name="last_name",
            field=models.CharField(
                blank=True, max_length=200, verbose_name="last name"
            ),
        ),
    ]
