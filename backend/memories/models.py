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

    # Store vector DB reference instead of actual embedding
    vector_id = models.CharField(max_length=255, null=True, blank=True)

    context = models.TextField(
        blank=True, help_text="Context where this memory was mentioned"
    )
    connections = models.JSONField(
        default=list, help_text="Broader topics this memory relates to"
    )
    search_tags = models.JSONField(
        default=list, help_text="Searchable tags for this memory"
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
            models.Index(fields=["vector_id"]),
            models.Index(fields=["user_id", "is_active"]),
            models.Index(fields=["fact_type", "is_active"]),
        ]

    def __str__(self):
        return f"Memory {self.id} for user {self.user_id}"

    def get_all_searchable_text(self):
        """Get all text that should be searchable"""
        searchable_parts = [self.content]
        searchable_parts.extend(self.metadata.get("tags", []))
        searchable_parts.extend(self.connections)
        searchable_parts.extend(self.search_tags)
        if self.context:
            searchable_parts.append(self.context)
        return " ".join(searchable_parts)
