# Migration for query rewriting setting

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memories', '0014_add_reranking_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='settings',
            name='enable_query_rewriting',
            field=models.BooleanField(default=True, help_text='Enable context-aware query rewriting for more targeted search results'),
        ),
    ]
