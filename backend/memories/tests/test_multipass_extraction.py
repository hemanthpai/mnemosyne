"""
Tests for multi-pass extraction pipeline

Tests the two-pass extraction feature that improves recall by:
- Pass 1: Initial extraction from conversation
- Pass 2: Re-analyze with Pass 1 context to find missed notes
- Deduplication: Ensure duplicate notes across passes are caught
"""

import uuid
import json
from unittest.mock import patch
from django.test import TestCase
from django.core.cache import cache

from memories.models import ConversationTurn, AtomicNote
from memories.tasks import extract_atomic_notes
from memories.settings_model import Settings


class MultipassExtractionTest(TestCase):
    """Test multi-pass extraction for improved recall"""

    def setUp(self):
        """Set up test environment"""
        cache.clear()
        Settings.objects.all().delete()

        self.user_id = uuid.uuid4()
        self.turn = ConversationTurn.objects.create(
            user_id=self.user_id,
            session_id='test-session',
            turn_number=1,
            user_message='I prefer dark mode and I live in San Francisco',
            assistant_message='Noted!'
        )

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_pass2_triggered_when_enabled(self, mock_vec, mock_emb, mock_gen):
        """Test that Pass 2 is triggered when multipass is enabled"""
        # Enable multipass extraction
        settings = Settings.objects.create(
            embeddings_provider='ollama',
            embeddings_endpoint_url='http://localhost:11434',
            embeddings_model='nomic-embed-text',
            generation_provider='ollama',
            generation_endpoint_url='http://localhost:11434',
            generation_model='qwen2.5:3b',
            enable_multipass_extraction=True
        )

        # Mock Pass 1 and Pass 2 extraction (called before enrichment)
        mock_gen.side_effect = [
            # Pass 1: Extract one note
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "prefers dark mode",
                        "type": "preference:ui",
                        "confidence": 0.9,
                        "tags": []
                    }]
                })
            },
            # Pass 2: No additional notes
            {
                'success': True,
                'text': json.dumps({
                    "notes": []
                })
            },
            # A-MEM enrichment for Pass 1 note
            {
                'success': True,
                'text': json.dumps({
                    "keywords": ["dark mode"],
                    "tags": ["preference"],
                    "context": "User prefers dark mode"
                })
            }
        ]

        # Mock embeddings
        mock_emb.return_value = {'success': True, 'embeddings': [[0.1] * 1024]}
        mock_vec.return_value = 'vec-1'

        # Run extraction
        result = extract_atomic_notes(str(self.turn.id))

        # Verify Pass 2 was called (3 LLM calls: Pass 1, Pass 2, enrichment)
        self.assertEqual(mock_gen.call_count, 3)

        # Check Pass 2 prompt included Pass 1 facts (second call)
        pass2_call = mock_gen.call_args_list[1]
        pass2_prompt = pass2_call.kwargs['prompt']
        self.assertIn('prefers dark mode', pass2_prompt)
        self.assertIn('pass 1', pass2_prompt.lower())

        # Verify 1 note created (from Pass 1)
        self.assertEqual(result['notes_created'], 1)

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_pass2_finds_additional_notes(self, mock_vec, mock_emb, mock_gen):
        """Test that Pass 2 can find notes missed by Pass 1"""
        # Enable multipass extraction
        settings = Settings.objects.create(
            embeddings_provider='ollama',
            embeddings_endpoint_url='http://localhost:11434',
            embeddings_model='nomic-embed-text',
            generation_provider='ollama',
            generation_endpoint_url='http://localhost:11434',
            generation_model='qwen2.5:3b',
            enable_multipass_extraction=True
        )

        # Mock Pass 1 and Pass 2 (called before enrichment)
        mock_gen.side_effect = [
            # Pass 1: Extract one note
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "prefers dark mode",
                        "type": "preference:ui",
                        "confidence": 0.9,
                        "tags": []
                    }]
                })
            },
            # Pass 2: Find additional note
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "lives in San Francisco",
                        "type": "personal:location",
                        "confidence": 0.85,
                        "tags": []
                    }]
                })
            },
            # A-MEM enrichment for note 1
            {
                'success': True,
                'text': json.dumps({
                    "keywords": ["dark mode"],
                    "tags": ["preference"],
                    "context": "User prefers dark mode"
                })
            },
            # A-MEM enrichment for note 2
            {
                'success': True,
                'text': json.dumps({
                    "keywords": ["San Francisco", "location"],
                    "tags": ["personal", "location"],
                    "context": "User lives in San Francisco"
                })
            }
        ]

        # Mock embeddings
        mock_emb.return_value = {'success': True, 'embeddings': [[0.1] * 1024]}
        # Return different vector IDs for each note
        mock_vec.side_effect = ['vec-1', 'vec-2']

        # Run extraction
        result = extract_atomic_notes(str(self.turn.id))

        # Verify 2 notes created (1 from Pass 1, 1 from Pass 2)
        self.assertEqual(result['notes_created'], 2)

        # Verify both notes exist
        notes = AtomicNote.objects.filter(user_id=self.user_id)
        self.assertEqual(notes.count(), 2)

        # Check we have both notes
        contents = [n.content for n in notes]
        self.assertIn('prefers dark mode', contents)
        self.assertIn('lives in San Francisco', contents)

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_deduplication_across_passes(self, mock_vec, mock_emb, mock_gen):
        """Test that duplicate notes across passes are caught"""
        # Enable multipass extraction
        settings = Settings.objects.create(
            embeddings_provider='ollama',
            embeddings_endpoint_url='http://localhost:11434',
            embeddings_model='nomic-embed-text',
            generation_provider='ollama',
            generation_endpoint_url='http://localhost:11434',
            generation_model='qwen2.5:3b',
            enable_multipass_extraction=True
        )

        # Mock Pass 1 and Pass 2 to return same note (duplicate)
        mock_gen.side_effect = [
            # Pass 1: Extract one note
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "prefers dark mode",
                        "type": "preference:ui",
                        "confidence": 0.9,
                        "tags": []
                    }]
                })
            },
            # Pass 2: Return same note (duplicate)
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "prefers dark mode",  # Duplicate!
                        "type": "preference:ui",
                        "confidence": 0.95,
                        "tags": []
                    }]
                })
            },
            # A-MEM enrichment (only one note, duplicate was filtered out)
            {
                'success': True,
                'text': json.dumps({
                    "keywords": ["dark mode"],
                    "tags": ["preference"],
                    "context": "User prefers dark mode"
                })
            }
        ]

        # Mock embeddings
        mock_emb.return_value = {'success': True, 'embeddings': [[0.1] * 1024]}
        mock_vec.return_value = 'vec-1'

        # Run extraction
        result = extract_atomic_notes(str(self.turn.id))

        # Verify only 1 note created (duplicate was skipped)
        self.assertEqual(result['notes_created'], 1)

        # Verify only one instance in database
        notes = AtomicNote.objects.filter(user_id=self.user_id)
        self.assertEqual(notes.count(), 1)
        self.assertEqual(notes.first().content, 'prefers dark mode')

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_pass2_skipped_when_disabled(self, mock_vec, mock_emb, mock_gen):
        """Test that Pass 2 is NOT called when multipass is disabled"""
        # Disable multipass extraction
        settings = Settings.objects.create(
            embeddings_provider='ollama',
            embeddings_endpoint_url='http://localhost:11434',
            embeddings_model='nomic-embed-text',
            generation_provider='ollama',
            generation_endpoint_url='http://localhost:11434',
            generation_model='qwen2.5:3b',
            enable_multipass_extraction=False  # Disabled!
        )

        # Mock Pass 1 only
        mock_gen.side_effect = [
            # Pass 1: Extract one note
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "prefers dark mode",
                        "type": "preference:ui",
                        "confidence": 0.9,
                        "tags": []
                    }]
                })
            },
            # A-MEM enrichment
            {
                'success': True,
                'text': json.dumps({
                    "keywords": ["dark mode"],
                    "tags": ["preference"],
                    "context": "User prefers dark mode"
                })
            }
            # No Pass 2!
        ]

        # Mock embeddings
        mock_emb.return_value = {'success': True, 'embeddings': [[0.1] * 1024]}
        mock_vec.return_value = 'vec-1'

        # Run extraction
        result = extract_atomic_notes(str(self.turn.id))

        # Verify Pass 2 was NOT called (only 2 LLM calls: Pass 1 and enrichment)
        self.assertEqual(mock_gen.call_count, 2)

        # Verify 1 note created
        self.assertEqual(result['notes_created'], 1)

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_pass2_continues_on_llm_failure(self, mock_vec, mock_emb, mock_gen):
        """Test that Pass 1 notes are still stored if Pass 2 LLM fails"""
        # Enable multipass extraction
        settings = Settings.objects.create(
            embeddings_provider='ollama',
            embeddings_endpoint_url='http://localhost:11434',
            embeddings_model='nomic-embed-text',
            generation_provider='ollama',
            generation_endpoint_url='http://localhost:11434',
            generation_model='qwen2.5:3b',
            enable_multipass_extraction=True
        )

        # Mock Pass 1 to succeed, Pass 2 to fail
        mock_gen.side_effect = [
            # Pass 1: Extract one note
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "prefers dark mode",
                        "type": "preference:ui",
                        "confidence": 0.9,
                        "tags": []
                    }]
                })
            },
            # Pass 2: LLM fails
            {
                'success': False,
                'error': 'LLM timeout'
            },
            # A-MEM enrichment (still runs for Pass 1 note)
            {
                'success': True,
                'text': json.dumps({
                    "keywords": ["dark mode"],
                    "tags": ["preference"],
                    "context": "User prefers dark mode"
                })
            }
        ]

        # Mock embeddings
        mock_emb.return_value = {'success': True, 'embeddings': [[0.1] * 1024]}
        mock_vec.return_value = 'vec-1'

        # Run extraction
        result = extract_atomic_notes(str(self.turn.id))

        # Verify extraction still marked successful
        self.assertEqual(result['status'], 'completed')

        # Verify Pass 1 note was still created
        self.assertEqual(result['notes_created'], 1)

        # Verify note exists in database
        notes = AtomicNote.objects.filter(user_id=self.user_id)
        self.assertEqual(notes.count(), 1)
        self.assertEqual(notes.first().content, 'prefers dark mode')
