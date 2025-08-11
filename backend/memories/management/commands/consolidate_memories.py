"""
Django management command to consolidate duplicate memories.

This command should be run periodically (e.g., weekly) to identify and consolidate
duplicate or highly similar memories across users or for specific users.
"""

import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count

from memories.models import Memory
from memories.memory_consolidation_service import memory_consolidation_service


class Command(BaseCommand):
    help = 'Consolidate duplicate and similar memories'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=str,
            help='Consolidate memories only for a specific user',
        )
        parser.add_argument(
            '--strategy',
            type=str,
            default='llm_guided',
            choices=['automatic', 'llm_guided', 'manual'],
            help='Consolidation strategy to use',
        )
        parser.add_argument(
            '--similarity-threshold',
            type=float,
            default=0.85,
            help='Minimum similarity threshold for consolidation (0.0-1.0)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be consolidated without making changes',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of memories to process per user',
        )
        parser.add_argument(
            '--min-memories',
            type=int,
            default=10,
            help='Minimum number of memories a user must have to process',
        )
        parser.add_argument(
            '--show-candidates',
            action='store_true',
            help='Show consolidation candidates without processing',
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        strategy = options.get('strategy')
        similarity_threshold = options.get('similarity_threshold')
        dry_run = options.get('dry_run')
        batch_size = options.get('batch_size')
        min_memories = options.get('min_memories')
        show_candidates = options.get('show_candidates')

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting memory consolidation (strategy={strategy}, threshold={similarity_threshold:.2f}, dry_run={dry_run})"
            )
        )

        # Update consolidation service settings
        memory_consolidation_service.similarity_threshold = similarity_threshold

        if show_candidates:
            self._show_consolidation_candidates(user_id, batch_size, min_memories)
            return

        if user_id:
            # Process specific user
            self._consolidate_user(user_id, strategy, batch_size, dry_run)
        else:
            # Process all users with sufficient memories
            self._consolidate_all_users(strategy, batch_size, min_memories, dry_run)

    def _consolidate_user(self, user_id, strategy, batch_size, dry_run):
        """Consolidate memories for a specific user"""
        self.stdout.write(f"Processing user: {user_id}")
        
        if dry_run:
            candidates = memory_consolidation_service.find_consolidation_candidates(
                user_id, min_similarity=memory_consolidation_service.similarity_threshold
            )
            
            self.stdout.write(f"Found {len(candidates)} consolidation groups:")
            for i, (primary_memory, duplicates) in enumerate(candidates, 1):
                self.stdout.write(
                    f"\n  Group {i}: Primary memory {primary_memory.id}"
                )
                self.stdout.write(f"    Content: {primary_memory.content[:100]}...")
                self.stdout.write(f"    {len(duplicates)} duplicates:")
                
                for dup_memory, score in duplicates:
                    self.stdout.write(
                        f"      - {dup_memory.id} (similarity: {score:.3f}): {dup_memory.content[:80]}..."
                    )
        else:
            stats = memory_consolidation_service.consolidate_user_memories(
                user_id, strategy, batch_size
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ User {user_id}: {stats['memories_consolidated']} memories consolidated into {stats['consolidation_groups']} groups"
                )
            )

    def _consolidate_all_users(self, strategy, batch_size, min_memories, dry_run):
        """Consolidate memories for all users"""
        # Get users with sufficient memories
        users_with_memories = (
            Memory.objects.filter(is_active=True)
            .values('user_id')
            .annotate(memory_count=Count('id'))
            .filter(memory_count__gte=min_memories)
            .order_by('-memory_count')
        )

        total_users = len(users_with_memories)
        self.stdout.write(f"Found {total_users} users with {min_memories}+ memories")

        total_stats = {
            'users_processed': 0,
            'total_memories_consolidated': 0,
            'total_consolidation_groups': 0,
            'total_duplicates_found': 0
        }

        for i, user_data in enumerate(users_with_memories, 1):
            user_id = str(user_data['user_id'])
            memory_count = user_data['memory_count']
            
            self.stdout.write(
                f"\n[{i}/{total_users}] Processing user {user_id} ({memory_count} memories)"
            )
            
            if dry_run:
                candidates = memory_consolidation_service.find_consolidation_candidates(
                    user_id, min_similarity=memory_consolidation_service.similarity_threshold
                )
                
                if candidates:
                    total_stats['total_duplicates_found'] += sum(len(dups) for _, dups in candidates)
                    self.stdout.write(
                        f"  Would consolidate {len(candidates)} groups "
                        f"({sum(len(dups) for _, dups in candidates)} duplicates)"
                    )
                else:
                    self.stdout.write("  No consolidation candidates found")
            else:
                try:
                    stats = memory_consolidation_service.consolidate_user_memories(
                        user_id, strategy, batch_size
                    )
                    
                    total_stats['users_processed'] += 1
                    total_stats['total_memories_consolidated'] += stats['memories_consolidated']
                    total_stats['total_consolidation_groups'] += stats['consolidation_groups']
                    total_stats['total_duplicates_found'] += stats['duplicates_found']
                    
                    if stats['memories_consolidated'] > 0:
                        self.stdout.write(
                            f"  ✅ Consolidated {stats['memories_consolidated']} memories into {stats['consolidation_groups']} groups"
                        )
                    else:
                        self.stdout.write("  No duplicates found")
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  ❌ Error processing user {user_id}: {e}")
                    )

        # Final summary
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDRY RUN SUMMARY:\n"
                    f"- Would process {total_users} users\n"
                    f"- Found {total_stats['total_duplicates_found']} potential duplicates"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nCONSOLIDATION SUMMARY:\n"
                    f"- Processed {total_stats['users_processed']}/{total_users} users\n"
                    f"- Consolidated {total_stats['total_memories_consolidated']} memories\n"
                    f"- Created {total_stats['total_consolidation_groups']} consolidation groups\n"
                    f"- Found {total_stats['total_duplicates_found']} total duplicates"
                )
            )

    def _show_consolidation_candidates(self, user_id, batch_size, min_memories):
        """Show consolidation candidates for analysis"""
        if user_id:
            candidates = memory_consolidation_service.find_consolidation_candidates(
                user_id, min_similarity=memory_consolidation_service.similarity_threshold
            )
            
            self.stdout.write(f"\nConsolidation candidates for user {user_id}:")
            self._display_candidates(candidates)
        else:
            # Show candidates for top users with most memories
            users_with_memories = (
                Memory.objects.filter(is_active=True)
                .values('user_id')
                .annotate(memory_count=Count('id'))
                .filter(memory_count__gte=min_memories)
                .order_by('-memory_count')[:5]  # Top 5 users
            )
            
            for user_data in users_with_memories:
                user_id = str(user_data['user_id'])
                memory_count = user_data['memory_count']
                
                self.stdout.write(f"\n{'='*60}")
                self.stdout.write(f"User {user_id} ({memory_count} memories)")
                self.stdout.write(f"{'='*60}")
                
                candidates = memory_consolidation_service.find_consolidation_candidates(
                    user_id, min_similarity=memory_consolidation_service.similarity_threshold, limit=20
                )
                
                if candidates:
                    self._display_candidates(candidates)
                else:
                    self.stdout.write("No consolidation candidates found")

    def _display_candidates(self, candidates):
        """Display consolidation candidates in a readable format"""
        if not candidates:
            self.stdout.write("No consolidation candidates found")
            return
            
        for i, (primary_memory, duplicates) in enumerate(candidates, 1):
            self.stdout.write(f"\n📎 GROUP {i}:")
            self.stdout.write(f"   Primary: {primary_memory.id} ({primary_memory.created_at.strftime('%Y-%m-%d')})")
            self.stdout.write(f"   Content: {primary_memory.content}")
            self.stdout.write(f"   Inference Level: {primary_memory.metadata.get('inference_level', 'stated')}")
            
            self.stdout.write(f"\n   🔗 {len(duplicates)} Similar memories:")
            for dup_memory, score in duplicates:
                self.stdout.write(
                    f"      • {dup_memory.id} (similarity: {score:.3f}, {dup_memory.created_at.strftime('%Y-%m-%d')})"
                )
                self.stdout.write(f"        {dup_memory.content}")
                self.stdout.write(f"        Inference Level: {dup_memory.metadata.get('inference_level', 'stated')}")
            
        self.stdout.write(f"\n📊 SUMMARY: {len(candidates)} consolidation groups found")

    def _get_memory_stats(self):
        """Get overall memory statistics"""
        from django.db.models import Count
        
        stats = {
            'total_active_memories': Memory.objects.filter(is_active=True).count(),
            'total_inactive_memories': Memory.objects.filter(is_active=False).count(),
            'users_with_memories': Memory.objects.values('user_id').distinct().count(),
            'avg_memories_per_user': Memory.objects.filter(is_active=True).count() / max(1, Memory.objects.values('user_id').distinct().count())
        }
        
        self.stdout.write(f"\n📈 MEMORY STORE STATISTICS:")
        self.stdout.write(f"   Active memories: {stats['total_active_memories']:,}")
        self.stdout.write(f"   Inactive memories: {stats['total_inactive_memories']:,}")
        self.stdout.write(f"   Users with memories: {stats['users_with_memories']:,}")
        self.stdout.write(f"   Average memories per user: {stats['avg_memories_per_user']:.1f}")
        
        return stats