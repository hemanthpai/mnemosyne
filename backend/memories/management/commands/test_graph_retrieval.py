"""
Django management command to test graph-enhanced memory retrieval functionality.

This command creates test memories with relationships and validates that graph retrieval works correctly.
"""

import uuid
from django.core.management.base import BaseCommand
from django.utils import timezone

from memories.models import Memory
from memories.graph_service import graph_service
from memories.memory_search_service import memory_search_service


class Command(BaseCommand):
    help = 'Test graph-enhanced memory retrieval functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Create test memories for graph retrieval testing',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up test memories after testing',
        )
        parser.add_argument(
            '--user-id',
            type=str,
            default='test-graph-user',
            help='User ID to use for testing',
        )

    def handle(self, *args, **options):
        create_test_data = options.get('create_test_data')
        cleanup = options.get('cleanup')
        user_id = options.get('user_id')

        self.stdout.write(
            self.style.SUCCESS("Testing Graph-Enhanced Memory Retrieval")
        )

        if cleanup:
            self._cleanup_test_data(user_id)
            return

        if create_test_data:
            self._create_test_data(user_id)

        self._run_graph_retrieval_tests(user_id)

    def _create_test_data(self, user_id):
        """Create test memories with various relationships"""
        self.stdout.write(f"Creating test memories for user: {user_id}")

        # Test case 1: Related cooking memories
        cooking_memories = [
            {
                "content": "I love making Italian pasta dishes, especially carbonara",
                "tags": ["cooking", "italian_food", "pasta", "carbonara", "loves"],
                "inference_level": "stated",
            },
            {
                "content": "My grandmother taught me how to make authentic marinara sauce",
                "tags": ["cooking", "italian_food", "sauce", "grandmother", "family", "learned"],
                "inference_level": "stated", 
            },
            {
                "content": "I always use fresh basil and oregano in my cooking",
                "tags": ["cooking", "herbs", "basil", "oregano", "ingredients", "always"],
                "inference_level": "stated",
            },
            {
                "content": "User enjoys cooking Italian food based on family traditions",
                "tags": ["cooking", "italian_food", "family", "traditions", "enjoys"],
                "inference_level": "inferred",
            }
        ]

        # Test case 2: Music and entertainment memories
        music_memories = [
            {
                "content": "I went to a jazz concert at the Blue Note last weekend",
                "tags": ["music", "jazz", "concert", "blue_note", "weekend", "attended"],
                "inference_level": "stated",
            },
            {
                "content": "I play piano and love improvisation",
                "tags": ["music", "piano", "improvisation", "plays", "loves"],
                "inference_level": "stated",
            },
            {
                "content": "Miles Davis is one of my favorite musicians",
                "tags": ["music", "jazz", "miles_davis", "favorite", "musician"],
                "inference_level": "stated",
            }
        ]

        # Test case 3: Work and technology memories
        work_memories = [
            {
                "content": "I'm working on a Python project using Django framework",
                "tags": ["work", "programming", "python", "django", "project", "currently"],
                "inference_level": "stated",
            },
            {
                "content": "I prefer using PostgreSQL for database projects",
                "tags": ["work", "database", "postgresql", "prefers", "projects"],
                "inference_level": "stated",
            },
            {
                "content": "User has experience with web development technologies",
                "tags": ["work", "web_development", "technology", "experience"],
                "inference_level": "inferred",
            }
        ]

        all_test_memories = cooking_memories + music_memories + work_memories
        created_memories = []

        for i, memory_data in enumerate(all_test_memories):
            # Create memory with embedding
            memory = memory_search_service.store_memory_with_embedding(
                content=memory_data["content"],
                user_id=user_id,
                metadata={
                    "tags": memory_data["tags"],
                    "inference_level": memory_data["inference_level"],
                    "evidence": f"Test data for graph retrieval: {memory_data['content']}",
                        "test_category": "graph_retrieval_test",
                    "test_index": i
                }
            )
            
            # Set additional fields for conflict resolution
            memory.fact_type = "mutable"
            memory.original_confidence = 0.8
            memory.temporal_confidence = 0.8
            memory.save()
            
            created_memories.append(memory)

        self.stdout.write(f"✅ Created {len(created_memories)} test memories")
        return created_memories

    def _run_graph_retrieval_tests(self, user_id):
        """Run various graph-enhanced retrieval tests"""
        # Get test memories
        test_memories = Memory.objects.filter(
            user_id=user_id,
            metadata__contains={'test_category': 'graph_retrieval_test'}
        ).order_by('created_at')

        if not test_memories.exists():
            self.stdout.write(
                self.style.WARNING("No test memories found. Run with --create-test-data first.")
            )
            return

        self.stdout.write(f"Found {test_memories.count()} test memories")

        # Test 1: Build memory graph
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("TEST 1: Building Memory Graph")
        self.stdout.write(f"{'='*60}")

        graph_result = graph_service.build_memory_graph(user_id)
        
        if graph_result["success"]:
            self.stdout.write(f"✅ Graph built successfully:")
            self.stdout.write(f"  Nodes created: {graph_result['nodes_created']}")
            self.stdout.write(f"  Relationships created: {graph_result['relationships_created']}")
        else:
            self.stdout.write(f"❌ Graph building failed: {graph_result.get('error')}")
            return

        # Test 2: Compare standard vs graph-enhanced search
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("TEST 2: Comparing Standard vs Graph-Enhanced Search")
        self.stdout.write(f"{'='*60}")

        test_queries = [
            {
                "query": "cooking Italian food",
                "expected_connections": ["pasta", "sauce", "herbs", "family"]
            },
            {
                "query": "music and improvisation", 
                "expected_connections": ["jazz", "piano", "concert", "musicians"]
            },
            {
                "query": "programming projects",
                "expected_connections": ["python", "django", "database", "web_development"]
            }
        ]

        for test_case in test_queries:
            query = test_case["query"]
            expected = test_case["expected_connections"]
            
            self.stdout.write(f"\n🔍 Testing query: '{query}'")
            
            # Standard search
            search_queries = [{"search_query": query, "confidence": 0.8, "search_type": "semantic"}]
            standard_results = memory_search_service.search_memories_with_queries(
                search_queries, user_id, limit=10, threshold=0.5
            )
            
            # Graph-enhanced search
            graph_results = memory_search_service.search_with_graph_enhancement(
                search_queries, user_id, limit=10, threshold=0.5, use_graph=True
            )
            
            self.stdout.write(f"  Standard search: {len(standard_results)} memories")
            self.stdout.write(f"  Graph-enhanced: {len(graph_results)} memories")
            
            # Check for expected connections in graph results
            found_connections = set()
            for memory in graph_results:
                memory_tags = memory.metadata.get('tags', [])
                found_connections.update(memory_tags)
            
            expected_set = set(expected)
            found_expected = expected_set & found_connections
            
            coverage = len(found_expected) / len(expected_set) if expected_set else 0
            self.stdout.write(f"  Connection coverage: {coverage:.1%} ({len(found_expected)}/{len(expected_set)})")
            
            if coverage >= 0.5:
                self.stdout.write(f"  ✅ Good connection coverage")
            else:
                self.stdout.write(f"  ⚠️  Low connection coverage")

        # Test 3: Graph traversal from specific memory
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("TEST 3: Graph Traversal Testing")
        self.stdout.write(f"{'='*60}")

        # Pick a memory about cooking
        cooking_memory = test_memories.filter(
            metadata__tags__contains=["cooking"]
        ).first()
        
        if cooking_memory:
            self.stdout.write(f"Starting traversal from: {cooking_memory.content}")
            
            related_memories = graph_service.traverse_related_memories(
                str(cooking_memory.id), user_id, depth=2
            )
            
            self.stdout.write(f"Found {len(related_memories)} related memories:")
            
            for i, rel_data in enumerate(related_memories[:5], 1):
                self.stdout.write(f"  {i}. {rel_data['content']}")
                self.stdout.write(f"     Relevance: {rel_data['relevance_score']:.3f}")
                self.stdout.write(f"     Path length: {rel_data['path_length']}")
                rel_types = [rel['type'] for rel in rel_data.get('relationships', [])]
                self.stdout.write(f"     Relationships: {', '.join(set(rel_types))}")

        # Test 4: Memory clusters
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("TEST 4: Memory Clustering")
        self.stdout.write(f"{'='*60}")

        clusters = graph_service.get_memory_clusters(user_id)
        
        self.stdout.write(f"Found {len(clusters)} memory clusters:")
        
        for cluster_name, memories in clusters.items():
            self.stdout.write(f"\n📂 {cluster_name}: {len(memories)} memories")
            for memory in memories[:3]:  # Show first 3
                self.stdout.write(f"  - {memory['content'][:80]}...")

        # Test 5: Centrality scores
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("TEST 5: Memory Centrality Analysis")
        self.stdout.write(f"{'='*60}")

        centrality_scores = graph_service.get_memory_centrality_scores(user_id)
        
        if centrality_scores:
            # Get top 5 most central memories
            sorted_scores = sorted(
                centrality_scores.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
            
            self.stdout.write("🎯 Most central memories (highly connected):")
            
            for memory_id, score in sorted_scores:
                try:
                    memory = Memory.objects.get(id=memory_id)
                    self.stdout.write(f"  Score: {score:.2f} - {memory.content[:80]}...")
                except Memory.DoesNotExist:
                    self.stdout.write(f"  Score: {score:.2f} - [Memory not found: {memory_id}]")

        self.stdout.write(f"\n✅ All graph retrieval tests completed!")

    def _cleanup_test_data(self, user_id):
        """Clean up test memories"""
        self.stdout.write(f"Cleaning up test data for user: {user_id}")
        
        # Delete test memories
        deleted_count = Memory.objects.filter(
            user_id=user_id,
            metadata__contains={'test_category': 'graph_retrieval_test'}
        ).delete()[0]
        
        # Clear graph data
        graph_service.clear_user_graph(user_id)
        
        self.stdout.write(f"✅ Deleted {deleted_count} test memories and cleared graph data")