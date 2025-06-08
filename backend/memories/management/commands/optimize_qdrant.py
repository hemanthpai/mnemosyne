from django.core.management.base import BaseCommand

from memories.vector_service import vector_service


class Command(BaseCommand):
    help = "Optimize Qdrant collection for RAM usage and performance"

    def add_arguments(self, parser):
        parser.add_argument(
            "--recreate",
            action="store_true",
            help="Recreate collection with optimized settings",
        )
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Show performance statistics",
        )

    def handle(self, *args, **options):
        if options["stats"]:
            stats = vector_service.get_performance_stats()
            self.stdout.write(self.style.SUCCESS(f"Performance stats: {stats}"))
            return

        if options["recreate"]:
            self.stdout.write("Recreating collection with optimized settings...")
            # This would require backing up data first
            self.stdout.write(
                self.style.WARNING("Manual recreation required - backup data first!")
            )
            return

        # Default: optimize existing collection
        result = vector_service.optimize_collection()
        if result["success"]:
            self.stdout.write(
                self.style.SUCCESS("Collection optimization triggered successfully")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"Optimization failed: {result['error']}")
            )
