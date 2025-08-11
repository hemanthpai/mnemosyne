"""
Django management command to apply temporal decay to memories.

This command should be run periodically (e.g., daily) to update temporal confidence
scores for all memories based on their age.
"""

import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from memories.models import Memory
from memories.conflict_resolution_service import conflict_resolution_service


class Command(BaseCommand):
    help = 'Apply temporal decay to all memories'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=str,
            help='Apply decay only to memories of a specific user',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of memories to process in each batch',
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        dry_run = options.get('dry_run')
        batch_size = options.get('batch_size')

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting temporal decay application (dry_run={dry_run})"
            )
        )

        # Get base queryset
        queryset = Memory.objects.filter(is_active=True)
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        total_memories = queryset.count()
        self.stdout.write(f"Processing {total_memories} active memories")

        processed = 0
        updated = 0
        
        # Process in batches
        while processed < total_memories:
            batch = list(queryset[processed:processed + batch_size])
            if not batch:
                break

            batch_updated = 0
            for memory in batch:
                old_confidence = memory.temporal_confidence
                
                if not dry_run:
                    new_confidence = conflict_resolution_service.apply_temporal_decay(memory)
                else:
                    # Calculate what the new confidence would be
                    now = timezone.now()
                    age_days = (now - memory.last_validated).days
                    if age_days > 0:
                        decay_periods = age_days / 30  # 30 day periods
                        decay_factor = 0.99 ** decay_periods
                        new_confidence = max(0.1, memory.original_confidence * decay_factor)
                        
                        if memory.fact_type == 'immutable':
                            new_confidence = max(new_confidence, memory.original_confidence * 0.8)
                    else:
                        new_confidence = memory.original_confidence
                
                # Check if there's a significant change
                if abs(old_confidence - new_confidence) > 0.01:
                    batch_updated += 1
                    if self.verbosity >= 2:
                        self.stdout.write(
                            f"  Memory {memory.id}: {old_confidence:.3f} -> {new_confidence:.3f}"
                        )

            updated += batch_updated
            processed += len(batch)
            
            if self.verbosity >= 1:
                self.stdout.write(
                    f"Processed {processed}/{total_memories} memories "
                    f"({batch_updated} updated in this batch)"
                )

        # Summary
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would update {updated} out of {total_memories} memories"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully updated {updated} out of {total_memories} memories"
                )
            )

        # Show some statistics
        if self.verbosity >= 1:
            self._show_statistics(user_id)

    def _show_statistics(self, user_id=None):
        """Show statistics about memory confidence levels"""
        queryset = Memory.objects.filter(is_active=True)
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Count by fact type
        mutable_count = queryset.filter(fact_type='mutable').count()
        immutable_count = queryset.filter(fact_type='immutable').count()
        temporal_count = queryset.filter(fact_type='temporal').count()

        # Average confidence by type
        from django.db.models import Avg
        avg_confidence = queryset.aggregate(
            mutable_avg=Avg('temporal_confidence', filter=queryset.filter(fact_type='mutable').values('temporal_confidence')),
            immutable_avg=Avg('temporal_confidence', filter=queryset.filter(fact_type='immutable').values('temporal_confidence')),
            temporal_avg=Avg('temporal_confidence', filter=queryset.filter(fact_type='temporal').values('temporal_confidence')),
            overall_avg=Avg('temporal_confidence')
        )

        self.stdout.write("\n" + "="*50)
        self.stdout.write("MEMORY STATISTICS")
        self.stdout.write("="*50)
        self.stdout.write(f"Mutable memories: {mutable_count}")
        self.stdout.write(f"Immutable memories: {immutable_count}")
        self.stdout.write(f"Temporal memories: {temporal_count}")
        
        if avg_confidence['overall_avg']:
            self.stdout.write(f"\nAverage confidence scores:")
            self.stdout.write(f"Overall: {avg_confidence['overall_avg']:.3f}")
            if avg_confidence['mutable_avg']:
                self.stdout.write(f"Mutable: {avg_confidence['mutable_avg']:.3f}")
            if avg_confidence['immutable_avg']:
                self.stdout.write(f"Immutable: {avg_confidence['immutable_avg']:.3f}")
            if avg_confidence['temporal_avg']:
                self.stdout.write(f"Temporal: {avg_confidence['temporal_avg']:.3f}")