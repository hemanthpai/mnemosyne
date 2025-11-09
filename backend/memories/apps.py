from django.apps import AppConfig


class MemoriesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "memories"

    # No signals needed
    # def ready(self):
    #     # Import signal handlers
    #     import memories.signals  # noqa: F401
