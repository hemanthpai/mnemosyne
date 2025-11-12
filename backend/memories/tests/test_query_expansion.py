"""
Query Expansion Tests

Tests the query expansion feature that improves search recall by:
- Expanding abstract queries into concrete variations
- Searching with multiple query variations
- Aggregating and deduplicating results
"""

import uuid
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache

from memories.models import AtomicNote, ConversationTurn
from memories.graph_service import graph_service
from memories.settings_model import Settings


class QueryExpansionTest(TestCase):
    """Test query expansion for improved search recall"""

    def setUp(self):
        """Set up test environment"""
        cache.clear()
        Settings.objects.all().delete()

        self.user_id = uuid.uuid4()

        # Create test notes
        turn = ConversationTurn.objects.create(
            user_id=self.user_id,
            session_id='test-session',
            turn_number=1,
            user_message='Test',
            assistant_message='Response'
        )

        self.note1 = AtomicNote.objects.create(
            user_id=self.user_id,
            content='prefers dark mode in IDE',
            note_type='preference:ui',
            vector_id='vec-1',
            source_turn=turn
        )

        self.note2 = AtomicNote.objects.create(
            user_id=self.user_id,
            content='uses vim keybindings',
            note_type='preference:editor',
            vector_id='vec-2',
            source_turn=turn
        )

    @patch('memories.graph_service.llm_service.generate_text')
    @patch('memories.graph_service.llm_service.get_embeddings')
    @patch('memories.graph_service.vector_service.search_similar')
    def test_query_expansion_when_enabled(self, mock_search, mock_emb, mock_gen):
        """Test that query expansion works when enabled"""
        # Enable query expansion
        settings = Settings.objects.create(
            embeddings_provider='ollama',
            embeddings_endpoint_url='http://localhost:11434',
            embeddings_model='nomic-embed-text',
            generation_provider='ollama',
            generation_endpoint_url='http://localhost:11434',
            generation_model='qwen2.5:3b',
            enable_query_expansion=True
        )

        # Mock LLM to return query variations
        mock_gen.return_value = {
            'success': True,
            'text': json.dumps({
                "variations": [
                    "dark mode preferences",
                    "dark theme settings",
                    "black background preference"
                ]
            })
        }

        # Mock embeddings for each variation
        mock_emb.return_value = {
            'success': True,
            'embeddings': [[0.1] * 1024]
        }

        # Mock search to return different results for each variation (original + 3 variations = 4)
        mock_search.side_effect = [
            # Original query: dark theme
            [{
                'id': 'vec-1',
                'score': 0.95,
                'metadata': {
                    'note_id': str(self.note1.id),
                    'type': 'atomic_note',
                    'note_type': 'preference:ui'
                }
            }],
            # Variation 1: dark mode preferences
            [{
                'id': 'vec-1',
                'score': 0.92,
                'metadata': {
                    'note_id': str(self.note1.id),
                    'type': 'atomic_note',
                    'note_type': 'preference:ui'
                }
            }],
            # Variation 2: dark theme settings
            [{
                'id': 'vec-1',
                'score': 0.88,
                'metadata': {
                    'note_id': str(self.note1.id),
                    'type': 'atomic_note',
                    'note_type': 'preference:ui'
                }
            }],
            # Variation 3: black background preference
            [{
                'id': 'vec-2',
                'score': 0.75,
                'metadata': {
                    'note_id': str(self.note2.id),
                    'type': 'atomic_note',
                    'note_type': 'preference:editor'
                }
            }]
        ]

        # Search with expansion
        results = graph_service.search_atomic_notes_with_expansion(
            query='dark theme',
            user_id=str(self.user_id),
            limit=10
        )

        # Verify LLM was called for expansion
        self.assertEqual(mock_gen.call_count, 1)
        expansion_call = mock_gen.call_args
        self.assertIn('dark theme', expansion_call.kwargs['prompt'])

        # Verify embeddings were generated for each variation (original + 3 variations = 4)
        self.assertEqual(mock_emb.call_count, 4)

        # Verify search was called for each variation (original + 3 variations = 4)
        self.assertEqual(mock_search.call_count, 4)

        # Verify results were deduplicated (note1 appears twice, should be deduplicated)
        # and aggregated
        self.assertGreaterEqual(len(results), 1)

    @patch('memories.graph_service.llm_service.get_embeddings')
    @patch('memories.graph_service.vector_service.search_similar')
    def test_query_expansion_disabled(self, mock_search, mock_emb):
        """Test that query expansion is skipped when disabled"""
        # Disable query expansion
        settings = Settings.objects.create(
            embeddings_provider='ollama',
            embeddings_endpoint_url='http://localhost:11434',
            embeddings_model='nomic-embed-text',
            enable_query_expansion=False
        )

        # Mock embeddings
        mock_emb.return_value = {
            'success': True,
            'embeddings': [[0.1] * 1024]
        }

        # Mock search
        mock_search.return_value = [{
            'id': 'vec-1',
            'score': 0.92,
            'metadata': {
                'note_id': str(self.note1.id),
                'type': 'atomic_note',
                'note_type': 'preference:ui'
            }
        }]

        # Search without expansion (use_expansion=False)
        results = graph_service.search_atomic_notes_with_expansion(
            query='dark theme',
            user_id=str(self.user_id),
            limit=10,
            use_expansion=False
        )

        # Verify only one embedding was generated (original query)
        self.assertEqual(mock_emb.call_count, 1)

        # Verify only one search was performed
        self.assertEqual(mock_search.call_count, 1)

        # Verify results returned
        self.assertGreater(len(results), 0)

    @patch('memories.graph_service.llm_service.generate_text')
    def test_expand_query_returns_variations(self, mock_gen):
        """Test that expand_query generates multiple query variations"""
        settings = Settings.objects.create(
            generation_provider='ollama',
            generation_endpoint_url='http://localhost:11434',
            generation_model='qwen2.5:3b'
        )

        # Mock LLM to return variations
        mock_gen.return_value = {
            'success': True,
            'text': json.dumps({
                "variations": [
                    "Python programming",
                    "Python development",
                    "Python coding",
                    "Python software engineering"
                ]
            })
        }

        # Expand query
        variations = graph_service.expand_query('Python')

        # Verify LLM was called
        self.assertEqual(mock_gen.call_count, 1)

        # Verify variations returned
        self.assertIsInstance(variations, list)
        self.assertGreater(len(variations), 0)

        # Original query should be included
        self.assertIn('Python', variations)

        # Variations should be included
        self.assertIn('Python programming', variations)

    @patch('memories.graph_service.llm_service.generate_text')
    @patch('memories.graph_service.llm_service.get_embeddings')
    @patch('memories.graph_service.vector_service.search_similar')
    def test_expansion_fallback_on_llm_failure(self, mock_search, mock_emb, mock_gen):
        """Test that expansion falls back to original query when LLM fails"""
        settings = Settings.objects.create(
            embeddings_provider='ollama',
            embeddings_endpoint_url='http://localhost:11434',
            embeddings_model='nomic-embed-text',
            generation_provider='ollama',
            generation_endpoint_url='http://localhost:11434',
            generation_model='qwen2.5:3b',
            enable_query_expansion=True
        )

        # Mock LLM to fail
        mock_gen.return_value = {
            'success': False,
            'error': 'LLM timeout'
        }

        # Mock embeddings
        mock_emb.return_value = {
            'success': True,
            'embeddings': [[0.1] * 1024]
        }

        # Mock search
        mock_search.return_value = [{
            'id': 'vec-1',
            'score': 0.92,
            'metadata': {
                'note_id': str(self.note1.id),
                'type': 'atomic_note',
                'note_type': 'preference:ui'
            }
        }]

        # Search with expansion (should fall back to original query)
        results = graph_service.search_atomic_notes_with_expansion(
            query='dark theme',
            user_id=str(self.user_id),
            limit=10
        )

        # Verify LLM was called for expansion
        self.assertEqual(mock_gen.call_count, 1)

        # Verify search still happened with original query (fallback)
        self.assertEqual(mock_search.call_count, 1)

        # Verify results returned (using fallback)
        self.assertGreater(len(results), 0)

    @patch('memories.graph_service.llm_service.generate_text')
    def test_expand_query_handles_invalid_json(self, mock_gen):
        """Test that expand_query handles invalid JSON from LLM"""
        settings = Settings.objects.create(
            generation_provider='ollama',
            generation_endpoint_url='http://localhost:11434',
            generation_model='qwen2.5:3b'
        )

        # Mock LLM to return invalid JSON
        mock_gen.return_value = {
            'success': True,
            'text': 'This is not valid JSON'
        }

        # Expand query
        variations = graph_service.expand_query('test query')

        # Verify fallback to original query only
        self.assertEqual(variations, ['test query'])
