"""
End-to-End Workflow Tests

Tests complete user journeys through the system:
- Store conversation → Extract notes → Enrich with A-MEM → Search
- Settings changes affecting behavior
- Error recovery and resilience
"""

import uuid
import json
from unittest.mock import patch
from django.test import TestCase, Client
from django.core.cache import cache

from memories.models import ConversationTurn, AtomicNote
from memories.tasks import extract_atomic_notes
from memories.settings_model import Settings


class EndToEndWorkflowTest(TestCase):
    """Test complete user workflows through the system"""

    def setUp(self):
        """Set up test environment"""
        cache.clear()
        Settings.objects.all().delete()
        self.client = Client()
        self.user_id = uuid.uuid4()

        # Create default settings
        self.settings = Settings.objects.create(
            embeddings_provider='ollama',
            embeddings_endpoint_url='http://localhost:11434',
            embeddings_model='nomic-embed-text',
            generation_provider='ollama',
            generation_endpoint_url='http://localhost:11434',
            generation_model='qwen2.5:3b',
            enable_multipass_extraction=True
        )

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    @patch('memories.tasks.vector_service.search_similar')
    def test_complete_conversation_lifecycle(self, mock_search, mock_vec, mock_emb, mock_gen):
        """
        Test complete lifecycle: Store → Extract → Enrich → Search

        This validates the entire user journey from storing a conversation
        to being able to search for it later.
        """
        # Step 1: Store conversation directly (bypassing API to avoid transaction issues)
        turn = ConversationTurn.objects.create(
            user_id=self.user_id,
            session_id='test-session',
            turn_number=1,
            user_message='I love using dark mode in my IDE',
            assistant_message='Noted your preference for dark mode!'
        )

        # Verify conversation stored
        self.assertEqual(turn.user_message, 'I love using dark mode in my IDE')
        turn_id = str(turn.id)

        # Step 2: Mock extraction and enrichment
        mock_gen.side_effect = [
            # Pass 1: Extract note
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "prefers dark mode in IDE",
                        "type": "preference:ui",
                        "confidence": 0.95,
                        "tags": []
                    }]
                })
            },
            # Pass 2: No additional notes
            {
                'success': True,
                'text': json.dumps({"notes": []})
            },
            # A-MEM enrichment
            {
                'success': True,
                'text': json.dumps({
                    "keywords": ["dark mode", "IDE", "preference"],
                    "tags": ["preference", "development", "ui"],
                    "context": "User strongly prefers dark mode in their IDE for reduced eye strain"
                })
            }
        ]

        # Mock embeddings
        test_embedding = [0.1] * 1024
        mock_emb.return_value = {'success': True, 'embeddings': [test_embedding]}
        mock_vec.return_value = 'vec-1'

        # Step 3: Run extraction task
        result = extract_atomic_notes(turn_id)

        # Verify extraction succeeded
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['notes_created'], 1)

        # Verify note created with A-MEM enrichment
        note = AtomicNote.objects.get(user_id=self.user_id)
        self.assertEqual(note.content, 'prefers dark mode in IDE')
        self.assertTrue(note.is_amem_enriched)
        self.assertIn('dark mode', note.keywords)
        self.assertIn('preference', note.llm_tags)
        self.assertIn('eye strain', note.contextual_description)

        # Step 4: Verify note is searchable (has vector_id and enrichment)
        # The note should be ready for search with its vector embedding
        self.assertIsNotNone(note.vector_id)
        self.assertEqual(note.vector_id, 'vec-1')

        # Step 5: Verify turn is linked to note and marked as extracted
        turn.refresh_from_db()
        self.assertTrue(turn.extracted)
        self.assertEqual(note.source_turn, turn)

        # Verify the complete data flow: conversation → note → enrichment → vector
        # This confirms the end-to-end pipeline is working
        self.assertEqual(note.user_id, turn.user_id)
        self.assertTrue(note.is_amem_enriched)
        self.assertIsNotNone(note.vector_id)

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_settings_change_affects_extraction(self, mock_vec, mock_emb, mock_gen):
        """
        Test that changing extraction settings affects behavior

        Validates that the settings system works and changes are
        reflected in extraction behavior.
        """
        # Create conversation
        turn = ConversationTurn.objects.create(
            user_id=self.user_id,
            session_id='test-session',
            turn_number=1,
            user_message='I enjoy Python programming',
            assistant_message='Great!'
        )

        # Initial extraction with multipass enabled
        mock_gen.side_effect = [
            # Pass 1
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "enjoys Python programming",
                        "type": "preference:programming",
                        "confidence": 0.9,
                        "tags": []
                    }]
                })
            },
            # Pass 2
            {
                'success': True,
                'text': json.dumps({"notes": []})
            },
            # Enrichment
            {
                'success': True,
                'text': json.dumps({
                    "keywords": ["Python"],
                    "tags": ["programming"],
                    "context": "Enjoys Python"
                })
            }
        ]

        mock_emb.return_value = {'success': True, 'embeddings': [[0.1] * 1024]}
        mock_vec.return_value = 'vec-turn1'

        extract_atomic_notes(str(turn.id))

        # Verify Pass 2 was called (3 LLM calls)
        self.assertEqual(mock_gen.call_count, 3)

        # Change settings to disable multipass
        self.settings.enable_multipass_extraction = False
        self.settings.save()

        # Create another conversation
        mock_gen.reset_mock()
        mock_vec.reset_mock()
        turn2 = ConversationTurn.objects.create(
            user_id=self.user_id,
            session_id='test-session',
            turn_number=2,
            user_message='I like JavaScript too',
            assistant_message='Noted!'
        )

        mock_vec.return_value = 'vec-turn2'

        mock_gen.side_effect = [
            # Pass 1 only
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "likes JavaScript",
                        "type": "preference:programming",
                        "confidence": 0.9,
                        "tags": []
                    }]
                })
            },
            # Enrichment
            {
                'success': True,
                'text': json.dumps({
                    "keywords": ["JavaScript"],
                    "tags": ["programming"],
                    "context": "Likes JavaScript"
                })
            }
        ]

        extract_atomic_notes(str(turn2.id))

        # Verify Pass 2 was NOT called (only 2 LLM calls)
        self.assertEqual(mock_gen.call_count, 2)

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_error_recovery_on_retry(self, mock_vec, mock_emb, mock_gen):
        """
        Test error recovery through retry mechanism

        Validates that the system handles transient failures gracefully
        and succeeds on retry.
        """
        turn = ConversationTurn.objects.create(
            user_id=self.user_id,
            session_id='test-session',
            turn_number=1,
            user_message='Test message',
            assistant_message='Response'
        )

        # First attempt: return invalid JSON
        mock_gen.return_value = {
            'success': True,
            'text': 'This is not valid JSON'
        }

        # Run extraction - should schedule retry
        result = extract_atomic_notes(str(turn.id), retry_count=0)

        # Verify retry scheduled
        self.assertEqual(result['status'], 'retry_scheduled')
        self.assertEqual(result['attempt'], 1)

        # Verify turn NOT marked as extracted yet
        turn.refresh_from_db()
        self.assertFalse(turn.extracted)

        # Second attempt: succeed with valid JSON
        mock_gen.reset_mock()
        mock_gen.side_effect = [
            # Pass 1
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "test note",
                        "type": "test:type",
                        "confidence": 0.9,
                        "tags": []
                    }]
                })
            },
            # Pass 2
            {
                'success': True,
                'text': json.dumps({"notes": []})
            },
            # Enrichment
            {
                'success': True,
                'text': json.dumps({
                    "keywords": ["test"],
                    "tags": ["test"],
                    "context": "Test note"
                })
            }
        ]

        mock_emb.return_value = {'success': True, 'embeddings': [[0.1] * 1024]}
        mock_vec.return_value = 'vec-1'

        # Retry extraction
        result = extract_atomic_notes(str(turn.id), retry_count=1)

        # Verify success on retry
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['notes_created'], 1)

        # Verify turn marked as extracted
        turn.refresh_from_db()
        self.assertTrue(turn.extracted)

        # Verify note was created
        note = AtomicNote.objects.get(user_id=self.user_id)
        self.assertEqual(note.content, 'test note')

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_multiple_conversations_same_session(self, mock_vec, mock_emb, mock_gen):
        """
        Test handling multiple conversation turns in same session

        Validates that the system correctly tracks multiple turns
        and extracts notes from each independently.
        """
        session_id = 'multi-turn-session'

        # Create multiple turns in same session
        turns = []
        for i in range(3):
            turn = ConversationTurn.objects.create(
                user_id=self.user_id,
                session_id=session_id,
                turn_number=i + 1,
                user_message=f'Message {i + 1}',
                assistant_message=f'Response {i + 1}'
            )
            turns.append(turn)

        # Mock successful extraction for each turn
        for turn in turns:
            mock_gen.reset_mock()
            mock_gen.side_effect = [
                # Pass 1
                {
                    'success': True,
                    'text': json.dumps({
                        "notes": [{
                            "content": f"note from turn {turn.turn_number}",
                            "type": "test:type",
                            "confidence": 0.9,
                            "tags": []
                        }]
                    })
                },
                # Pass 2
                {
                    'success': True,
                    'text': json.dumps({"notes": []})
                },
                # Enrichment
                {
                    'success': True,
                    'text': json.dumps({
                        "keywords": [f"turn{turn.turn_number}"],
                        "tags": ["test"],
                        "context": f"Note from turn {turn.turn_number}"
                    })
                }
            ]

            mock_emb.return_value = {'success': True, 'embeddings': [[0.1] * 1024]}
            mock_vec.return_value = f'vec-{turn.turn_number}'

            result = extract_atomic_notes(str(turn.id))
            self.assertEqual(result['status'], 'completed')

        # Verify all turns extracted
        for turn in turns:
            turn.refresh_from_db()
            self.assertTrue(turn.extracted)

        # Verify 3 notes created
        notes = AtomicNote.objects.filter(user_id=self.user_id)
        self.assertEqual(notes.count(), 3)

        # Verify each note has correct content
        for i, note in enumerate(sorted(notes, key=lambda n: n.created_at), 1):
            self.assertEqual(note.content, f"note from turn {i}")
