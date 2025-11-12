# Manual migration for reranking settings

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memories', '0013_alter_atomicnote_contextual_description_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='settings',
            name='enable_reranking',
            field=models.BooleanField(default=True, help_text='Enable cross-encoder reranking for improved search precision'),
        ),
        migrations.AddField(
            model_name='settings',
            name='reranking_provider',
            field=models.CharField(default='ollama', help_text='Provider: remote (GPU server endpoint), ollama (LLM-based), or sentence_transformers (local cross-encoder)', max_length=50),
        ),
        migrations.AddField(
            model_name='settings',
            name='reranking_endpoint_url',
            field=models.CharField(default='http://your-gpu-server:8081', help_text='Endpoint URL for remote reranking server (used with \'remote\' provider)', max_length=500),
        ),
        migrations.AddField(
            model_name='settings',
            name='reranking_model_name',
            field=models.CharField(default='BAAI/bge-reranker-base', help_text='Model name (for remote: reference only; for sentence_transformers: model to load)', max_length=200),
        ),
        migrations.AddField(
            model_name='settings',
            name='reranking_batch_size',
            field=models.IntegerField(default=16, help_text='Batch size for reranking (lower = less memory, higher = faster)'),
        ),
        migrations.AddField(
            model_name='settings',
            name='reranking_device',
            field=models.CharField(default='cpu', help_text='Device: cpu, cuda (if GPU available), or auto (auto-detect)', max_length=20),
        ),
        migrations.AddField(
            model_name='settings',
            name='ollama_reranking_base_url',
            field=models.CharField(default='http://host.docker.internal:11434', help_text='Ollama API endpoint URL for reranking', max_length=500),
        ),
        migrations.AddField(
            model_name='settings',
            name='ollama_reranking_model',
            field=models.CharField(default='llama3.2:3b', help_text='Ollama model for LLM-based reranking (e.g., llama3.2:3b, qwen2.5:3b, gemma2:2b)', max_length=200),
        ),
        migrations.AddField(
            model_name='settings',
            name='ollama_reranking_temperature',
            field=models.FloatField(default=0.0, help_text='Temperature for Ollama reranking (0.0 = deterministic scoring)'),
        ),
        migrations.AddField(
            model_name='settings',
            name='reranking_candidate_multiplier',
            field=models.IntegerField(default=3, help_text='Retrieve N× more candidates before reranking (e.g., 3 = retrieve 30 to rerank top 10)'),
        ),
    ]
