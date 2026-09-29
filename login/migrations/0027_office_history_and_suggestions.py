from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("login", "0026_alter_officeentry_direction_alter_officeentry_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="officeentry",
            name="deleted_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.CreateModel(
            name="OfficeHiddenSuggestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name_key", models.CharField(max_length=240)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="office_hidden_suggestions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("user", "name_key"), name="office_hidden_name_per_user")],
            },
        ),
    ]
