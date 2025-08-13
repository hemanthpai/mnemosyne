"""
Django management command to test memory consolidation functionality.

This command creates test memories and verifies that consolidation works correctly.
"""

import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from memories.models import Memory
from memories.memory_consolidation_service import memory_consolidation_service


class Command(BaseCommand):
    help = 'Test memory consolidation functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Create test memories for consolidation testing',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up test memories after testing',
        )
        parser.add_argument(
            '--user-id',
            type=str,
            default='test-consolidation-user',
            help='User ID to use for testing',
        )

    def handle(self, *args, **options):
        create_test_data = options.get('create_test_data')
        cleanup = options.get('cleanup')
        user_id = options.get('user_id')

        self.stdout.write(
            self.style.SUCCESS("Testing Memory Consolidation Functionality")
        )

        if cleanup:
            self._cleanup_test_data(user_id)
            return

        if create_test_data:
            self._create_test_data(user_id)

        self._run_consolidation_tests(user_id)

    def _create_test_data(self, user_id):
        """Create test memories with various types of duplicates"""
        self.stdout.write(f"Creating test memories for user: {user_id}")

        # Test case 1: Exact duplicates
        exact_duplicates = [
            "I work at Google as a software engineer",
            "I work at Google as a software engineer",  # Exact duplicate
            "I am employed at Google as a software engineer",  # Near duplicate
        ]

        # Test case 2: Similar content with different details
        similar_content = [
            "I love Italian food, especially pasta",
            "I really enjoy Italian cuisine, particularly pasta dishes",
            "Italian food is my favorite, especially spaghetti and other pasta",
        ]

        # Test case 3: Conflicting information (temporal)
        conflicting_info = [
            "I live in New York City",
            "I moved to San Francisco last month",  # Should supersede, not consolidate
        ]

        # Test case 4: Related but distinct information
        related_distinct = [
            "I have a cat named Whiskers",
            "My cat Whiskers loves to play with yarn",
            "Whiskers is a tabby cat who is 3 years old",
        ]

        test_groups = [
            ("exact_duplicates", exact_duplicates),
            ("similar_content", similar_content),
            ("conflicting_info", conflicting_info),
            ("related_distinct", related_distinct),
        ]

        created_memories = {}

        for group_name, contents in test_groups:
            group_memories = []
            
            for i, content in enumerate(contents):
                # Create memory with different timestamps
                created_time = timezone.now() - timedelta(minutes=i * 10)
                
                memory = Memory.objects.create(
                    user_id=user_id,
                    content=content,
                    fact_type='mutable',
                    original_confidence=0.8,
                    temporal_confidence=0.8,
                    metadata={
                        'tags': ['test_data', group_name],
                        'inference_level': 'stated',
                        'evidence': f'Test data for {group_name}',
                        'test_group': group_name,
                        'test_index': i
                    },
                    created_at=created_time,
                )
                
                group_memories.append(memory)
                
            created_memories[group_name] = group_memories
            self.stdout.write(f"  Created {len(group_memories)} memories for {group_name}")

        self.stdout.write(f"✅ Created {sum(len(memories) for memories in created_memories.values())} test memories")
        return created_memories

    def _run_consolidation_tests(self, user_id):
        """Run various consolidation tests"""
        # Get test memories
        test_memories = Memory.objects.filter(
            user_id=user_id,
            metadata__contains={'tags': ['test_data']}
        ).order_by('created_at')

        if not test_memories.exists():
            self.stdout.write(
                self.style.WARNING("No test memories found. Run with --create-test-data first.")
            )
            return

        self.stdout.write(f"Found {test_memories.count()} test memories")

        # Test 1: Find consolidation candidates
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("TEST 1: Finding Consolidation Candidates")
        self.stdout.write(f"{'='*60}")

        candidates = memory_consolidation_service.find_consolidation_candidates(
            user_id, min_similarity=0.75, limit=50
        )

        self.stdout.write(f"Found {len(candidates)} consolidation groups:")
        for i, (primary_memory, duplicates) in enumerate(candidates, 1):
            self.stdout.write(f"\n  Group {i}:")
            self.stdout.write(f"    Primary: {primary_memory.content}")
            self.stdout.write(f"    Group: {primary_memory.metadata.get('test_group', 'unknown')}")
            
            for dup_memory, score in duplicates:
                self.stdout.write(f"      Duplicate (score: {score:.3f}): {dup_memory.content}")

        # Test 2: Test different consolidation strategies
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("TEST 2: Testing Consolidation Strategies")
        self.stdout.write(f"{'='*60}")

        strategies = ['automatic', 'llm_guided']
        
        for strategy in strategies:
            self.stdout.write(f"\n📋 Testing {strategy} consolidation:")
            
            # Find a group to test
            if candidates:
                primary_memory, duplicates = candidates[0]
                memories_to_consolidate = [primary_memory] + [dup[0] for dup in duplicates[:2]]
                
                self.stdout.write(f"  Consolidating {len(memories_to_consolidate)} memories using {strategy}")
                
                # Make a copy for testing
                test_memories_copy = []
                for memory in memories_to_consolidate:
                    copy_memory = Memory.objects.create(
                        user_id=f"{user_id}_test_{strategy}",
                        content=memory.content,
                        fact_type=memory.fact_type,
                        original_confidence=memory.original_confidence,
                        temporal_confidence=memory.temporal_confidence,
                        metadata=memory.metadata.copy()
                    )
                    test_memories_copy.append(copy_memory)
                
                # Test consolidation
                consolidated = memory_consolidation_service.merge_memories(
                    test_memories_copy, consolidation_strategy=strategy
                )
                
                if consolidated:
                    self.stdout.write(f"  ✅ Consolidation successful!")
                    self.stdout.write(f"    Result: {consolidated.content}")
                    self.stdout.write(f"    Strategy: {consolidated.metadata.get('consolidation_type', 'unknown')}")
                    
                    # Clean up test copies
                    for memory in test_memories_copy:
                        if memory != consolidated:
                            memory.delete()
                    consolidated.delete()
                else:
                    self.stdout.write(f"  ❌ Consolidation failed")
                    
        # Test 3: Full user consolidation
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("TEST 3: Full User Memory Consolidation")
        self.stdout.write(f"{'='*60}")

        # Create a separate test user for full consolidation
        full_test_user = f"{user_id}_full_test"
        
        # Copy some test memories
        original_memories = list(test_memories[:6])  # Take first 6 memories
        for memory in original_memories:
            Memory.objects.create(
                user_id=full_test_user,
                content=memory.content,
                fact_type=memory.fact_type,
                original_confidence=memory.original_confidence,
                temporal_confidence=memory.temporal_confidence,
                metadata=memory.metadata.copy()
            )

        before_count = Memory.objects.filter(user_id=full_test_user, is_active=True).count()
        self.stdout.write(f"Before consolidation: {before_count} active memories")

        # Run full consolidation
        stats = memory_consolidation_service.consolidate_user_memories(
            full_test_user, strategy='llm_guided', limit=50
        )

        after_count = Memory.objects.filter(user_id=full_test_user, is_active=True).count()
        self.stdout.write(f"After consolidation: {after_count} active memories")
        
        self.stdout.write(f"📊 Consolidation Statistics:")
        for key, value in stats.items():
            self.stdout.write(f"  {key}: {value}")

        # Clean up full test user
        Memory.objects.filter(user_id=full_test_user).delete()

        # Test 4: Performance test
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("TEST 4: Performance Test")
        self.stdout.write(f"{'='*60}")

        import time
        start_time = time.time()
        
        # Test duplicate finding performance
        test_memory = test_memories.first()
        duplicates = memory_consolidation_service.find_duplicates(test_memory, user_id)
        
        end_time = time.time()
        duration = end_time - start_time
        
        self.stdout.write(f"Duplicate detection for 1 memory took: {duration:.3f} seconds")
        self.stdout.write(f"Found {len(duplicates)} duplicates")

        self.stdout.write(f"\n✅ All consolidation tests completed!")

    def _cleanup_test_data(self, user_id):
        """Clean up test memories"""
        self.stdout.write(f"Cleaning up test data for user: {user_id}")
        
        # Delete test memories
        deleted_count = Memory.objects.filter(
            user_id__startswith=user_id
        ).delete()[0]
        
        self.stdout.write(f"✅ Deleted {deleted_count} test memories")

    def _analyze_test_results(self, results):
        """Analyze and display test results"""
        self.stdout.write("\n📊 TEST RESULTS ANALYSIS:")
        
        # Add analysis logic here
        pass