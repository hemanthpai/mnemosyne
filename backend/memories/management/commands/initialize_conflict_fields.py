"""
Django management command to initialize conflict resolution fields for existing memories.

This should be run once after the migration to set appropriate values for existing memories.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from memories.models import Memory


class Command(BaseCommand):
    help = 'Initialize conflict resolution fields for existing memories'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')

        self.stdout.write(
            self.style.SUCCESS(
                f"Initializing conflict resolution fields (dry_run={dry_run})"
            )
        )

        # Get all memories that need initialization
        memories_to_update = Memory.objects.filter(
            last_validated__isnull=True
        )

        total_memories = memories_to_update.count()
        self.stdout.write(f"Found {total_memories} memories to initialize")

        if total_memories == 0:
            self.stdout.write(self.style.SUCCESS("No memories need initialization"))
            return

        updated_count = 0
        for memory in memories_to_update:
            # Set last_validated to created_at
            # Set original_confidence from metadata if available
            confidence = 0.5  # Default
            if memory.metadata and 'confidence' in memory.metadata:
                confidence = float(memory.metadata['confidence'])

            if not dry_run:
                memory.last_validated = memory.created_at
                memory.original_confidence = confidence
                memory.temporal_confidence = confidence
                memory.save()

            updated_count += 1

            if self.verbosity >= 2:
                self.stdout.write(
                    f"  Memory {memory.id}: confidence={confidence:.3f}, "
                    f"validated={memory.created_at.strftime('%Y-%m-%d')}"
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would initialize {updated_count} memories"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully initialized {updated_count} memories"
                )
            )