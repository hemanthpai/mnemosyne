# Final schema migration that matches current database state

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("memories", "0002_remove_memory_embedding_memory_vector_id_and_more"),
    ]

    operations = [
        # Database schema already matches the model exactly
        # This migration exists to sync Django's migration state with reality
        migrations.RunSQL(
            sql="SELECT 1",  # No-op SQL
            reverse_sql="SELECT 1",
        ),
    ]