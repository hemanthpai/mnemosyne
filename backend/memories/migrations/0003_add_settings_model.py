# Generated manually for Settings model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memories', '0002_phase3_atomic_notes'),
    ]

    operations = [
        migrations.CreateModel(
            name='Settings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('singleton_key', models.IntegerField(default=1, editable=False, unique=True)),
                ('embeddings_provider', models.CharField(default='ollama', help_text='Provider: ollama, openai, openai_compatible', max_length=50)),
                ('embeddings_endpoint_url', models.CharField(default='http://host.docker.internal:11434', help_text='API endpoint URL', max_length=500)),
                ('embeddings_model', models.CharField(default='mxbai-embed-large', help_text='Model name for embeddings', max_length=200)),
                ('embeddings_api_key', models.CharField(blank=True, default='', help_text='API key (optional for some providers)', max_length=500)),
                ('embeddings_timeout', models.IntegerField(default=30, help_text='Request timeout in seconds')),
                ('generation_model', models.CharField(blank=True, default='', help_text='Model for text generation (defaults to embeddings_model if empty)', max_length=200)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.CharField(blank=True, default='system', max_length=200)),
            ],
            options={
                'verbose_name': 'Settings',
                'verbose_name_plural': 'Settings',
            },
        ),
    ]
