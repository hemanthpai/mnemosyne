import uuid

from django.db import models


class Memory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField()
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    # Store vector DB reference instead of actual embedding
    vector_id = models.CharField(max_length=255, null=True, blank=True)


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user_id"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["vector_id"]),
        ]

    def __str__(self):
        return f"Memory {self.id} for user {self.user_id}"

    def get_all_searchable_text(self):
        """Get all text that should be searchable"""
        searchable_parts = [self.content]
        
        # Add tags from metadata
        searchable_parts.extend(self.metadata.get("tags", []))
        
        # Add context from metadata if present
        context = self.metadata.get("context", "")
        if context:
            searchable_parts.append(context)
            
        return " ".join(searchable_parts)
