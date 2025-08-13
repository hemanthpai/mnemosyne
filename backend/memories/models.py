import uuid

from django.db import models


class Memory(models.Model):
    FACT_TYPE_CHOICES = [
        ('mutable', 'Mutable'),      # Can change over time (preferences, location, status)
        ('immutable', 'Immutable'),  # Fixed facts (birthdate, past events)
        ('temporal', 'Temporal'),    # Time-bound facts (current job, current location)
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField()
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    # Links to conversation chunks in Vector DB that led to this memory
    conversation_chunk_ids = models.JSONField(
        default=list, 
        help_text="List of ConversationChunk IDs that led to this memory extraction"
    )
    
    # New fields for conflict resolution and temporal tracking
    supersedes = models.ForeignKey(
        'self', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='superseded_by',
        help_text="Memory that this one replaces/updates"
    )
    fact_type = models.CharField(
        max_length=20, 
        choices=FACT_TYPE_CHOICES, 
        default='mutable',
        help_text="Type of fact - whether it can change over time"
    )
    original_confidence = models.FloatField(
        default=0.5,
        help_text="Original confidence score when memory was created"
    )
    temporal_confidence = models.FloatField(
        default=0.5,
        help_text="Current confidence after temporal decay"
    )
    last_validated = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this memory was validated or confirmed"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this memory is currently active (not superseded)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user_id"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["user_id", "is_active"]),
            models.Index(fields=["fact_type", "is_active"]),
        ]

    def __str__(self):
        return f"Memory {self.id} for user {self.user_id}"

    def get_memory_text_for_graph(self):
        """Get memory content and tags for graph storage - vector search now handled by conversation chunks"""
        searchable_parts = [self.content]
        searchable_parts.extend(self.metadata.get("tags", []))
        return " ".join(searchable_parts)
    
    def get_standardized_metadata(self):
        """
        Get standardized metadata structure focused on graph construction and memory reliability.
        Returns metadata in the new simplified format for graph-enhanced architecture.
        """
        return {
            "inference_level": self.metadata.get("inference_level", "stated"),
            "evidence": self.metadata.get("evidence", ""),
            "extraction_timestamp": self.metadata.get("extraction_timestamp", self.created_at.isoformat()),
            "tags": self.metadata.get("tags", []),
            "entity_type": self.metadata.get("entity_type", "general"),  # person, place, preference, skill, fact, etc.
            "relationship_hints": self.metadata.get("relationship_hints", []),  # suggested relationship types
            "model_used": self.metadata.get("model_used", "unknown"),
            "extraction_source": self.metadata.get("extraction_source", "conversation")
        }
    
    def update_metadata_to_standard_format(self):
        """
        Update metadata to use the new standardized format, removing redundant fields.
        This helps migration from old to new format.
        """
        # Preserve essential fields, remove redundant ones
        new_metadata = self.get_standardized_metadata()
        
        # Remove old fields that are now handled differently
        old_fields_to_remove = ["context", "connections", "confidence"]
        for field in old_fields_to_remove:
            new_metadata.pop(field, None)
            
        # Add conversation chunk linkage if available
        if hasattr(self, 'conversation_chunk_ids') and self.conversation_chunk_ids:
            new_metadata["source_chunk_ids"] = self.conversation_chunk_ids
            
        self.metadata = new_metadata
        return new_metadata


class ConversationChunk(models.Model):
    """
    Stores original conversation text chunks for vector database storage and semantic search.
    Each chunk represents a segment of user conversation that led to memory extraction.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField()
    content = models.TextField(help_text="Original conversation text chunk")
    vector_id = models.CharField(
        max_length=255, 
        unique=True,
        help_text="Vector database ID for this chunk's embedding"
    )
    timestamp = models.DateTimeField(
        help_text="When this conversation segment occurred"
    )
    metadata = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Additional context: source info, session data, etc."
    )
    extracted_memory_ids = models.JSONField(
        default=list,
        help_text="List of Memory IDs that were extracted from this chunk"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user_id"]),
            models.Index(fields=["timestamp"]),
            models.Index(fields=["vector_id"]),
            models.Index(fields=["user_id", "timestamp"]),
        ]

    def __str__(self):
        return f"ConversationChunk {self.id} for user {self.user_id}"

    def get_conversation_preview(self, max_length=100):
        """Get a preview of the conversation content"""
        if len(self.content) <= max_length:
            return self.content
        return self.content[:max_length] + "..."
