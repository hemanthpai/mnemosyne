# Migration for hybrid search setting

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memories', '0015_add_query_rewriting_setting'),
    ]

    operations = [
        migrations.AddField(
            model_name='settings',
            name='enable_hybrid_search',
            field=models.BooleanField(default=True, help_text='Enable hybrid search (BM25 + Vector) using Reciprocal Rank Fusion for improved recall'),
        ),
    ]
