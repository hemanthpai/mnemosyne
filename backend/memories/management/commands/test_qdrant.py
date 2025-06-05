from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test Qdrant connection and operations"

    def handle(self, *args, **options):
        from memories.vector_service import vector_service

        self.stdout.write("Testing Qdrant connection...")

        # Health check
        if vector_service.health_check():
            self.stdout.write(self.style.SUCCESS("✓ Qdrant connection successful"))
        else:
            self.stdout.write(self.style.ERROR("✗ Qdrant connection failed"))
            return

        # Collection info
        info = vector_service.get_collection_info()
        if info:
            self.stdout.write(self.style.SUCCESS(f"✓ Collection info: {info}"))
        else:
            self.stdout.write(self.style.ERROR("✗ Failed to get collection info"))
