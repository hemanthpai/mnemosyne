# Generated manually for Phase 3: A-Mem Atomic Notes & Graph

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('memories', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AtomicNote',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('user_id', models.UUIDField(db_index=True)),
                ('content', models.TextField()),
                ('note_type', models.CharField(db_index=True, max_length=100)),
                ('context', models.TextField(blank=True)),
                ('confidence', models.FloatField(default=1.0)),
                ('importance_score', models.FloatField(db_index=True, default=1.0)),
                ('vector_id', models.CharField(max_length=255, unique=True)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-importance_score', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='NoteRelationship',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('relationship_type', models.CharField(choices=[('related_to', 'Related To'), ('contradicts', 'Contradicts'), ('refines', 'Refines'), ('context_for', 'Context For'), ('follows_from', 'Follows From')], db_index=True, default='related_to', max_length=50)),
                ('strength', models.FloatField(default=1.0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('from_note', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outgoing_relationships', to='memories.atomicnote')),
                ('to_note', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='incoming_relationships', to='memories.atomicnote')),
            ],
        ),
        migrations.AddField(
            model_name='atomicnote',
            name='source_turn',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='extracted_notes', to='memories.conversationturn'),
        ),
        migrations.AddIndex(
            model_name='atomicnote',
            index=models.Index(fields=['user_id', '-importance_score'], name='memories_at_user_id_18095d_idx'),
        ),
        migrations.AddIndex(
            model_name='atomicnote',
            index=models.Index(fields=['user_id', 'note_type'], name='memories_at_user_id_eb0ec9_idx'),
        ),
        migrations.AddIndex(
            model_name='atomicnote',
            index=models.Index(fields=['user_id', '-created_at'], name='memories_at_user_id_a8c667_idx'),
        ),
        migrations.AddIndex(
            model_name='noterelationship',
            index=models.Index(fields=['from_note', 'relationship_type'], name='memories_no_from_no_eea815_idx'),
        ),
        migrations.AddIndex(
            model_name='noterelationship',
            index=models.Index(fields=['to_note', 'relationship_type'], name='memories_no_to_note_5e86c9_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='noterelationship',
            unique_together={('from_note', 'to_note', 'relationship_type')},
        ),
    ]
