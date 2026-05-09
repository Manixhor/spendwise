from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('login', '0015_savingsgoal_current_month_auto_allocation'),
    ]

    operations = [
        migrations.CreateModel(
            name='PageView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.CharField(max_length=255)),
                ('view_count', models.PositiveIntegerField(default=0)),
                ('last_viewed', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-last_viewed'],
            },
        ),
    ]