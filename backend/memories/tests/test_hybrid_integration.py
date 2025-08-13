"""
Integration tests for the hybrid architecture end-to-end workflows
Tests complete flows from conversation input to memory retrieval
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone as django_timezone

from memories.models import Memory, ConversationChunk
from memories.memory_search_service import MemorySearchService
from memories.vector_service import VectorService
from memories.graph_service import GraphService


class HybridArchitectureIntegrationTest(TestCase):
    """Integration tests for complete hybrid architecture workflows"""

    def setUp(self):
        self.client = Client()
        self.user_id = str(uuid.uuid4())
        self.search_service = MemorySearchService()
        self.vector_service = VectorService()
        self.graph_service = GraphService()

    @patch('memories.vector_service.VectorService.store_conversation_chunks')
    @patch('memories.llm_service.LLMService.extract_memories')
    @patch('memories.graph_service.GraphService.build_memory_graph')
    def test_complete_memory_extraction_workflow(self, mock_graph, mock_extract, mock_vector):
        """Test complete workflow from conversation to memory extraction and storage"""
        
        # Mock LLM extraction response
        mock_extract.return_value = {
            "success": True,
            "memories": [
                {
                    "content": "User works as a software engineer",
                    "entity_type": "fact",
                    "inference_level": "stated",
                    "confidence": 0.95,
                    "evidence": "User explicitly mentioned their job title",
                    "fact_type": "immutable",
                    "tags": ["work", "profession"]
                },
                {
                    "content": "User prefers remote work",
                    "entity_type": "preference",
                    "inference_level": "inferred",
                    "confidence": 0.8,
                    "evidence": "User mentioned working from home",
                    "fact_type": "mutable",
                    "tags": ["work", "preference"]
                }
            ]
        }
        
        # Mock vector storage
        mock_vector.return_value = {
            "success": True,
            "chunk_ids": ["chunk_123", "chunk_456"],
            "chunks_created": 2
        }
        
        # Mock graph building
        mock_graph.return_value = {
            "success": True,
            "relationships_created": 3,
            "nodes_created": 2
        }
        
        # Test conversation input
        conversation = """
        Hi, I'm John and I work as a software engineer at TechCorp. 
        I really enjoy my job, especially since I can work from home most days.
        The flexibility allows me to focus better and maintain work-life balance.
        """
        
        # Call extraction endpoint
        url = reverse('extract-memories')
        response = self.client.post(url, {
            'conversation_text': conversation,
            'user_id': self.user_id
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify extraction response
        self.assertTrue(data['success'])
        self.assertEqual(data['memories_extracted'], 2)
        self.assertIn('hybrid_storage', data)
        
        # Verify mocks were called correctly
        mock_extract.assert_called_once()
        mock_vector.assert_called_once()
        mock_graph.assert_called_once()
        
        # Verify memories were created
        memories = Memory.objects.filter(user_id=self.user_id)
        self.assertEqual(memories.count(), 2)
        
        # Verify memory content and metadata
        work_memory = memories.filter(content__icontains="software engineer").first()
        self.assertIsNotNone(work_memory)
        self.assertEqual(work_memory.metadata['entity_type'], 'fact')
        self.assertEqual(work_memory.metadata['inference_level'], 'stated')

    @patch('memories.vector_service.VectorService.search_conversation_context')
    @patch('memories.graph_service.GraphService.expand_memory_set_with_relationships')
    def test_complete_hybrid_search_workflow(self, mock_graph_expand, mock_vector_search):
        """Test complete hybrid search workflow from query to ranked results"""
        
        # Create test data - conversation chunks and memories
        chunk1 = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="I work as a software engineer and love coding in Python",
            vector_id="vector_1",
            timestamp=django_timezone.now(),
            metadata={"session_id": "session_1"}
        )
        
        chunk2 = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="I also enjoy machine learning and data science projects",
            vector_id="vector_2", 
            timestamp=django_timezone.now(),
            metadata={"session_id": "session_1"}
        )
        
        memory1 = Memory.objects.create(
            user_id=self.user_id,
            content="User works as a software engineer",
            metadata={
                "entity_type": "fact",
                "inference_level": "stated",
                "confidence": 0.95,
                "tags": ["work", "profession"]
            },
            fact_type="immutable",
            conversation_chunk_ids=[str(chunk1.id)]
        )
        
        memory2 = Memory.objects.create(
            user_id=self.user_id,
            content="User enjoys Python programming",
            metadata={
                "entity_type": "preference",
                "inference_level": "stated", 
                "confidence": 0.9,
                "tags": ["programming", "python"]
            },
            fact_type="mutable",
            conversation_chunk_ids=[str(chunk1.id)]
        )
        
        memory3 = Memory.objects.create(
            user_id=self.user_id,
            content="User is interested in machine learning",
            metadata={
                "entity_type": "preference",
                "inference_level": "stated",
                "confidence": 0.85,
                "tags": ["ml", "data_science"]
            },
            fact_type="mutable",
            conversation_chunk_ids=[str(chunk2.id)]
        )
        
        # Update chunks to link back to memories
        chunk1.extracted_memory_ids = [str(memory1.id), str(memory2.id)]
        chunk1.save()
        chunk2.extracted_memory_ids = [str(memory3.id)]
        chunk2.save()
        
        # Mock vector search results
        mock_vector_search.return_value = [
            {
                "chunk_id": str(chunk1.id),
                "score": 0.88,
                "content": chunk1.content,
                "extracted_memory_ids": [str(memory1.id), str(memory2.id)]
            },
            {
                "chunk_id": str(chunk2.id),
                "score": 0.75,
                "content": chunk2.content,
                "extracted_memory_ids": [str(memory3.id)]
            }
        ]
        
        # Mock graph expansion
        mock_graph_expand.return_value = {
            "expanded_memory_ids": [str(memory1.id), str(memory2.id), str(memory3.id)],
            "relationship_scores": {
                str(memory2.id): 0.8,  # Related to programming
                str(memory3.id): 0.6   # Related through data science
            }
        }
        
        # Test retrieval endpoint
        url = reverse('retrieve-memories')
        response = self.client.post(url, {
            'prompt': 'What programming languages does the user know?',
            'user_id': self.user_id
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify hybrid search response
        self.assertTrue(data['success'])
        self.assertGreater(len(data['memories']), 0)
        self.assertIn('hybrid_search_info', data)
        self.assertIn('conversation_context', data)
        
        # Verify memories have hybrid search scores
        for memory in data['memories']:
            self.assertIn('hybrid_search_score', memory)
            self.assertIn('conversation_chunk_ids', memory)
        
        # Verify conversation context information
        context = data['conversation_context']
        self.assertIn('total_sessions', context)
        self.assertIn('context_summary', context)

    @patch('memories.vector_service.VectorService.search_conversation_context')
    def test_conversation_context_expansion(self, mock_vector_search):
        """Test conversation context expansion across sessions"""
        
        now = django_timezone.now()
        
        # Create conversation chunks in different sessions
        # Session 1 - Programming discussion
        chunk1 = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="I love programming in Python",
            vector_id="vector_1",
            timestamp=now,
            metadata={"session_id": "session_1"}
        )
        
        chunk2 = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="I'm also learning JavaScript for web development",
            vector_id="vector_2",
            timestamp=now + django_timezone.timedelta(minutes=15),
            metadata={"session_id": "session_1"}
        )
        
        # Session 2 - Career discussion (1 hour later)
        chunk3 = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="I'm considering a career change to data science",
            vector_id="vector_3",
            timestamp=now + django_timezone.timedelta(hours=1, minutes=30),
            metadata={"session_id": "session_2"}
        )
        
        # Mock vector search returning chunk from session 1
        mock_vector_search.return_value = [
            {
                "chunk_id": str(chunk1.id),
                "score": 0.9,
                "content": chunk1.content,
                "timestamp": chunk1.timestamp.isoformat()
            }
        ]
        
        # Test context expansion
        expanded = self.search_service.expand_conversation_context(
            chunk_ids=[str(chunk1.id)],
            user_id=self.user_id
        )
        
        # Should include both chunks from session 1, but not session 2
        self.assertIn('conversation_context', expanded)
        context = expanded['conversation_context']
        
        # Should detect session grouping
        self.assertGreaterEqual(context['total_expanded_chunks'], 2)
        self.assertGreaterEqual(context['total_sessions'], 1)

    def test_bidirectional_linking_integrity(self):
        """Test that bidirectional linking remains consistent"""
        
        # Create memory and conversation chunk
        memory = Memory.objects.create(
            user_id=self.user_id,
            content="User likes Italian food",
            metadata={
                "entity_type": "preference",
                "confidence": 0.9
            },
            fact_type="mutable"
        )
        
        chunk = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="I absolutely love Italian cuisine, especially pasta",
            vector_id="vector_test",
            timestamp=django_timezone.now()
        )
        
        # Link memory to chunk
        memory.conversation_chunk_ids = [str(chunk.id)]
        memory.save()
        
        # Link chunk to memory
        chunk.extracted_memory_ids = [str(memory.id)]
        chunk.save()
        
        # Verify bidirectional linking
        memory.refresh_from_db()
        chunk.refresh_from_db()
        
        self.assertIn(str(chunk.id), memory.conversation_chunk_ids)
        self.assertIn(str(memory.id), chunk.extracted_memory_ids)
        
        # Test API endpoints maintain consistency
        # Get memory - should show linked chunks
        memory_url = reverse('memory-detail', kwargs={'pk': str(memory.id)})
        memory_response = self.client.get(memory_url)
        
        if memory_response.status_code == 200:
            memory_data = memory_response.json()
            self.assertIn('conversation_chunk_ids', memory_data)
        
        # Get chunk memories - should show linked memory
        chunk_url = reverse('conversation-memories', kwargs={'chunk_id': str(chunk.id)})
        chunk_response = self.client.get(chunk_url)
        
        self.assertEqual(chunk_response.status_code, 200)
        chunk_data = chunk_response.json()
        self.assertTrue(chunk_data['success'])
        self.assertEqual(len(chunk_data['memories']), 1)
        self.assertEqual(chunk_data['memories'][0]['id'], str(memory.id))

    @patch('memories.vector_service.VectorService.store_conversation_chunks')
    @patch('memories.llm_service.LLMService.extract_memories')
    def test_conversation_chunking_with_overlap(self, mock_extract, mock_vector):
        """Test conversation chunking produces appropriate overlap"""
        
        # Create long conversation
        long_conversation = (
            "I work as a software engineer at TechCorp. " * 50 +  # ~1800 chars
            "My main focus is on backend development using Python and Django. " * 30 +  # ~1800 chars
            "I also have experience with machine learning and data analysis." * 20  # ~1260 chars
        )
        
        mock_extract.return_value = {
            "success": True,
            "memories": []
        }
        
        # Mock vector service to capture chunking behavior
        def capture_chunks(*args, **kwargs):
            # This would be called with the conversation chunks
            return {
                "success": True,
                "chunk_ids": ["chunk_1", "chunk_2", "chunk_3"],
                "chunks_created": 3
            }
        
        mock_vector.side_effect = capture_chunks
        
        # Call extraction endpoint
        url = reverse('extract-memories')
        response = self.client.post(url, {
            'conversation_text': long_conversation,
            'user_id': self.user_id
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify chunking occurred
        self.assertIn('hybrid_storage', data)
        hybrid_info = data['hybrid_storage']
        self.assertGreater(hybrid_info['chunks_generated'], 1)
        
        # Check that chunks were created
        chunks = ConversationChunk.objects.filter(user_id=self.user_id)
        self.assertGreater(chunks.count(), 1)
        
        # Verify chunk content has reasonable length
        for chunk in chunks:
            self.assertLessEqual(len(chunk.content), 1200)  # Should respect chunk size
            self.assertGreater(len(chunk.content), 300)     # Should not be too small

    def test_memory_ranking_with_hybrid_scores(self):
        """Test that memory ranking incorporates hybrid search scores"""
        
        # Create memories with different characteristics
        high_conf_memory = Memory.objects.create(
            user_id=self.user_id,
            content="User works as senior software engineer",
            metadata={
                "entity_type": "fact",
                "inference_level": "stated",
                "confidence": 0.95,
                "tags": ["work", "profession"]
            },
            fact_type="immutable",
            conversation_chunk_ids=["chunk_1"]
        )
        
        medium_conf_memory = Memory.objects.create(
            user_id=self.user_id,
            content="User might be interested in blockchain",
            metadata={
                "entity_type": "preference",
                "inference_level": "inferred",
                "confidence": 0.6,
                "tags": ["technology", "blockchain"]
            },
            fact_type="mutable",
            conversation_chunk_ids=["chunk_2"]
        )
        
        # Test ranking algorithm considers multiple factors
        with patch.object(self.search_service, '_rank_and_filter_results') as mock_rank:
            mock_rank.return_value = [
                {
                    **high_conf_memory.__dict__,
                    'id': str(high_conf_memory.id),
                    'hybrid_search_score': 0.92,
                    'ranking_details': {
                        'base_score': 0.85,
                        'confidence_factor': 1.1,
                        'inference_penalty': 1.0,
                        'final_score': 0.92
                    }
                },
                {
                    **medium_conf_memory.__dict__,
                    'id': str(medium_conf_memory.id),
                    'hybrid_search_score': 0.58,
                    'ranking_details': {
                        'base_score': 0.7,
                        'confidence_factor': 0.85,
                        'inference_penalty': 0.9,
                        'final_score': 0.58
                    }
                }
            ]
            
            result = self.search_service.search_memories_with_hybrid_approach(
                prompt="software engineering work",
                user_id=self.user_id,
                limit=10
            )
            
            # Verify ranking was applied
            mock_rank.assert_called_once()
            self.assertTrue(result['success'])
            
            # Higher confidence memory should rank higher
            memories = result['memories']
            if len(memories) >= 2:
                self.assertGreaterEqual(
                    memories[0]['hybrid_search_score'],
                    memories[1]['hybrid_search_score']
                )


class GraphRelationshipIntegrationTest(TestCase):
    """Integration tests for graph relationship functionality in hybrid architecture"""

    def setUp(self):
        self.user_id = str(uuid.uuid4())
        self.graph_service = GraphService()

    @patch('memories.graph_service.GraphService._create_memory_node')
    @patch('memories.graph_service.GraphService._create_enhanced_relationships')
    def test_relationship_detection_integration(self, mock_relationships, mock_node):
        """Test that relationship detection works with real memory data"""
        
        # Create memories with potential relationships
        memory1 = Memory.objects.create(
            user_id=self.user_id,
            content="User works at Google",
            metadata={
                "entity_type": "fact",
                "inference_level": "stated",
                "confidence": 0.95
            },
            fact_type="immutable"
        )
        
        memory2 = Memory.objects.create(
            user_id=self.user_id,
            content="User is a software engineer",
            metadata={
                "entity_type": "fact",
                "inference_level": "stated",
                "confidence": 0.9
            },
            fact_type="immutable"
        )
        
        memory3 = Memory.objects.create(
            user_id=self.user_id,
            content="User likes Python programming",
            metadata={
                "entity_type": "preference",
                "inference_level": "stated",
                "confidence": 0.85
            },
            fact_type="mutable"
        )
        
        # Mock successful node creation
        mock_node.return_value = {"success": True}
        
        # Mock relationship creation to capture what relationships would be detected
        def capture_relationships(*args, **kwargs):
            # This should detect SUPPORTS relationships between work-related memories
            return {"relationships_created": 2}
        
        mock_relationships.side_effect = capture_relationships
        
        # Build graph
        result = self.graph_service.build_memory_graph(
            user_id=self.user_id,
            incremental=False
        )
        
        # Verify graph building was attempted
        self.assertTrue(result.get('success'))
        mock_node.assert_called()
        mock_relationships.assert_called()

    def test_relationship_type_detection_accuracy(self):
        """Test accuracy of different relationship type detection"""
        
        # Test CONTRADICTS relationship
        contradicts_result = self.graph_service._detect_contradicts_relationship(
            "User loves coffee",
            "User hates coffee",
            {"entity_type": "preference"},
            {"entity_type": "preference"}
        )
        self.assertTrue(contradicts_result)
        
        # Test UPDATES relationship  
        updates_result = self.graph_service._detect_updates_relationship(
            "User works at Company A",
            "User works at Company B",
            {"entity_type": "fact"},
            {"entity_type": "fact"}
        )
        self.assertTrue(updates_result)
        
        # Test SUPPORTS relationship
        supports_result = self.graph_service._detect_supports_relationship(
            "User is a software engineer",
            "User knows Python programming",
            {"entity_type": "fact"},
            {"entity_type": "skill"}
        )
        self.assertTrue(supports_result)
        
        # Test RELATES_TO relationship
        relates_result = self.graph_service._detect_relates_to_relationship(
            "User likes coffee",
            "User drinks tea",
            {"entity_type": "preference"},
            {"entity_type": "preference"}
        )
        self.assertTrue(relates_result)


if __name__ == '__main__':
    pytest.main([__file__])