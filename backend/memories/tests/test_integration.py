"""
Integration tests for Phase 3 pipeline
"""

import uuid
from unittest.mock import patch
from django.test import TestCase, Client
from django.core.cache import cache
from rest_framework import status

from memories.models import ConversationTurn, AtomicNote, NoteRelationship
from memories.conversation_service import conversation_service
from memories.settings_model import Settings


class Phase3PipelineIntegrationTest(TestCase):
    """Test full Phase 3 pipeline integration"""

    def setUp(self):
        """Set up test environment"""
        cache.clear()
        Settings.objects.all().delete()
        self.client = Client()
        self.user_id = str(uuid.uuid4())
        self.session_id = "integration-test-session"

    @patch('memories.conversation_service.llm_service.get_embeddings')
    @patch('memories.conversation_service.vector_service.store_embedding')
    def test_store_conversation_turn_api(self, mock_vector, mock_embeddings):
        """Test storing conversation turn via API"""
        # Mock embedding generation
        mock_embeddings.return_value = {
            'success': True,
            'embeddings': [[0.1] * 1024]
        }
        mock_vector.return_value = 'vector-id-1'

        # Store turn via API
        response = self.client.post(
            '/api/conversations/store/',
            data={
                'user_id': self.user_id,
                'session_id': self.session_id,
                'user_message': 'I prefer dark mode in my editor',
                'assistant_message': 'Got it, I will remember that!'
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertTrue(data['success'])
        self.assertEqual(data['turn_number'], 1)

        # Verify turn was created
        turn = ConversationTurn.objects.get(id=data['turn_id'])
        self.assertEqual(turn.user_message, 'I prefer dark mode in my editor')
        self.assertFalse(turn.extracted)  # Not extracted yet

    @patch('memories.conversation_service.llm_service.get_embeddings')
    @patch('memories.conversation_service.vector_service.store_embedding')
    def test_list_conversations_api(self, mock_vector, mock_embeddings):
        """Test listing conversations via API"""
        # Mock embeddings
        mock_embeddings.return_value = {
            'success': True,
            'embeddings': [[0.1] * 1024, [0.2] * 1024]
        }
        mock_vector.side_effect = ['vec-1', 'vec-2']

        # Create test conversations
        conversation_service.store_turn(
            user_id=self.user_id,
            session_id=self.session_id,
            user_message='First message',
            assistant_message='First response'
        )

        conversation_service.store_turn(
            user_id=self.user_id,
            session_id=self.session_id,
            user_message='Second message',
            assistant_message='Second response'
        )

        # List conversations
        response = self.client.get(
            f'/api/conversations/list/?user_id={self.user_id}&limit=10'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 2)
        self.assertEqual(len(data['conversations']), 2)

    @patch('memories.conversation_service.llm_service.get_embeddings')
    @patch('memories.conversation_service.vector_service.search_similar')
    def test_search_conversations_api(self, mock_search, mock_embeddings):
        """Test searching conversations via API"""
        # Mock embedding for query
        mock_embeddings.return_value = {
            'success': True,
            'embeddings': [[0.1] * 1024]
        }

        # Mock search results
        mock_search.return_value = {
            'success': True,
            'results': [
                {
                    'id': str(uuid.uuid4()),
                    'score': 0.95,
                    'metadata': {
                        'user_message': 'I prefer dark mode',
                        'assistant_message': 'Noted!',
                        'session_id': 'session-1',
                        'turn_number': 1,
                        'timestamp': '2025-01-01T00:00:00Z'
                    }
                }
            ]
        }

        # Search
        response = self.client.post(
            '/api/conversations/search/',
            data={
                'query': 'dark mode preferences',
                'user_id': self.user_id,
                'limit': 5,
                'mode': 'fast'
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertTrue(data['success'])
        self.assertEqual(data['mode'], 'fast')
        self.assertGreater(len(data['results']), 0)


class SettingsIntegrationTest(TestCase):
    """Test settings integration with LLM service"""

    def setUp(self):
        """Set up test environment"""
        cache.clear()
        Settings.objects.all().delete()
        self.client = Client()

    def test_settings_update_affects_generation(self):
        """Test that updating settings affects generation behavior"""
        # Get initial settings
        response = self.client.get('/api/settings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        initial = response.json()['settings']
        self.assertEqual(initial['generation_temperature'], 0.3)

        # Update generation temperature
        response = self.client.put(
            '/api/settings/update/',
            data={'generation_temperature': 0.8},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated = response.json()['settings']

        self.assertEqual(updated['generation_temperature'], 0.8)

        # Verify persistence
        response = self.client.get('/api/settings/')
        persisted = response.json()['settings']

        self.assertEqual(persisted['generation_temperature'], 0.8)

    def test_generation_config_separation(self):
        """Test that generation and embeddings can use different configs"""
        # Set up different configs
        response = self.client.put(
            '/api/settings/update/',
            data={
                'embeddings_provider': 'ollama',
                'embeddings_model': 'mxbai-embed-large',
                'generation_provider': 'openai',
                'generation_model': 'gpt-4',
                'generation_temperature': 0.5
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        settings = response.json()['settings']

        # Verify separation
        self.assertEqual(settings['embeddings_provider'], 'ollama')
        self.assertEqual(settings['embeddings_model'], 'mxbai-embed-large')
        self.assertEqual(settings['generation_provider'], 'openai')
        self.assertEqual(settings['generation_model'], 'gpt-4')


class AtomicNotesIntegrationTest(TestCase):
    """Test atomic notes and relationships integration"""

    def setUp(self):
        """Set up test environment"""
        cache.clear()
        self.user_id = uuid.uuid4()

    def test_atomic_note_creation_and_search(self):
        """Test creating atomic notes and searching them"""
        # Create test note
        note = AtomicNote.objects.create(
            user_id=self.user_id,
            content="prefers dark mode",
            note_type="preference:ui",
            context="mentioned while discussing editor preferences",
            confidence=1.0,
            tags=["ui", "dark-mode"],
            vector_id="test-vec-1"
        )

        # Verify creation
        self.assertIsNotNone(note.id)
        self.assertEqual(note.user_id, self.user_id)
        self.assertEqual(note.importance_score, 1.0)  # Default

        # Query notes
        notes = AtomicNote.objects.filter(user_id=self.user_id)
        self.assertEqual(notes.count(), 1)

    def test_note_relationships_graph(self):
        """Test building a knowledge graph with relationships"""
        # Create notes
        note1 = AtomicNote.objects.create(
            user_id=self.user_id,
            content="prefers VSCode",
            note_type="preference:editor",
            vector_id="vec-1",
            confidence=1.0
        )

        note2 = AtomicNote.objects.create(
            user_id=self.user_id,
            content="uses vim keybindings",
            note_type="preference:editor",
            vector_id="vec-2",
            confidence=1.0
        )

        note3 = AtomicNote.objects.create(
            user_id=self.user_id,
            content="prefers dark mode",
            note_type="preference:ui",
            vector_id="vec-3",
            confidence=1.0
        )

        # Create relationships
        rel1 = NoteRelationship.objects.create(
            from_note=note2,
            to_note=note1,
            relationship_type='context_for',
            strength=0.9
        )

        rel2 = NoteRelationship.objects.create(
            from_note=note3,
            to_note=note1,
            relationship_type='related_to',
            strength=0.6
        )

        # Test graph traversal - get all notes related to note1
        incoming = NoteRelationship.objects.filter(to_note=note1)
        self.assertEqual(incoming.count(), 2)

        # Get related note contents
        related_contents = [rel.from_note.content for rel in incoming]
        self.assertIn("uses vim keybindings", related_contents)
        self.assertIn("prefers dark mode", related_contents)

    def test_note_ordering_by_importance(self):
        """Test that notes are ordered by importance score"""
        # Create notes with different importance
        note1 = AtomicNote.objects.create(
            user_id=self.user_id,
            content="low importance",
            note_type="test:type",
            vector_id="vec-1",
            confidence=0.5,
            importance_score=0.5
        )

        note2 = AtomicNote.objects.create(
            user_id=self.user_id,
            content="high importance",
            note_type="test:type",
            vector_id="vec-2",
            confidence=0.9,
            importance_score=2.5
        )

        note3 = AtomicNote.objects.create(
            user_id=self.user_id,
            content="medium importance",
            note_type="test:type",
            vector_id="vec-3",
            confidence=0.7,
            importance_score=1.2
        )

        # Query with default ordering (by importance, descending)
        notes = list(AtomicNote.objects.filter(user_id=self.user_id))

        # Should be ordered: high, medium, low
        self.assertEqual(notes[0].content, "high importance")
        self.assertEqual(notes[1].content, "medium importance")
        self.assertEqual(notes[2].content, "low importance")
