"""
Entity-Relationship Models for Knowledge Graph Architecture

This module defines the new data models for storing extracted entities and relationships
in a proper knowledge graph structure.
"""

import uuid
from django.db import models


class Entity(models.Model):
    """
    Represents an entity extracted from conversations (User, Person, Place, Concept, etc.)
    """
    ENTITY_TYPE_CHOICES = [
        ('user', 'User'),  # The user themselves
        ('person', 'Person'),  # Other people
        ('place', 'Place'),  # Locations, venues
        ('concept', 'Concept'),  # Abstract concepts (astrophysics, programming)
        ('object', 'Object'),  # Concrete objects (book, phone)
        ('activity', 'Activity'),  # Actions, hobbies (reading, cooking)
        ('preference', 'Preference'),  # Likes, dislikes, preferences
        ('skill', 'Skill'),  # Abilities, competencies
        ('event', 'Event'),  # Specific events, experiences
        ('organization', 'Organization'),  # Companies, institutions
        ('product', 'Product'),  # Software, tools, products
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)  # Which user's knowledge graph this belongs to
    
    # Core entity properties
    name = models.CharField(max_length=255, help_text="Canonical name of the entity")
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPE_CHOICES)
    
    # Graph database identifiers
    graph_node_id = models.CharField(max_length=255, unique=True, help_text="Neo4j node ID")
    
    # Metadata
    aliases = models.JSONField(
        default=list, 
        blank=True,
        help_text="Alternative names/mentions for this entity"
    )
    description = models.TextField(blank=True, help_text="Additional context about the entity")
    confidence = models.FloatField(default=0.5, help_text="Confidence in entity extraction")
    
    # Source tracking
    conversation_chunk_ids = models.JSONField(
        default=list,
        help_text="Conversation chunks that mentioned this entity"
    )
    first_mentioned = models.DateTimeField(auto_now_add=True)
    last_mentioned = models.DateTimeField(auto_now=True)
    mention_count = models.PositiveIntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user_id', 'name', 'entity_type']
        indexes = [
            models.Index(fields=['user_id', 'entity_type']),
            models.Index(fields=['user_id', 'name']),
            models.Index(fields=['graph_node_id']),
        ]
    
    def __str__(self):
        return f"{self.entity_type}: {self.name} (User: {self.user_id})"


class Relationship(models.Model):
    """
    Represents a relationship between two entities
    """
    RELATIONSHIP_TYPE_CHOICES = [
        # Preference relationships
        ('LOVES', 'Loves'),
        ('LIKES', 'Likes'), 
        ('DISLIKES', 'Dislikes'),
        ('HATES', 'Hates'),
        ('PREFERS', 'Prefers'),
        
        # Social relationships
        ('KNOWS', 'Knows'),
        ('WORKS_WITH', 'Works With'),
        ('FRIENDS_WITH', 'Friends With'),
        ('FAMILY_OF', 'Family Of'),
        
        # Professional relationships
        ('WORKS_AT', 'Works At'),
        ('STUDIES_AT', 'Studies At'),
        ('SKILLED_IN', 'Skilled In'),
        ('LEARNING', 'Learning'),
        
        # Location relationships
        ('LIVES_IN', 'Lives In'),
        ('VISITED', 'Visited'),
        ('WANTS_TO_VISIT', 'Wants to Visit'),
        
        # Activity relationships
        ('DOES', 'Does'),
        ('ENJOYS', 'Enjoys'),
        ('PRACTICES', 'Practices'),
        
        # Temporal relationships
        ('USED_TO', 'Used To'),
        ('CURRENTLY', 'Currently'),
        ('PLANS_TO', 'Plans To'),
        
        # Semantic relationships
        ('RELATED_TO', 'Related To'),
        ('PART_OF', 'Part Of'),
        ('SIMILAR_TO', 'Similar To'),
    ]
    
    TEMPORAL_QUALIFIER_CHOICES = [
        ('past', 'Past'),
        ('present', 'Present'), 
        ('future', 'Future'),
        ('ongoing', 'Ongoing'),
        ('temporary', 'Temporary'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    
    # Relationship components
    source_entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name='outgoing_relationships')
    target_entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name='incoming_relationships')
    relationship_type = models.CharField(max_length=20, choices=RELATIONSHIP_TYPE_CHOICES)
    
    # Graph database identifier
    graph_relationship_id = models.CharField(max_length=255, unique=True, help_text="Neo4j relationship ID")
    
    # Relationship properties
    strength = models.FloatField(default=0.5, help_text="Strength of the relationship (0-1)")
    confidence = models.FloatField(default=0.5, help_text="Confidence in relationship extraction")
    temporal_qualifier = models.CharField(
        max_length=20, 
        choices=TEMPORAL_QUALIFIER_CHOICES, 
        default='present',
        help_text="Temporal context of the relationship"
    )
    
    # Source tracking
    conversation_chunk_ids = models.JSONField(
        default=list,
        help_text="Conversation chunks that established this relationship"
    )
    evidence = models.TextField(help_text="Supporting evidence from conversation")
    
    # Temporal tracking
    established_at = models.DateTimeField(auto_now_add=True)
    last_confirmed = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="Whether relationship is currently valid")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['source_entity', 'target_entity', 'relationship_type']
        indexes = [
            models.Index(fields=['user_id', 'relationship_type']),
            models.Index(fields=['source_entity', 'relationship_type']),
            models.Index(fields=['target_entity', 'relationship_type']),
            models.Index(fields=['graph_relationship_id']),
        ]
    
    def __str__(self):
        return f"{self.source_entity.name} -{self.relationship_type}-> {self.target_entity.name}"


class EntityConversationChunk(models.Model):
    """
    Enhanced ConversationChunk model with entity linking
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    content = models.TextField(help_text="Original conversation text chunk")
    vector_id = models.CharField(
        max_length=255, 
        unique=True,
        help_text="Vector database ID for this chunk's embedding"
    )
    timestamp = models.DateTimeField(help_text="When this conversation segment occurred")
    
    # Entity and relationship extraction results
    extracted_entities = models.JSONField(
        default=list,
        help_text="Entity IDs extracted from this chunk"
    )
    extracted_relationships = models.JSONField(
        default=list,
        help_text="Relationship IDs extracted from this chunk"
    )
    
    # Processing metadata
    extraction_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    extraction_metadata = models.JSONField(
        default=dict,
        help_text="Metadata about the extraction process"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user_id", "timestamp"]),
            models.Index(fields=["vector_id"]),
            models.Index(fields=["extraction_status"]),
        ]
    
    def __str__(self):
        return f"EntityConversationChunk {self.id} for user {self.user_id}"
    
    def get_conversation_preview(self, max_length=100):
        """Get a preview of the conversation content"""
        if len(self.content) <= max_length:
            return self.content
        return self.content[:max_length] + "..."