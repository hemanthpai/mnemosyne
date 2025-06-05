from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Initialize Qdrant collection"

    def handle(self, *args, **options):
        try:
            # Import here to catch import errors gracefully
            from memories.vector_service import vector_service

            # Test connection first
            if not vector_service.health_check():
                self.stdout.write(
                    self.style.ERROR(
                        "Cannot connect to Qdrant. Make sure it's running."
                    )  # pylint: disable=no-member
                )
                return

            # Initialize collection
            vector_service._ensure_collection()
            self.stdout.write(
                self.style.SUCCESS("Successfully initialized Qdrant collection")
            )

        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"Import error: {e}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to initialize Qdrant: {e}"))
