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

    # Phase 3: Generation Model (for extraction and relationship building)
    generation_model = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Model for text generation (defaults to embeddings_model if empty)"
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
            mask_api_key: If True, mask the API key for security

        Returns:
            Dictionary of settings
        """
        api_key = self.embeddings_api_key
        if mask_api_key and api_key:
            # Show first 4 and last 4 characters
            if len(api_key) > 8:
                api_key = f"{api_key[:4]}...{api_key[-4:]}"
            else:
                api_key = "***"

        return {
            'embeddings_provider': self.embeddings_provider,
            'embeddings_endpoint_url': self.embeddings_endpoint_url,
            'embeddings_model': self.embeddings_model,
            'embeddings_api_key': api_key,
            'embeddings_timeout': self.embeddings_timeout,
            'generation_model': self.generation_model or self.embeddings_model,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __str__(self):
        return f"Settings ({self.embeddings_provider} - {self.embeddings_model})"
