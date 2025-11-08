# Generated migration for prompt customization fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memories', '0005_add_generation_config_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='settings',
            name='extraction_prompt',
            field=models.TextField(blank=True, default='', help_text='Custom prompt for atomic note extraction (uses default if empty)'),
        ),
        migrations.AddField(
            model_name='settings',
            name='relationship_prompt',
            field=models.TextField(blank=True, default='', help_text='Custom prompt for relationship building (uses default if empty)'),
        ),
    ]
