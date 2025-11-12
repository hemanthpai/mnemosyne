# Generated manually to add A-MEM configuration fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memories', '0009_remove_relationship_prompt'),
    ]

    operations = [
        migrations.AddField(
            model_name='settings',
            name='amem_enrichment_temperature',
            field=models.FloatField(default=0.3, help_text="Temperature for note enrichment LLM calls (lower = more focused)"),
        ),
        migrations.AddField(
            model_name='settings',
            name='amem_enrichment_max_tokens',
            field=models.IntegerField(default=300, help_text="Max tokens for note enrichment responses"),
        ),
        migrations.AddField(
            model_name='settings',
            name='amem_link_generation_temperature',
            field=models.FloatField(default=0.3, help_text="Temperature for link generation LLM calls"),
        ),
        migrations.AddField(
            model_name='settings',
            name='amem_link_generation_max_tokens',
            field=models.IntegerField(default=500, help_text="Max tokens for link generation responses"),
        ),
        migrations.AddField(
            model_name='settings',
            name='amem_link_generation_k',
            field=models.IntegerField(default=10, help_text="Number of nearest neighbors to consider for link generation (k)"),
        ),
        migrations.AddField(
            model_name='settings',
            name='amem_evolution_temperature',
            field=models.FloatField(default=0.3, help_text="Temperature for memory evolution LLM calls"),
        ),
        migrations.AddField(
            model_name='settings',
            name='amem_evolution_max_tokens',
            field=models.IntegerField(default=800, help_text="Max tokens for memory evolution responses"),
        ),
    ]
