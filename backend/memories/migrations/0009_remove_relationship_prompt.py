# Generated manually to remove dead relationship_prompt field

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('memories', '0008_settings_enable_query_expansion'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='settings',
            name='relationship_prompt',
        ),
    ]
