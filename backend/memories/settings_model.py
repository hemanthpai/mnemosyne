"""
Settings Model

Stores editable configuration in database that overrides environment variables.
Settings are cached in memory and reloaded when updated.
"""

import logging
from typing import Dict, Any, Optional

from django.db import models
from django.core.cache import cache

logger = logging.getLogger(__name__)

SETTINGS_CACHE_KEY = "mnemosyne_settings"
SETTINGS_CACHE_TIMEOUT = 300  # 5 minutes


class Settings(models.Model):
    """
    Application settings stored in database

    Singleton model - only one instance should exist.
    Settings override environment variables.
    """

    # Singleton key (always 1)
    singleton_key = models.IntegerField(default=1, unique=True, editable=False)

    # Embeddings Configuration
    embeddings_provider = models.CharField(
        max_length=50,
        default='ollama',
        help_text="Provider: ollama, openai, openai_compatible"
    )
    embeddings_endpoint_url = models.CharField(
        max_length=500,
        default='http://host.docker.internal:11434',
        help_text="API endpoint URL"
    )
    embeddings_model = models.CharField(
        max_length=200,
        default='mxbai-embed-large',
        help_text="Model name for embeddings"
    )
    embeddings_api_key = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text="API key (optional for some providers)"
    )
    embeddings_timeout = models.IntegerField(
        default=30,
        help_text="Request timeout in seconds"
    )

    # Generation Configuration (for extraction and relationship building)
    # Separate from embeddings to allow different providers/endpoints
    generation_provider = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Provider for text generation (defaults to embeddings_provider if empty)"
    )
    generation_endpoint_url = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text="API endpoint URL for generation (defaults to embeddings_endpoint_url if empty)"
    )
    generation_model = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Model for text generation (defaults to embeddings_model if empty)"
    )
    generation_api_key = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text="API key for generation (defaults to embeddings_api_key if empty)"
    )
    generation_temperature = models.FloatField(
        default=0.3,
        help_text="Sampling temperature for generation (0.0-1.0)"
    )
    generation_max_tokens = models.IntegerField(
        default=1000,
        help_text="Maximum tokens to generate"
    )
    generation_timeout = models.IntegerField(
        default=60,
        help_text="Request timeout in seconds for generation"
    )

    # Prompt Customization
    # Allow users to customize the prompts used for extraction and relationship building
    extraction_prompt = models.TextField(
        blank=True,
        default='',
        help_text="Custom prompt for atomic note extraction (uses default if empty)"
    )
    relationship_prompt = models.TextField(
        blank=True,
        default='',
        help_text="Custom prompt for relationship building (uses default if empty)"
    )

    # Extraction Configuration
    enable_multipass_extraction = models.BooleanField(
        default=True,
        help_text="Enable multi-pass extraction for higher recall (Pass 1: explicit facts, Pass 2: implied/contextual facts)"
    )

    # Metadata
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200, blank=True, default='system')

    class Meta:
        verbose_name = "Settings"
        verbose_name_plural = "Settings"

    def save(self, *args, **kwargs):
        """Override save to enforce singleton and clear cache"""
        self.singleton_key = 1  # Always 1
        super().save(*args, **kwargs)

        # Clear cache when settings are updated
        cache.delete(SETTINGS_CACHE_KEY)
        logger.info("Settings updated and cache cleared")

    @classmethod
    def get_settings(cls) -> 'Settings':
        """
        Get settings (from cache or database)

        Returns singleton Settings instance, creating it if it doesn't exist.
        Settings are cached for 5 minutes.
        """
        # Try cache first
        settings = cache.get(SETTINGS_CACHE_KEY)
        if settings is not None:
            return settings

        # Get or create settings
        settings, created = cls.objects.get_or_create(singleton_key=1)

        if created:
            logger.info("Created default settings")

        # Cache for 5 minutes
        cache.set(SETTINGS_CACHE_KEY, settings, SETTINGS_CACHE_TIMEOUT)

        return settings

    @classmethod
    def update_settings(cls, **kwargs) -> 'Settings':
        """
        Update settings with provided values

        Args:
            **kwargs: Field names and values to update

        Returns:
            Updated Settings instance
        """
        settings = cls.get_settings()

        # Update fields
        for field, value in kwargs.items():
            if hasattr(settings, field):
                setattr(settings, field, value)

        settings.save()
        return settings

    def to_dict(self, mask_api_key: bool = True) -> Dict[str, Any]:
        """
        Convert settings to dictionary

        Args:
            mask_api_key: If True, mask the API keys for security

        Returns:
            Dictionary of settings
        """
        # Mask embeddings API key
        embeddings_api_key = self.embeddings_api_key
        if mask_api_key and embeddings_api_key:
            if len(embeddings_api_key) > 8:
                embeddings_api_key = f"{embeddings_api_key[:4]}...{embeddings_api_key[-4:]}"
            else:
                embeddings_api_key = "***"

        # Mask generation API key
        generation_api_key = self.generation_api_key
        if mask_api_key and generation_api_key:
            if len(generation_api_key) > 8:
                generation_api_key = f"{generation_api_key[:4]}...{generation_api_key[-4:]}"
            else:
                generation_api_key = "***"

        return {
            # Embeddings configuration
            'embeddings_provider': self.embeddings_provider,
            'embeddings_endpoint_url': self.embeddings_endpoint_url,
            'embeddings_model': self.embeddings_model,
            'embeddings_api_key': embeddings_api_key,
            'embeddings_timeout': self.embeddings_timeout,

            # Generation configuration (with fallbacks)
            'generation_provider': self.generation_provider or self.embeddings_provider,
            'generation_endpoint_url': self.generation_endpoint_url or self.embeddings_endpoint_url,
            'generation_model': self.generation_model or self.embeddings_model,
            'generation_api_key': generation_api_key or embeddings_api_key,
            'generation_temperature': self.generation_temperature,
            'generation_max_tokens': self.generation_max_tokens,
            'generation_timeout': self.generation_timeout,

            # Prompt customization
            'extraction_prompt': self.extraction_prompt,
            'relationship_prompt': self.relationship_prompt,

            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __str__(self):
        return f"Settings ({self.embeddings_provider} - {self.embeddings_model})"
