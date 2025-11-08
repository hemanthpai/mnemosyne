# Generated manually for separate generation configuration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memories', '0004_rename_memories_co_user_id_4e8a8c_idx_memories_co_user_id_7f2a82_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='settings',
            name='generation_provider',
            field=models.CharField(blank=True, default='', help_text='Provider for text generation (defaults to embeddings_provider if empty)', max_length=50),
        ),
        migrations.AddField(
            model_name='settings',
            name='generation_endpoint_url',
            field=models.CharField(blank=True, default='', help_text='API endpoint URL for generation (defaults to embeddings_endpoint_url if empty)', max_length=500),
        ),
        migrations.AddField(
            model_name='settings',
            name='generation_api_key',
            field=models.CharField(blank=True, default='', help_text='API key for generation (defaults to embeddings_api_key if empty)', max_length=500),
        ),
        migrations.AddField(
            model_name='settings',
            name='generation_temperature',
            field=models.FloatField(default=0.3, help_text='Sampling temperature for generation (0.0-1.0)'),
        ),
        migrations.AddField(
            model_name='settings',
            name='generation_max_tokens',
            field=models.IntegerField(default=1000, help_text='Maximum tokens to generate'),
        ),
        migrations.AddField(
            model_name='settings',
            name='generation_timeout',
            field=models.IntegerField(default=60, help_text='Request timeout in seconds for generation'),
        ),
    ]
