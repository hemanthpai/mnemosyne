import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from settings_app.models import LLMSettings

logger = logging.getLogger(__name__)


@receiver(post_save, sender=LLMSettings)
def refresh_services_on_settings_change(sender, instance, created, **kwargs):
    """Refresh all services when LLMSettings are updated"""
    try:
        from .llm_service import llm_service

        action = "created" if created else "updated"
        logger.info("LLM settings %s, refreshing all services...", action)

        # Skip refresh if we're just updating graph build status to avoid loops
        if hasattr(instance, '_skip_signals'):
            logger.info("Skipping service refresh for graph status update")
            return

        # Refresh LLM service
        llm_service.refresh_settings()

        logger.info("Successfully refreshed all services")
    except Exception as e:
        logger.error("Failed to refresh services after settings change: %s", e)


@receiver(post_delete, sender=LLMSettings)
def handle_llm_settings_deletion(sender, instance, **kwargs):
    """Handle when LLM settings are deleted"""
    logger.warning("LLM settings were deleted - services may not function properly")
