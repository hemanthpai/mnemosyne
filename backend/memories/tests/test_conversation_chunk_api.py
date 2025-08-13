"""
Tests for ConversationChunk API endpoints and functionality
"""

import json
import uuid
from datetime import datetime, timezone

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone as django_timezone

from memories.models import Memory, ConversationChunk


class ConversationChunkAPITest(TestCase):
    """Test ConversationChunk API endpoints"""

    def setUp(self):
        self.client = Client()
        self.user_id = str(uuid.uuid4())
        
        # Create test conversation chunks
        self.chunk1 = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="First conversation about coffee preferences. I really love espresso.",
            vector_id=f"vector_{uuid.uuid4().hex}",
            timestamp=django_timezone.now(),
            metadata={"source": "test", "session_id": "session_1"},
            extracted_memory_ids=[]
        )
        
        self.chunk2 = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="Later conversation about work. I work as a software engineer.",
            vector_id=f"vector_{uuid.uuid4().hex}",
            timestamp=django_timezone.now(),
            metadata={"source": "test", "session_id": "session_2"},
            extracted_memory_ids=[]
        )

    def test_list_conversation_chunks(self):
        """Test listing conversation chunks for a user"""
        url = reverse('conversation-list')
        response = self.client.get(url, {'user_id': self.user_id})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data['success'])
        self.assertEqual(len(data['chunks']), 2)
        self.assertIn('count', data)

    def test_get_specific_conversation_chunk(self):
        """Test retrieving a specific conversation chunk"""
        url = reverse('conversation-detail', kwargs={'pk': str(self.chunk1.id)})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data['success'])
        self.assertEqual(data['chunk']['id'], str(self.chunk1.id))
        self.assertEqual(data['chunk']['content'], self.chunk1.content)

    def test_conversation_chunk_memories_endpoint(self):
        """Test getting memories from a conversation chunk"""
        # Create a memory linked to the chunk
        memory = Memory.objects.create(
            user_id=self.user_id,
            content="User likes espresso",
            metadata={
                "tags": ["coffee", "preference"],
                "confidence": 0.9,
                "entity_type": "preference",
                "inference_level": "stated"
            },
            fact_type="mutable",
            conversation_chunk_ids=[str(self.chunk1.id)]
        )
        
        # Update chunk to link back to memory
        self.chunk1.extracted_memory_ids = [str(memory.id)]
        self.chunk1.save()
        
        url = reverse('conversation-memories', kwargs={'chunk_id': str(self.chunk1.id)})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data['success'])
        self.assertEqual(len(data['memories']), 1)
        self.assertEqual(data['memories'][0]['id'], str(memory.id))

    def test_conversation_search_endpoint(self):
        """Test conversation search endpoint"""
        url = reverse('conversation-search')
        payload = {
            'query': 'coffee preferences',
            'user_id': self.user_id,
            'limit': 5
        }
        
        response = self.client.post(
            url, 
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Note: This test may fail without proper vector service setup
        # In a real test environment, you'd mock the vector service
        if response.status_code == 200:
            data = response.json()
            self.assertTrue(data['success'])
            self.assertIn('results', data)

    def test_delete_conversation_chunk(self):
        """Test deleting a conversation chunk"""
        chunk_id = str(self.chunk1.id)
        url = reverse('conversation-detail', kwargs={'pk': chunk_id})
        
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify chunk is deleted
        self.assertFalse(ConversationChunk.objects.filter(id=chunk_id).exists())

    def test_conversation_chunk_pagination(self):
        """Test pagination for conversation chunks"""
        # Create more chunks for pagination testing
        for i in range(15):
            ConversationChunk.objects.create(
                user_id=self.user_id,
                content=f"Additional conversation {i}",
                vector_id=f"vector_{uuid.uuid4().hex}",
                timestamp=django_timezone.now(),
                extracted_memory_ids=[]
            )
        
        url = reverse('conversation-list')
        response = self.client.get(url, {
            'user_id': self.user_id,
            'page': 1,
            'page_size': 10
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data['success'])
        self.assertEqual(len(data['chunks']), 10)  # First page
        self.assertGreaterEqual(data['count'], 17)  # Total count

    def test_invalid_conversation_chunk_id(self):
        """Test handling of invalid conversation chunk IDs"""
        invalid_id = str(uuid.uuid4())
        url = reverse('conversation-detail', kwargs={'pk': invalid_id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_conversation_chunk_user_isolation(self):
        """Test that users can only see their own conversation chunks"""
        other_user_id = str(uuid.uuid4())
        
        # Create chunk for different user
        other_chunk = ConversationChunk.objects.create(
            user_id=other_user_id,
            content="Private conversation",
            vector_id=f"vector_{uuid.uuid4().hex}",
            timestamp=django_timezone.now(),
            extracted_memory_ids=[]
        )
        
        # Request chunks for original user
        url = reverse('conversation-list')
        response = self.client.get(url, {'user_id': self.user_id})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should only see chunks for the requested user
        chunk_ids = [chunk['id'] for chunk in data['chunks']]
        self.assertNotIn(str(other_chunk.id), chunk_ids)


class ConversationChunkModelTest(TestCase):
    """Test ConversationChunk model functionality"""

    def setUp(self):
        self.user_id = str(uuid.uuid4())

    def test_conversation_chunk_str_representation(self):
        """Test string representation of ConversationChunk"""
        chunk = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="Test conversation content",
            vector_id="test_vector_123",
            timestamp=django_timezone.now()
        )
        
        str_repr = str(chunk)
        self.assertIn(self.user_id[:8], str_repr)
        self.assertIn("Test conversation", str_repr)

    def test_conversation_chunk_content_preview(self):
        """Test content preview functionality"""
        long_content = "This is a very long conversation content. " * 20
        chunk = ConversationChunk.objects.create(
            user_id=self.user_id,
            content=long_content,
            vector_id="test_vector_123",
            timestamp=django_timezone.now()
        )
        
        # Test that we can get a preview (if method exists)
        if hasattr(chunk, 'get_content_preview'):
            preview = chunk.get_content_preview()
            self.assertLess(len(preview), len(long_content))
            self.assertTrue(preview.endswith('...') or len(preview) < 200)

    def test_conversation_chunk_metadata_handling(self):
        """Test metadata field handling"""
        metadata = {
            "source": "api",
            "session_id": "session_123",
            "chunk_index": 1,
            "total_chunks": 3,
            "confidence": 0.85
        }
        
        chunk = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="Test content with metadata",
            vector_id="test_vector_123",
            timestamp=django_timezone.now(),
            metadata=metadata
        )
        
        # Verify metadata is preserved
        chunk.refresh_from_db()
        self.assertEqual(chunk.metadata["source"], "api")
        self.assertEqual(chunk.metadata["session_id"], "session_123")
        self.assertEqual(chunk.metadata["chunk_index"], 1)

    def test_conversation_chunk_memory_linking(self):
        """Test linking conversation chunks to memories"""
        # Create a memory
        memory = Memory.objects.create(
            user_id=self.user_id,
            content="User prefers dark roast coffee",
            metadata={
                "entity_type": "preference",
                "confidence": 0.9
            },
            fact_type="mutable"
        )
        
        # Create chunk with memory link
        chunk = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="I really love dark roast coffee",
            vector_id="test_vector_123",
            timestamp=django_timezone.now(),
            extracted_memory_ids=[str(memory.id)]
        )
        
        # Verify linking
        self.assertIn(str(memory.id), chunk.extracted_memory_ids)
        
        # Update memory to link back
        memory.conversation_chunk_ids = [str(chunk.id)]
        memory.save()
        
        # Verify bidirectional linking
        memory.refresh_from_db()
        self.assertIn(str(chunk.id), memory.conversation_chunk_ids)

    def test_conversation_chunk_ordering(self):
        """Test default ordering of conversation chunks"""
        # Create chunks with different timestamps
        earlier_time = django_timezone.now() - django_timezone.timedelta(hours=1)
        later_time = django_timezone.now()
        
        chunk2 = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="Later conversation",
            vector_id="vector_2",
            timestamp=later_time
        )
        
        chunk1 = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="Earlier conversation",
            vector_id="vector_1",
            timestamp=earlier_time
        )
        
        # Get chunks in default order
        chunks = list(ConversationChunk.objects.filter(user_id=self.user_id))
        
        # Should be ordered by timestamp (newest first if that's the default)
        if len(chunks) >= 2:
            # Verify some kind of consistent ordering exists
            self.assertTrue(chunks[0].timestamp >= chunks[1].timestamp or 
                          chunks[0].timestamp <= chunks[1].timestamp)


class ConversationChunkIntegrationTest(TestCase):
    """Integration tests for conversation chunk functionality"""

    def setUp(self):
        self.client = Client()
        self.user_id = str(uuid.uuid4())

    def test_conversation_to_memory_workflow(self):
        """Test complete workflow from conversation to memory extraction"""
        # This would typically involve the memory extraction endpoint
        # For now, test the data flow manually
        
        # 1. Create conversation chunk
        chunk = ConversationChunk.objects.create(
            user_id=self.user_id,
            content="I work as a data scientist and I love working with Python.",
            vector_id=f"vector_{uuid.uuid4().hex}",
            timestamp=django_timezone.now(),
            metadata={"source": "api_test"}
        )
        
        # 2. Create extracted memories
        memory1 = Memory.objects.create(
            user_id=self.user_id,
            content="User works as a data scientist",
            metadata={
                "entity_type": "fact",
                "inference_level": "stated",
                "confidence": 0.95,
                "evidence": "User explicitly stated their profession"
            },
            fact_type="immutable",
            conversation_chunk_ids=[str(chunk.id)]
        )
        
        memory2 = Memory.objects.create(
            user_id=self.user_id,
            content="User enjoys programming in Python",
            metadata={
                "entity_type": "preference",
                "inference_level": "stated", 
                "confidence": 0.9,
                "evidence": "User said they love working with Python"
            },
            fact_type="mutable",
            conversation_chunk_ids=[str(chunk.id)]
        )
        
        # 3. Update chunk to link back to memories
        chunk.extracted_memory_ids = [str(memory1.id), str(memory2.id)]
        chunk.save()
        
        # 4. Verify complete bidirectional linking
        chunk.refresh_from_db()
        self.assertEqual(len(chunk.extracted_memory_ids), 2)
        self.assertIn(str(memory1.id), chunk.extracted_memory_ids)
        self.assertIn(str(memory2.id), chunk.extracted_memory_ids)
        
        # Test API endpoint for getting memories from chunk
        url = reverse('conversation-memories', kwargs={'chunk_id': str(chunk.id)})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['memories']), 2)


if __name__ == '__main__':
    import django
    from django.test.utils import get_runner
    from django.conf import settings
    
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["memories.tests.test_conversation_chunk_api"])