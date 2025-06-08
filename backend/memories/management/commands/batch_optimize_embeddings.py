# Create management/commands/batch_optimize_embeddings.py

import logging

from django.core.management.base import BaseCommand

from memories.batch_service import batch_memory_service
from memories.models import Memory

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Batch regenerate embeddings for all memories using optimized storage"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=str,
            help="Regenerate embeddings for specific user only",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Batch size for processing (default: 50)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be processed without making changes",
        )

    def handle(self, *args, **options):
        user_id = options.get("user_id")
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]

        # Get memories to process
        queryset = Memory.objects.all()
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        total_memories = queryset.count()

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY RUN: Would process {total_memories} memories "
                    f"in batches of {batch_size}"
                )
            )
            return

        if total_memories == 0:
            self.stdout.write("No memories found to process")
            return

        self.stdout.write(
            f"Processing {total_memories} memories in batches of {batch_size}"
        )

        # Process by user to maintain efficiency
        if user_id:
            users_to_process = [user_id]
        else:
            users_to_process = queryset.values_list("user_id", flat=True).distinct()

        total_updated = 0
        total_failed = 0

        for user in users_to_process:
            user_memories = Memory.objects.filter(user_id=user)
            memory_ids = list(user_memories.values_list("id", flat=True))

            self.stdout.write(f"Processing {len(memory_ids)} memories for user {user}")

            result = batch_memory_service.batch_update_embeddings(
                memory_ids=memory_ids, user_id=user, batch_size=batch_size
            )

            if result["success"]:
                updated = result["updated_count"]
                failed = result["failed_count"]
                total_updated += updated
                total_failed += failed

                self.stdout.write(
                    self.style.SUCCESS(
                        f"User {user}: {updated} updated, {failed} failed"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"User {user}: Failed - {result.get('error', 'Unknown error')}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Batch processing complete: {total_updated} updated, {total_failed} failed"
            )
        )
