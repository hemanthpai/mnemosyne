import uuid
from django.db import models


class ConversationTurn(models.Model):
    """Stores raw conversation turns with embeddings for fast retrieval"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    session_id = models.CharField(max_length=255, db_index=True)
    turn_number = models.IntegerField()

    # Raw conversation data
    user_message = models.TextField()
    assistant_message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # Vector storage
    vector_id = models.CharField(max_length=255, unique=True, null=True, blank=True)

    # Track extraction status
    extracted = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user_id', '-timestamp']),
            models.Index(fields=['session_id', 'turn_number']),
        ]
        unique_together = [['session_id', 'turn_number']]

    def __str__(self):
        return f"Turn {self.turn_number} in session {self.session_id[:8]}"

    def get_full_text(self):
        """Get text for embedding - user message only

        Rationale: Memory search is about finding what the USER said/did/prefers.
        Assistant responses are often acknowledgments that add semantic noise.

        Both messages are still stored for context. Atomic extraction
        will pull structured facts from both user and assistant messages.
        """
        return self.user_message


# =============================================================================
# A-Mem Atomic Notes & Knowledge Graph
# =============================================================================


class AtomicNote(models.Model):
    """
    Atomic memory notes (A-Mem architecture)

    Stores individual atomic facts extracted from conversations.
    Each note represents a single, granular piece of knowledge with
    context and relationships to other notes.

    Examples:
    - "prefers dark mode" (preference:ui)
    - "uses vim keybindings" (preference:editor)
    - "experienced Python developer" (skill:programming)
    - "lives in San Francisco" (personal:location)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)

    # The atomic fact (single, granular piece of knowledge)
    content = models.TextField()

    # Structured type taxonomy: category:subcategory
    # Examples: preference:ui, skill:programming, interest:topic, relationship:person
    note_type = models.CharField(max_length=100, db_index=True)

    # Context about when/why/how this was mentioned
    context = models.TextField(blank=True)

    # Provenance - which conversation turn this came from
    source_turn = models.ForeignKey(
        ConversationTurn,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='extracted_notes'
    )

    # Confidence score from extraction (0.0-1.0)
    confidence = models.FloatField(default=1.0)

    # Computed importance score (based on frequency, recency, connections)
    importance_score = models.FloatField(default=1.0, db_index=True)

    # Vector storage for semantic search
    vector_id = models.CharField(max_length=255, unique=True)

    # Tags for filtering and organization
    tags = models.JSONField(default=list, blank=True)

    # =============================================================================
    # A-MEM Enhancement Fields (Section 3.1)
    # =============================================================================

    # LLM-generated keywords (Ki) - 3-5 specific terms capturing key concepts
    keywords = models.JSONField(default=list, blank=True)

    # LLM-generated tags (Gi) - 3+ categorical labels for classification
    llm_tags = models.JSONField(default=list, blank=True)

    # LLM-generated contextual description (Xi) - Rich semantic summary
    contextual_description = models.TextField(blank=True)

    # Track if note has been enriched with A-MEM attributes
    is_amem_enriched = models.BooleanField(default=False, db_index=True)

    # Lifecycle timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-importance_score', '-created_at']
        indexes = [
            models.Index(fields=['user_id', '-importance_score']),
            models.Index(fields=['user_id', 'note_type']),
            models.Index(fields=['user_id', '-created_at']),
        ]

    def __str__(self):
        return f"{self.note_type}: {self.content[:50]}"


class NoteRelationship(models.Model):
    """
    Relationships between atomic notes

    Creates a knowledge graph by linking related notes together.
    Enables graph traversal to find related context.

    Relationship types:
    - related_to: General connection
    - contradicts: Notes that conflict
    - refines: One note adds detail to another
    - context_for: Provides context for another note
    - follows_from: Temporal or causal relationship
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # The two notes being connected
    from_note = models.ForeignKey(
        AtomicNote,
        on_delete=models.CASCADE,
        related_name='outgoing_relationships'
    )
    to_note = models.ForeignKey(
        AtomicNote,
        on_delete=models.CASCADE,
        related_name='incoming_relationships'
    )

    # Type of relationship
    relationship_type = models.CharField(
        max_length=50,
        db_index=True,
        choices=[
            ('related_to', 'Related To'),
            ('contradicts', 'Contradicts'),
            ('refines', 'Refines'),
            ('context_for', 'Context For'),
            ('follows_from', 'Follows From'),
        ],
        default='related_to'
    )

    # Strength of relationship (0.0-1.0)
    strength = models.FloatField(default=1.0)

    # When this relationship was discovered/created
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevent duplicate relationships
        unique_together = [['from_note', 'to_note', 'relationship_type']]
        indexes = [
            models.Index(fields=['from_note', 'relationship_type']),
            models.Index(fields=['to_note', 'relationship_type']),
        ]

    def __str__(self):
        return f"{self.from_note.content[:30]} -{self.relationship_type}-> {self.to_note.content[:30]}"


# =============================================================================
# Settings Model
# =============================================================================

from .settings_model import Settings  # noqa: E402
