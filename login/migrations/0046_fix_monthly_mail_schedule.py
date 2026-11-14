from datetime import time

from django.db import migrations


def fix_schedule(apps, schema_editor):
    setting = apps.get_model('login', 'MonthlyAnalysisMailSetting')
    setting.objects.filter(pk=1).update(enabled=True, send_day=8, send_time=time(0))


class Migration(migrations.Migration):
    dependencies = [('login', '0045_dailyallowancepushdelivery')]
    operations = [migrations.RunPython(fix_schedule, migrations.RunPython.noop)]
