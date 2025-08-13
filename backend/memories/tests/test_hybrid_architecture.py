"""
Unit tests for the hybrid architecture functionality
Tests conversation chunking, bidirectional linking, and hybrid search
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

import pytest
from django.test import TestCase
from django.utils import timezone as django_timezone

from memories.models import Memory, ConversationChunk
from memories.vector_service import VectorService
from memories.graph_service import GraphService
from memories.memory_search_service import MemorySearchService


class ConversationChunkModelTest(TestCase):
    """Test the ConversationChunk model"""

    def setUp(self):
        self.user_id = str(uuid.uuid4())
        self.test_content = "This is a test conversation chunk with meaningful content."

    def test_conversation_chunk_creation(self):
        """Test creating a ConversationChunk"""
        chunk = ConversationChunk.objects.create(
            user_id=self.user_id,
            content=self.test_content,
            vector_id=f"test_vector_{uuid.uuid4().hex}",
            timestamp=django_timezone.now(),
            metadata={"source": "test", "session_id": "test_session"},
            extracted_memory_ids=[]
        )
        
        self.assertIsNotNone(chunk.id)
        self.assertEqual(chunk.user_id, self.user_id)
        self.assertEqual(chunk.content, self.test_content)
        self.assertIsInstance(chunk.metadata, dict)
        self.assertIsInstance(chunk.extracted_memory_ids, list)

    def test_conversation_chunk_bidirectional_linking(self):
        """Test bidirectional linking between chunks and memories"""
        # Create a memory
        memory = Memory.objects.create(
            user_id=self.user_id,
            content="User prefers astrophysics",
            metadata={
                "tags": ["science", "preference"],
                "confidence": 0.9,
                "entity_type": "preference",
                "inference_level": "stated"
            },
            fact_type="mutable"
        )
        
        # Create a conversation chunk
        chunk = ConversationChunk.objects.create(
            user_id=self.user_id,
            content=self.test_content,
            vector_id=f"test_vector_{uuid.uuid4().hex}",
            timestamp=django_timezone.now(),
            extracted_memory_ids=[str(memory.id)]
        )
        
        # Update memory to link back to chunk
        memory.conversation_chunk_ids = [str(chunk.id)]
        memory.save()
        
        # Verify bidirectional linking
        self.assertIn(str(memory.id), chunk.extracted_memory_ids)
        self.assertIn(str(chunk.id), memory.conversation_chunk_ids)


class VectorServiceHybridTest(TestCase):
    """Test VectorService hybrid architecture methods"""

    def setUp(self):
        self.vector_service = VectorService()
        self.user_id = str(uuid.uuid4())

    @patch('memories.vector_service.vector_service.store_embedding')
    def test_conversation_chunking(self, mock_store):
        """Test conversation text chunking"""
        long_conversation = "This is a long conversation. " * 100  # ~2700 chars
        
        chunks = self.vector_service.chunk_conversation(long_conversation, chunk_size=1000)
        
        # Should create multiple chunks
        self.assertGreater(len(chunks), 1)
        
        # Each chunk should be around the target size
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 1100)  # Allow for sentence boundaries
            self.assertGreater(len(chunk), 500)  # Should not be too small

    @patch('memories.vector_service.vector_service.store_embedding')
    def test_store_conversation_chunk_embedding(self, mock_store):
        """Test storing conversation chunk embeddings"""
        mock_store.return_value = {"success": True, "vector_id": "test_vector_123"}
        
        # Create a conversation chunk
        chunk = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="Test conversation content",
            vector_id="test_vector_123",
            timestamp=django_timezone.now()
        )
        
        result = self.vector_service.store_conversation_chunk_embedding(
            chunk_id=str(chunk.id),
            user_id=self.user_id,
            content="Test conversation content",
            timestamp=django_timezone.now(),
            metadata={"source": "test"}
        )
        
        self.assertTrue(result.get("success"))
        mock_store.assert_called_once()

    @patch('memories.vector_service.vector_service.search_similar')
    def test_search_conversation_context(self, mock_search):
        """Test searching conversation context"""
        mock_search.return_value = [
            {
                "id": "test_vector_123",
                "score": 0.85,
                "payload": {
                    "content_type": "conversation_chunk",
                    "chunk_id": "chunk_123",
                    "content": "Test conversation"
                }
            }
        ]
        
        results = self.vector_service.search_conversation_context(
            query="test query",
            user_id=self.user_id,
            limit=5
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["chunk_id"], "chunk_123")
        mock_search.assert_called_once()


class MemoryModelHybridTest(TestCase):
    """Test Memory model updates for hybrid architecture"""

    def setUp(self):
        self.user_id = str(uuid.uuid4())

    def test_memory_standardized_metadata(self):
        """Test memory metadata standardization"""
        memory = Memory.objects.create(
            user_id=self.user_id,
            content="User works as a software engineer",
            metadata={
                "tags": ["work", "profession"],
                "confidence": 0.85,
                "entity_type": "fact",
                "inference_level": "stated",
                "evidence": "User explicitly mentioned their job title"
            },
            fact_type="immutable",
            conversation_chunk_ids=["chunk_123", "chunk_456"]
        )
        
        standardized = memory.get_standardized_metadata()
        
        # Verify all required fields are present
        required_fields = [
            "entity_type", "inference_level", "evidence",
            "tags", "extraction_timestamp", "relationship_hints", "model_used", "extraction_source"
        ]
        for field in required_fields:
            self.assertIn(field, standardized)
        
        # Verify conversation chunk IDs are preserved
        self.assertEqual(memory.conversation_chunk_ids, ["chunk_123", "chunk_456"])

    def test_memory_conversation_chunk_linking(self):
        """Test memory linking to conversation chunks"""
        memory = Memory.objects.create(
            user_id=self.user_id,
            content="Test memory content",
            metadata={"tags": ["test"], "confidence": 0.8},
            fact_type="mutable"
        )
        
        # Initially no chunks linked
        self.assertEqual(memory.conversation_chunk_ids, [])
        
        # Link to conversation chunks
        memory.conversation_chunk_ids = ["chunk_1", "chunk_2"]
        memory.save()
        
        # Verify linking
        memory.refresh_from_db()
        self.assertEqual(memory.conversation_chunk_ids, ["chunk_1", "chunk_2"])


class MemorySearchServiceHybridTest(TestCase):
    """Test MemorySearchService hybrid architecture methods"""

    def setUp(self):
        self.search_service = MemorySearchService()
        self.user_id = str(uuid.uuid4())

    @patch('memories.memory_search_service.MemorySearchService._extract_memories_from_text')
    @patch('memories.vector_service.VectorService.store_conversation_chunks')
    @patch('memories.graph_service.GraphService.build_memory_graph')
    def test_store_conversation_and_memories(self, mock_graph, mock_vector, mock_extract):
        """Test storing conversation and extracted memories"""
        # Mock extraction
        mock_extract.return_value = [
            {
                "content": "User likes coffee",
                "entity_type": "preference",
                "confidence": 0.9,
                "inference_level": "stated",
                "evidence": "User said 'I love coffee'",
                "fact_type": "mutable"
            }
        ]
        
        # Mock vector storage
        mock_vector.return_value = {
            "success": True,
            "chunk_ids": ["chunk_123"]
        }
        
        # Mock graph building
        mock_graph.return_value = {
            "success": True,
            "relationships_created": 2
        }
        
        conversation = "I love coffee. I drink it every morning."
        
        result = self.search_service.store_conversation_and_memories(
            conversation_text=conversation,
            user_id=self.user_id
        )
        
        self.assertTrue(result["success"])
        self.assertEqual(result["memories_extracted"], 1)
        mock_extract.assert_called_once()
        mock_vector.assert_called_once()
        mock_graph.assert_called_once()

    @patch('memories.vector_service.VectorService.search_conversation_context')
    @patch('memories.graph_service.GraphService.expand_memory_set_with_relationships')
    def test_hybrid_search_architecture(self, mock_graph_expand, mock_vector_search):
        """Test the 4-step hybrid search architecture"""
        # Mock vector search results
        mock_vector_search.return_value = [
            {
                "chunk_id": "chunk_123",
                "score": 0.85,
                "content": "I love coffee",
                "extracted_memory_ids": ["memory_1", "memory_2"]
            }
        ]
        
        # Mock graph expansion
        mock_graph_expand.return_value = {
            "expanded_memory_ids": ["memory_1", "memory_2", "memory_3"],
            "relationship_scores": {"memory_3": 0.7}
        }
        
        # Create test memories
        memory1 = Memory.objects.create(
            user_id=self.user_id,
            content="User likes coffee",
            metadata={"confidence": 0.9, "entity_type": "preference"},
            fact_type="mutable",
            conversation_chunk_ids=["chunk_123"]
        )
        
        memory2 = Memory.objects.create(
            user_id=self.user_id,
            content="User drinks coffee daily",
            metadata={"confidence": 0.8, "entity_type": "fact"},
            fact_type="mutable",
            conversation_chunk_ids=["chunk_123"]
        )
        
        result = self.search_service.search_memories_with_hybrid_approach(
            prompt="coffee preferences",
            user_id=self.user_id,
            limit=10
        )
        
        self.assertTrue(result["success"])
        self.assertGreater(len(result["memories"]), 0)
        self.assertIn("hybrid_search_info", result)
        mock_vector_search.assert_called_once()

    def test_conversation_session_detection(self):
        """Test conversation session detection"""
        # Create conversation chunks with different timestamps
        now = django_timezone.now()
        
        chunk1 = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="First conversation",
            vector_id="vector_1",
            timestamp=now,
            extracted_memory_ids=["memory_1"]
        )
        
        # Second chunk 30 minutes later (same session)
        chunk2 = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="Continuing conversation",
            vector_id="vector_2",
            timestamp=now + django_timezone.timedelta(minutes=30),
            extracted_memory_ids=["memory_2"]
        )
        
        # Third chunk 2 hours later (different session)
        chunk3 = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="New conversation",
            vector_id="vector_3",
            timestamp=now + django_timezone.timedelta(hours=2),
            extracted_memory_ids=["memory_3"]
        )
        
        # Test session detection
        expanded_context = self.search_service.expand_conversation_context(
            chunk_ids=[str(chunk2.id)],
            user_id=self.user_id
        )
        
        self.assertIn("conversation_context", expanded_context)
        # Should include chunk1 and chunk2 (same session), but not chunk3
        session_chunks = expanded_context["conversation_context"]["total_expanded_chunks"]
        self.assertGreaterEqual(session_chunks, 2)


class GraphServiceHybridTest(TestCase):
    """Test GraphService hybrid architecture enhancements"""

    def setUp(self):
        self.graph_service = GraphService()
        self.user_id = str(uuid.uuid4())

    @patch('memories.graph_service.GraphService._create_memory_node')
    @patch('memories.graph_service.GraphService._create_enhanced_relationships')
    def test_enhanced_relationship_detection(self, mock_relationships, mock_node):
        """Test enhanced relationship detection"""
        # Create test memories
        memory1 = Memory.objects.create(
            user_id=self.user_id,
            content="User likes coffee",
            metadata={
                "entity_type": "preference",
                "inference_level": "stated",
                "confidence": 0.9
            },
            fact_type="mutable"
        )
        
        memory2 = Memory.objects.create(
            user_id=self.user_id,
            content="User drinks tea in the evening",
            metadata={
                "entity_type": "preference", 
                "inference_level": "stated",
                "confidence": 0.8
            },
            fact_type="mutable"
        )
        
        mock_node.return_value = {"success": True}
        mock_relationships.return_value = {"relationships_created": 3}
        
        result = self.graph_service.build_memory_graph(
            user_id=self.user_id,
            incremental=False
        )
        
        # Verify enhanced relationship creation was called
        mock_relationships.assert_called()
        self.assertTrue(result.get("success"))

    def test_relationship_type_detection(self):
        """Test different relationship type detection"""
        # Test contradicts detection
        contradicts = self.graph_service._detect_contradicts_relationship(
            "User likes coffee",
            "User hates coffee",
            {"entity_type": "preference"},
            {"entity_type": "preference"}
        )
        self.assertTrue(contradicts)
        
        # Test updates detection
        updates = self.graph_service._detect_updates_relationship(
            "User works at Company A",
            "User works at Company B", 
            {"entity_type": "fact"},
            {"entity_type": "fact"}
        )
        self.assertTrue(updates)
        
        # Test supports detection
        supports = self.graph_service._detect_supports_relationship(
            "User is a software engineer",
            "User codes in Python",
            {"entity_type": "fact"},
            {"entity_type": "skill"}
        )
        self.assertTrue(supports)


if __name__ == '__main__':
    pytest.main([__file__])