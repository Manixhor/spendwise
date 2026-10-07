# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('login', '0027_office_history_and_suggestions'),
    ]

    operations = [
        migrations.AddField(
            model_name='monthlyanalysismailsetting',
            name='send_day_8_enabled',
            field=models.BooleanField(default=False, help_text='Send on 8th of the month at 00:00 IST'),
        ),
    ]
