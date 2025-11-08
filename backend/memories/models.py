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
    vector_id = models.CharField(max_length=255, unique=True)

    # For Phase 3: Track extraction status
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
        """Get text for embedding - user message only for Phase 1

        Rationale: Memory search is about finding what the USER said/did/prefers.
        Assistant responses are often acknowledgments that add semantic noise.

        Both messages are still stored for context. Phase 3 atomic extraction
        will pull structured facts from both user and assistant messages.
        """
        return self.user_message
