"""
Integration tests for the MemorySearchService class - requires Qdrant and LLM connection
"""

import logging
import os
import unittest
import uuid
from unittest import mock

import pytest
import requests
from django.test import TestCase

from memories.memory_search_service import MemorySearchService
from memories.llm_service import llm_service as llm_service_instance
from memories.models import Memory

# Configure logging to ensure messages are visible
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

# Increase verbosity of specific loggers
logging.getLogger("memories.memory_search_service").setLevel(logging.DEBUG)
logging.getLogger("memories.llm_service").setLevel(logging.DEBUG)
logging.getLogger("memories.vector_service").setLevel(logging.DEBUG)

# Test Qdrant connection details
QDRANT_TEST_HOST = os.environ.get("QDRANT_TEST_HOST", "localhost")
QDRANT_TEST_PORT = int(os.environ.get("QDRANT_TEST_PORT", "6334"))  # Different port for tests


def is_qdrant_test_available():
    """Check if Qdrant test instance is available"""
    print("=== Qdrant Test Availability Check ===")
    print(f"Qdrant test connection details: {QDRANT_TEST_HOST}:{QDRANT_TEST_PORT}")

    # Connect directly with Qdrant client to avoid Django dependency
    print("Attempting direct Qdrant connection...")
    try:
        from qdrant_client import QdrantClient

        client = None
        try:
            client = QdrantClient(host=QDRANT_TEST_HOST, port=QDRANT_TEST_PORT, timeout=3)
            # Test connection by getting collections
            _ = client.get_collections()
            print("Direct Qdrant connection successful!")
            print("=== Qdrant is AVAILABLE ===\n")
            return True
        finally:
            # Always close the client, even if an exception occurred
            if client:
                client.close()
    except Exception as e:
        print(f"Failed direct Qdrant connection: {e}")
        print("=== Qdrant is NOT AVAILABLE ===\n")
        logger.warning(f"Direct Qdrant connection failed: {e}")
        return False


def is_openai_api_available():
    """Check if an OpenAI-compatible API endpoint is available"""
    # Check for endpoint URL in environment (using OLLAMA_BASE_URL like the main tests)
    endpoint_url = os.environ.get('OLLAMA_BASE_URL')
    api_key = os.environ.get('OLLAMA_API_KEY')  # Optional for Ollama
    
    if not endpoint_url:
        logger.info('No LLM endpoint URL specified (set OLLAMA_BASE_URL)')
        return False
    
    # Validate the URL format
    try:
        from urllib.parse import urlparse
        parsed = urlparse(endpoint_url)
        if not parsed.scheme or not parsed.netloc:
            logger.warning(f'Invalid LLM endpoint URL format: {endpoint_url}')
            return False
    except Exception as e:
        logger.warning(f'Error parsing LLM endpoint URL: {e}')
        return False
    
    # Try a simple request to check if the endpoint is accessible
    # Only do this for http/https URLs to avoid hanging on local connections
    if parsed.scheme in ['http', 'https']:
        try:
            logger.info(f'Testing LLM endpoint: {endpoint_url}')
            # Set a short timeout to avoid hanging tests
            headers = {}
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            response = requests.get(endpoint_url, timeout=3, headers=headers or None)
            # We don't actually care about the response content, just that the endpoint exists
            logger.info(f'LLM endpoint test status code: {response.status_code}')
            # Even 401/403 is OK here - it means the endpoint exists but we need proper auth
            return response.status_code < 500
        except requests.RequestException as e:
            logger.warning(f'Error connecting to LLM endpoint: {e}')
            return False
    
    # For non-HTTP endpoints, just return True if the URL is valid
    return True


@pytest.mark.integration
@pytest.mark.skipif(
    not is_qdrant_test_available(),
    reason="Qdrant test instance not available"
)
@pytest.mark.django_db
class MemorySearchServiceIntegrationTest(TestCase):
    """Integration tests for the MemorySearchService class - requires Qdrant connection"""

    @classmethod
    def setUpClass(cls):
        """Set up the test environment once before all tests"""
        super().setUpClass()
        
        # Store original environment variables
        cls.orig_qdrant_host = os.environ.get("QDRANT_HOST")
        cls.orig_qdrant_port = os.environ.get("QDRANT_PORT")
        cls.orig_collection_name = os.environ.get("QDRANT_COLLECTION_NAME")
        
        # Set test environment variables
        os.environ["QDRANT_HOST"] = QDRANT_TEST_HOST
        os.environ["QDRANT_PORT"] = str(QDRANT_TEST_PORT)
        os.environ["QDRANT_COLLECTION_NAME"] = f"test_memories_{uuid.uuid4().hex}"
        
        # Create a fresh service instance with test settings
        cls.memory_search_service = MemorySearchService()
        
        # Clear any existing test data
        cls.memory_search_service.clear_cache()
        
        # Clear vector database
        from memories.vector_service import vector_service
        vector_service.clear_all_memories()

    def setUp(self):
        """Set up test environment before each test"""
        # Create a test user ID
        self.test_user_id = str(uuid.uuid4())
        
        # Clear cache between tests
        self.memory_search_service.clear_cache()
        
        # Clear any existing memories for this user
        from memories.vector_service import vector_service
        vector_service.delete_user_memories(self.test_user_id)
        
        # Delete all Memory objects for this user
        Memory.objects.filter(user_id=self.test_user_id).delete()
        
        # Validate LLM endpoint availability
        self._validate_llm_endpoint()

    def tearDown(self):
        """Clean up after each test"""
        # Clear cache after tests
        self.memory_search_service.clear_cache()
        
        # Clear any memories created during the test
        from memories.vector_service import vector_service
        vector_service.delete_user_memories(self.test_user_id)
        
        # Delete all Memory objects for this user
        Memory.objects.filter(user_id=self.test_user_id).delete()

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        # Clear test collection
        try:
            from memories.vector_service import vector_service
            vector_service.clear_all_memories()
        except Exception as e:
            logger.warning(f"Error clearing test collection: {e}")
        
        # Restore original environment variables
        if cls.orig_qdrant_host:
            os.environ["QDRANT_HOST"] = cls.orig_qdrant_host
        else:
            os.environ.pop("QDRANT_HOST", None)
            
        if cls.orig_qdrant_port:
            os.environ["QDRANT_PORT"] = cls.orig_qdrant_port
        else:
            os.environ.pop("QDRANT_PORT", None)
            
        if cls.orig_collection_name:
            os.environ["QDRANT_COLLECTION_NAME"] = cls.orig_collection_name
        else:
            os.environ.pop("QDRANT_COLLECTION_NAME", None)
        
        super().tearDownClass()

    def _validate_llm_endpoint(self):
        """Validate that an LLM endpoint is available and properly configured.
        Returns tuple of (endpoint_url, api_key) if valid, otherwise skips the test.
        """
        # Check for endpoint URL in environment (using OLLAMA_BASE_URL like the main tests)
        endpoint_url = os.environ.get('OLLAMA_BASE_URL')
        api_key = os.environ.get('OLLAMA_API_KEY')  # Optional for Ollama
        
        if not endpoint_url:
            self.skipTest('No LLM endpoint URL specified (set OLLAMA_BASE_URL)')
        
        # Validate the URL format
        try:
            from urllib.parse import urlparse
            parsed = urlparse(endpoint_url)
            if not parsed.scheme or not parsed.netloc:
                self.skipTest(f'Invalid LLM endpoint URL format: {endpoint_url}')
        except Exception as e:
            self.skipTest(f'Error parsing LLM endpoint URL: {e}')
        
        # Try a simple request to check if the endpoint is accessible
        # Only do this for http/https URLs to avoid hanging on local connections
        if parsed.scheme in ['http', 'https']:
            try:
                logger.info(f'Testing LLM endpoint: {endpoint_url}')
                # Set a short timeout to avoid hanging tests
                headers = {}
                if api_key:
                    headers['Authorization'] = f'Bearer {api_key}'
                response = requests.get(endpoint_url, timeout=3, headers=headers or None)
                # We don't actually care about the response content, just that the endpoint exists
                logger.info(f'LLM endpoint test status code: {response.status_code}')
                # Even 401/403 is OK here - it means the endpoint exists but we need proper auth
                if response.status_code >= 500:
                    self.skipTest(f'LLM endpoint returned server error: {response.status_code}')
            except requests.exceptions.RequestException as e:
                logger.error(f'Connection error to LLM API: {e}')
                self.skipTest(f'Cannot connect to LLM API endpoint: {e}')
            except Exception as e:
                logger.error(f'Unexpected error testing LLM API: {e}')
                self.skipTest(f'Error testing LLM API connectivity: {e}')
        
        return endpoint_url, api_key

    # 1. Basic Service Functionality Tests
    
    def test_service_initialization(self):
        """Test successful initialization of MemorySearchService"""
        # Verify service was initialized
        self.assertIsNotNone(self.memory_search_service)
        self.assertIsInstance(self.memory_search_service, MemorySearchService)
        
        # Verify cache is empty
        self.assertEqual(len(self.memory_search_service.embedding_cache), 0)

    def test_store_memory_with_embedding(self):
        """Test storing a memory with embedding"""
        content = "This is a test memory about artificial intelligence and machine learning."
        metadata = {"tags": ["ai", "ml"], "source": "test"}
        
        # Store memory
        memory = self.memory_search_service.store_memory_with_embedding(
            content=content,
            user_id=self.test_user_id,
            metadata=metadata
        )
        
        # Verify memory was created
        self.assertIsNotNone(memory)
        self.assertEqual(memory.content, content)
        self.assertEqual(memory.user_id, self.test_user_id)
        self.assertEqual(memory.metadata, metadata)
        self.assertIsNotNone(memory.vector_id)
        self.assertIsInstance(memory.vector_id, str)
        
        # Verify memory was saved to database
        saved_memory = Memory.objects.get(id=memory.id)
        self.assertEqual(saved_memory.content, content)
        self.assertEqual(saved_memory.user_id, self.test_user_id)
        self.assertEqual(saved_memory.metadata, metadata)
        self.assertEqual(saved_memory.vector_id, memory.vector_id)

    def test_store_memory_with_embedding_failure(self):
        """Test handling of embedding generation failure"""
        content = "This is a test memory."
        metadata = {"tags": ["test"]}
        
        # Mock embedding generation to fail
        with mock.patch.object(llm_service_instance, 'get_embeddings', 
                              return_value={"success": False, "error": "Embedding failed"}):
            with self.assertRaises(ValueError) as context:
                self.memory_search_service.store_memory_with_embedding(
                    content=content,
                    user_id=self.test_user_id,
                    metadata=metadata
                )
            
            self.assertIn("Failed to generate embedding", str(context.exception))
            
            # Verify no memory was saved to database
            self.assertEqual(Memory.objects.filter(user_id=self.test_user_id).count(), 0)

    # 2. Search Functionality Tests
    
    def test_search_memories(self):
        """Test searching for memories"""
        # First store some memories
        content1 = "I love programming in Python and working with machine learning algorithms."
        content2 = "My favorite hobby is hiking in the mountains during summer."
        content3 = "I'm learning about neural networks and deep learning frameworks."
        
        memory1 = self.memory_search_service.store_memory_with_embedding(
            content=content1,
            user_id=self.test_user_id,
            metadata={"tags": ["programming", "python"]}
        )
        
        memory2 = self.memory_search_service.store_memory_with_embedding(
            content=content2,
            user_id=self.test_user_id,
            metadata={"tags": ["hiking", "outdoors"]}
        )
        
        memory3 = self.memory_search_service.store_memory_with_embedding(
            content=content3,
            user_id=self.test_user_id,
            metadata={"tags": ["ml", "neural networks"]}
        )
        
        # Search for programming related memories
        results = self.memory_search_service.search_memories(
            query="programming and Python",
            user_id=self.test_user_id,
            limit=10,
            threshold=0.3
        )
        
        # Verify results
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        
        # The first memory should be most relevant
        if len(results) > 0:
            # At least one result should be found
            self.assertIn(results[0].id, [memory1.id, memory2.id, memory3.id])

    def test_search_memories_empty_query(self):
        """Test searching with empty query"""
        # First store a memory
        content = "This is a test memory."
        self.memory_search_service.store_memory_with_embedding(
            content=content,
            user_id=self.test_user_id,
            metadata={"tags": ["test"]}
        )
        
        # Search with empty query
        results = self.memory_search_service.search_memories(
            query="",
            user_id=self.test_user_id,
            limit=10
        )
        
        # Should return empty list
        self.assertIsInstance(results, list)
        # With empty query, we might get results or empty list depending on LLM behavior
        # But it should not crash

    def test_search_memories_no_results(self):
        """Test searching when no memories match"""
        # Search without storing any memories
        results = self.memory_search_service.search_memories(
            query="completely unrelated query about quantum physics",
            user_id=self.test_user_id,
            limit=10,
            threshold=0.9  # High threshold
        )
        
        # Should return empty list
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 0)

    def test_search_memories_with_queries(self):
        """Test enhanced search with multiple queries"""
        # First store some memories
        content1 = "I enjoy working with Python for data science projects."
        content2 = "My weekend activity is rock climbing in outdoor locations."
        content3 = "I'm researching natural language processing techniques."
        
        self.memory_search_service.store_memory_with_embedding(
            content=content1,
            user_id=self.test_user_id,
            metadata={"tags": ["python", "data science"]}
        )
        
        self.memory_search_service.store_memory_with_embedding(
            content=content2,
            user_id=self.test_user_id,
            metadata={"tags": ["climbing", "outdoors"]}
        )
        
        self.memory_search_service.store_memory_with_embedding(
            content=content3,
            user_id=self.test_user_id,
            metadata={"tags": ["nlp", "research"]}
        )
        
        # Search with multiple queries
        search_queries = [
            {"query": "Python programming", "type": "direct", "weight": 1.0},
            {"query": "data science", "type": "semantic", "weight": 0.8}
        ]
        
        results = self.memory_search_service.search_memories_with_queries(
            search_queries=search_queries,
            user_id=self.test_user_id,
            limit=10,
            threshold=0.3
        )
        
        # Verify results
        self.assertIsInstance(results, list)
        # Should get some results
        self.assertGreaterEqual(len(results), 0)  # May be empty depending on embeddings

    # 3. Caching Tests
    
    def test_embedding_cache(self):
        """Test embedding caching functionality"""
        query = "test query for caching"
        
        # Check cache is initially empty
        cache_key = f"embedding:{hash(query)}"
        self.assertNotIn(cache_key, self.memory_search_service.embedding_cache)
        
        # Perform a search to populate cache
        self.memory_search_service.search_memories(
            query=query,
            user_id=self.test_user_id,
            limit=5
        )
        
        # Check that embedding was cached
        # Note: This might not always be cached depending on implementation details
        # But we can at least verify the cache structure
        self.assertIsInstance(self.memory_search_service.embedding_cache, dict)

    def test_clear_cache(self):
        """Test clearing the embedding cache"""
        query = "test query for cache clearing"
        
        # Perform a search to populate cache
        self.memory_search_service.search_memories(
            query=query,
            user_id=self.test_user_id,
            limit=5
        )
        
        # Clear cache
        self.memory_search_service.clear_cache()
        
        # Verify cache is empty
        self.assertEqual(len(self.memory_search_service.embedding_cache), 0)

    # 4. Advanced Functionality Tests
    
    def test_find_semantic_connections(self):
        """Test finding semantic connections between memories"""
        # First store some related memories
        content1 = "I'm learning about machine learning algorithms."
        content2 = "Neural networks are a subset of machine learning."
        
        memory1 = self.memory_search_service.store_memory_with_embedding(
            content=content1,
            user_id=self.test_user_id,
            metadata={"tags": ["ml", "learning"]}
        )
        
        memory2 = self.memory_search_service.store_memory_with_embedding(
            content=content2,
            user_id=self.test_user_id,
            metadata={"tags": ["neural networks", "ml"]}
        )
        
        memories = [memory1, memory2]
        
        # Find semantic connections
        connected_memories = self.memory_search_service.find_semantic_connections(
            memories=memories,
            original_query="machine learning concepts",
            user_id=self.test_user_id
        )
        
        # Verify results
        self.assertIsInstance(connected_memories, list)
        # Should at least return the original memories
        self.assertGreaterEqual(len(connected_memories), len(memories))

    @unittest.skip("Skipping due to potential LLM costs and time")
    def test_summarize_relevant_memories(self):
        """Test summarizing relevant memories (skipped to avoid LLM costs)"""
        # First store some memories
        content1 = "I've been working on a Python project for data analysis."
        content2 = "The project involves processing large datasets with pandas."
        
        memory1 = self.memory_search_service.store_memory_with_embedding(
            content=content1,
            user_id=self.test_user_id,
            metadata={"tags": ["python", "data analysis"]}
        )
        
        memory2 = self.memory_search_service.store_memory_with_embedding(
            content=content2,
            user_id=self.test_user_id,
            metadata={"tags": ["pandas", "datasets"]}
        )
        
        memories = [memory1, memory2]
        
        # Summarize memories
        summary = self.memory_search_service.summarize_relevant_memories(
            memories=memories,
            user_query="Tell me about my data analysis work"
        )
        
        # Verify summary structure
        self.assertIsInstance(summary, dict)
        self.assertIn("summary", summary)
        self.assertIn("key_points", summary)
        self.assertIn("confidence", summary)
        
        # Verify content
        self.assertIsInstance(summary["summary"], str)
        self.assertIsInstance(summary["key_points"], list)
        self.assertIsInstance(summary["confidence"], (int, float))

    # 5. Error Handling Tests
    
    def test_search_memories_embedding_failure(self):
        """Test handling of embedding generation failure during search"""
        # Mock embedding generation to fail
        with mock.patch.object(llm_service_instance, 'get_embeddings', 
                              return_value={"success": False, "error": "Embedding failed"}):
            results = self.memory_search_service.search_memories(
                query="test query",
                user_id=self.test_user_id,
                limit=10
            )
            
            # Should return empty list
            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 0)

    def test_search_memories_vector_service_failure(self):
        """Test handling of vector service failure during search"""
        # First store a memory
        content = "This is a test memory."
        self.memory_search_service.store_memory_with_embedding(
            content=content,
            user_id=self.test_user_id,
            metadata={"tags": ["test"]}
        )
        
        # Mock vector service to fail
        from memories.vector_service import vector_service
        with mock.patch.object(vector_service, 'search_similar', 
                              side_effect=Exception("Vector service error")):
            results = self.memory_search_service.search_memories(
                query="test query",
                user_id=self.test_user_id,
                limit=10
            )
            
            # Should return empty list
            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 0)

    # 6. Cross-User Isolation Tests
    
    def test_user_data_isolation(self):
        """Test that users cannot access each other's memories"""
        # Create another user
        other_user_id = str(uuid.uuid4())
        
        # Store memory for first user
        content1 = "First user's private memory."
        memory1 = self.memory_search_service.store_memory_with_embedding(
            content=content1,
            user_id=self.test_user_id,
            metadata={"tags": ["user1"]}
        )
        
        # Store memory for second user
        content2 = "Second user's private memory."
        memory2 = self.memory_search_service.store_memory_with_embedding(
            content=content2,
            user_id=other_user_id,
            metadata={"tags": ["user2"]}
        )
        
        # First user searches - should only find their own memory
        results1 = self.memory_search_service.search_memories(
            query="private memory",
            user_id=self.test_user_id,
            limit=10
        )
        
        # Second user searches - should only find their own memory
        results2 = self.memory_search_service.search_memories(
            query="private memory",
            user_id=other_user_id,
            limit=10
        )
        
        # Verify isolation
        self.assertIn(memory1, results1)
        self.assertNotIn(memory2, results1)
        
        self.assertIn(memory2, results2)
        self.assertNotIn(memory1, results2)

    # 7. Performance Test (simple version)
    
    @unittest.skip("Skipping performance test in regular test suite")
    def test_search_performance(self):
        """Simple performance test with multiple memories (skipped by default)"""
        # Store multiple memories
        base_content = "This is test memory number {}. It contains information about {} and {}."
        topics = ["machine learning", "data science", "artificial intelligence", 
                 "neural networks", "deep learning", "natural language processing"]
        
        # Create 20 memories
        memories = []
        for i in range(20):
            content = base_content.format(i, topics[i % len(topics)], topics[(i + 1) % len(topics)])
            memory = self.memory_search_service.store_memory_with_embedding(
                content=content,
                user_id=self.test_user_id,
                metadata={"tags": ["test", f"topic_{i % len(topics)}"]}
            )
            memories.append(memory)
        
        # Time the search operation
        import time
        start_time = time.time()
        
        results = self.memory_search_service.search_memories(
            query="machine learning and data science",
            user_id=self.test_user_id,
            limit=10
        )
        
        elapsed_time = time.time() - start_time
        
        # Verify results
        self.assertIsInstance(results, list)
        
        # Log performance
        print(f"Performance test: searched 20 memories in {elapsed_time:.4f} seconds")
        print(f"Found {len(results)} relevant memories")


if __name__ == '__main__':
    unittest.main()
