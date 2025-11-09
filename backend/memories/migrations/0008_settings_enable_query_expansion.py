# Generated manually for enable_query_expansion setting

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memories', '0007_settings_enable_multipass_extraction'),
    ]

    operations = [
        migrations.AddField(
            model_name='settings',
            name='enable_query_expansion',
            field=models.BooleanField(default=True, help_text='Enable query expansion for better search recall (expands abstract queries into concrete variations)'),
        ),
    ]
