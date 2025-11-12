"""
Tests for A-MEM (Agentic Memory) enrichment pipeline

Tests the enrichment of atomic notes with:
- Keywords (Ki): Key concepts extracted from the note
- Tags (Gi): Broad categories for classification
- Contextual Description (Xi): Richer context for the note
- Multi-attribute embeddings: Combining all attributes for better search

Based on "Empowering Agentic Memory with Event Stream Modelling" (NeurIPS 2025)
"""

import uuid
import json
from unittest.mock import Mock, patch, call
from django.test import TestCase
from django.core.cache import cache

from memories.models import ConversationTurn, AtomicNote
from memories.tasks import extract_atomic_notes
from memories.settings_model import Settings


class AmemEnrichmentTest(TestCase):
    """Test A-MEM enrichment pipeline"""

    def setUp(self):
        """Set up test environment"""
        cache.clear()
        Settings.objects.all().delete()

        # Create settings with A-MEM enabled
        self.settings = Settings.objects.create(
            embeddings_provider='ollama',
            embeddings_endpoint_url='http://localhost:11434',
            embeddings_model='nomic-embed-text',
            generation_provider='ollama',
            generation_endpoint_url='http://localhost:11434',
            generation_model='qwen2.5:3b',
            enable_multipass_extraction=False  # Disable for focused testing
        )

        self.user_id = uuid.uuid4()

        # Create test conversation turn
        self.turn = ConversationTurn.objects.create(
            user_id=self.user_id,
            session_id='test-session',
            turn_number=1,
            user_message='I prefer dark mode in all my applications',
            assistant_message='Got it! Dark mode preference noted.'
        )

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_keywords_extraction_success(self, mock_vec, mock_emb, mock_gen):
        """Test successful A-MEM keywords extraction"""
        # Mock Pass 1 extraction
        mock_gen.side_effect = [
            # Pass 1: Extract note
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "prefers dark mode in applications",
                        "type": "preference:ui",
                        "confidence": 0.95
                    }]
                })
            },
            # A-MEM enrichment call
            {
                'success': True,
                'text': json.dumps({
                    "keywords": ["dark mode", "UI preference", "visual settings"],
                    "tags": ["preference", "interface", "accessibility"],
                    "context": "User has a strong preference for dark mode interfaces across all applications, likely for reduced eye strain and better low-light viewing."
                })
            }
        ]

        # Mock embedding generation
        enriched_embedding = [0.2] * 1024
        mock_emb.return_value = {'success': True, 'embeddings': [enriched_embedding]}
        mock_vec.return_value = 'vec-enriched'

        # Run extraction
        result = extract_atomic_notes(str(self.turn.id))

        # Verify extraction succeeded
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['notes_created'], 1)

        # Verify note was created with A-MEM attributes
        note = AtomicNote.objects.get(user_id=self.user_id)
        self.assertEqual(note.content, 'prefers dark mode in applications')
        self.assertTrue(note.is_amem_enriched)

        # Verify keywords
        self.assertIn('dark mode', note.keywords)
        self.assertIn('UI preference', note.keywords)
        self.assertEqual(len(note.keywords), 3)

        # Verify tags
        self.assertIn('preference', note.llm_tags)
        self.assertIn('interface', note.llm_tags)
        self.assertEqual(len(note.llm_tags), 3)

        # Verify contextual description
        self.assertIn('strong preference for dark mode', note.contextual_description)
        self.assertIn('eye strain', note.contextual_description)

        # Verify A-MEM embedding was generated
        # Two embedding calls: one for vector storage, one for link generation
        self.assertEqual(mock_emb.call_count, 2)
        # First call should include keywords, tags, and context in combined text
        first_embedding_call = mock_emb.call_args_list[0]
        # get_embeddings is called with a list of texts as first arg
        embedding_texts = first_embedding_call.args[0]  # List of texts
        embedding_text = embedding_texts[0]  # First (and only) text
        self.assertIn('dark mode', embedding_text)
        self.assertIn('preference', embedding_text)
        self.assertIn('eye strain', embedding_text)

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_enrichment_fallback_on_llm_failure(self, mock_vec, mock_emb, mock_gen):
        """Test A-MEM enrichment falls back gracefully when LLM fails"""
        # Mock Pass 1 extraction to succeed
        mock_gen.side_effect = [
            # Pass 1: Extract note
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "prefers dark mode",
                        "type": "preference:ui",
                        "confidence": 0.95
                    }]
                })
            },
            # A-MEM enrichment fails
            {
                'success': False,
                'error': 'LLM timeout'
            }
        ]

        # Mock embedding generation - content-only embedding (fallback enrichment has no keywords)
        embedding = [0.1] * 1024
        mock_emb.return_value = {'success': True, 'embeddings': [embedding]}
        mock_vec.return_value = 'vec-1'

        # Run extraction
        result = extract_atomic_notes(str(self.turn.id))

        # Verify extraction still succeeded (graceful degradation)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['notes_created'], 1)

        # Verify note was created with fallback enrichment
        note = AtomicNote.objects.get(user_id=self.user_id)
        self.assertEqual(note.content, 'prefers dark mode')
        # Even fallback enrichment sets is_amem_enriched = True
        self.assertTrue(note.is_amem_enriched)

        # Verify fallback tags applied (based on note_type)
        # Fallback uses [note_type] as is, not split
        self.assertEqual(note.llm_tags, ['preference:ui'])

        # Verify keywords empty (fallback didn't generate these)
        self.assertEqual(len(note.keywords), 0)

        # Verify context is first 200 chars of content (fallback behavior)
        self.assertEqual(note.contextual_description, note.content[:200])

        # Verify embedding was still generated and stored (A-MEM embedding with fallback data)
        # Two calls: one for storage, one for link generation
        self.assertEqual(mock_emb.call_count, 2)
        self.assertIsNotNone(note.vector_id)

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_enrichment_with_invalid_json(self, mock_vec, mock_emb, mock_gen):
        """Test A-MEM enrichment handles invalid JSON from LLM"""
        # Mock Pass 1 extraction
        mock_gen.side_effect = [
            # Pass 1: Extract note
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "prefers dark mode",
                        "type": "preference:ui",
                        "confidence": 0.95
                    }]
                })
            },
            # A-MEM enrichment returns invalid JSON
            {
                'success': True,
                'text': "This is not valid JSON at all!"
            }
        ]

        # Mock embedding generation
        base_embedding = [0.1] * 1024
        mock_emb.return_value = {'success': True, 'embeddings': [base_embedding]}
        mock_vec.return_value = 'vec-base'

        # Run extraction
        result = extract_atomic_notes(str(self.turn.id))

        # Verify extraction succeeded with fallback
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['notes_created'], 1)

        # Verify note created with fallback enrichment
        note = AtomicNote.objects.get(user_id=self.user_id)
        # Even fallback enrichment sets is_amem_enriched = True
        self.assertTrue(note.is_amem_enriched)

        # Verify fallback tags applied (note_type as single tag)
        self.assertEqual(note.llm_tags, ['preference:ui'])

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_multi_attribute_embedding_composition(self, mock_vec, mock_emb, mock_gen):
        """Test that multi-attribute embedding includes all A-MEM components"""
        # Mock extraction and enrichment
        mock_gen.side_effect = [
            # Pass 1
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "learning Python",
                        "type": "skill:programming",
                        "confidence": 0.9
                    }]
                })
            },
            # A-MEM enrichment
            {
                'success': True,
                'text': json.dumps({
                    "keywords": ["Python", "programming", "learning"],
                    "tags": ["skill", "technology", "development"],
                    "context": "User is actively learning Python programming language"
                })
            }
        ]

        # Mock embeddings
        base_emb = [0.1] * 1024
        multi_attr_emb = [0.2] * 1024
        mock_emb.side_effect = [
            {'success': True, 'embeddings': [base_emb]},
            {'success': True, 'embeddings': [multi_attr_emb]}
        ]
        mock_vec.side_effect = ['vec-1', 'vec-2']

        # Run extraction
        extract_atomic_notes(str(self.turn.id))

        # Verify multi-attribute embedding call composition
        # Two calls: one for storage, one for link generation
        self.assertEqual(mock_emb.call_count, 2)

        # Check the multi-attribute embedding text (first call)
        multi_attr_call = mock_emb.call_args_list[0]
        # get_embeddings is called with a list of texts as first arg
        embedding_texts = multi_attr_call.args[0]
        embedding_text = embedding_texts[0]  # First (and only) text

        # Should include base content
        self.assertIn('learning Python', embedding_text)

        # Should include keywords
        self.assertIn('Python', embedding_text)
        self.assertIn('programming', embedding_text)

        # Should include tags
        self.assertIn('skill', embedding_text)
        self.assertIn('technology', embedding_text)

        # Should include contextual description
        self.assertIn('actively learning', embedding_text)

        # Verify proper formatting (keywords and tags should be formatted specially)
        # The implementation should format multi-attributes clearly
        self.assertTrue(
            'Keywords:' in embedding_text or 'Tags:' in embedding_text,
            "Multi-attribute embedding should have clear formatting"
        )

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_enrichment_partial_data(self, mock_vec, mock_emb, mock_gen):
        """Test enrichment handles partial data (some fields missing)"""
        # Mock extraction and enrichment with partial data
        mock_gen.side_effect = [
            # Pass 1
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "uses vim",
                        "type": "preference:editor",
                        "confidence": 0.95
                    }]
                })
            },
            # A-MEM enrichment with only keywords (missing tags and context)
            {
                'success': True,
                'text': json.dumps({
                    "keywords": ["vim", "editor"],
                    # tags and context missing - will trigger fallback
                })
            }
        ]

        # Mock embeddings
        mock_emb.side_effect = [
            {'success': True, 'embeddings': [[0.1] * 1024]},
            {'success': True, 'embeddings': [[0.2] * 1024]}
        ]
        mock_vec.side_effect = ['vec-1', 'vec-2']

        # Run extraction
        result = extract_atomic_notes(str(self.turn.id))

        # Verify extraction succeeded
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['notes_created'], 1)

        # Verify note created with fallback enrichment (partial data triggers fallback)
        note = AtomicNote.objects.get(user_id=self.user_id)

        # Keywords should be empty (fallback doesn't have keywords)
        self.assertEqual(len(note.keywords), 0)

        # Tags should be fallback value (note_type)
        self.assertEqual(note.llm_tags, ['preference:editor'])

        # Context should be first 200 chars of content (fallback behavior)
        self.assertEqual(note.contextual_description, note.content[:200])

        # Note should still be considered enriched if we got some data
        # (implementation detail - check what actually happens)
        # This tests the robustness of partial enrichment

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_enrichment_with_empty_arrays(self, mock_vec, mock_emb, mock_gen):
        """Test enrichment handles empty arrays gracefully"""
        # Mock extraction and enrichment
        mock_gen.side_effect = [
            # Pass 1
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "test note",
                        "type": "test:type",
                        "confidence": 0.9
                    }]
                })
            },
            # A-MEM enrichment with empty arrays
            {
                'success': True,
                'text': json.dumps({
                    "keywords": [],  # Empty
                    "tags": [],  # Empty
                    "context": ""  # Empty
                })
            }
        ]

        # Mock embeddings
        mock_emb.return_value = {'success': True, 'embeddings': [[0.1] * 1024]}
        mock_vec.return_value = 'vec-1'

        # Run extraction
        result = extract_atomic_notes(str(self.turn.id))

        # Verify extraction succeeded
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['notes_created'], 1)

        # Verify note created with empty arrays (valid enrichment)
        note = AtomicNote.objects.get(user_id=self.user_id)

        # Empty keywords OK (enrichment returned empty list)
        self.assertEqual(len(note.keywords), 0)

        # Empty tags OK (enrichment returned empty list)
        self.assertEqual(len(note.llm_tags), 0)

        # Empty context OK (enrichment returned empty string)
        self.assertEqual(note.contextual_description, '')


class AmemEmbeddingFailureTest(TestCase):
    """Test A-MEM behavior when embedding generation fails"""

    def setUp(self):
        """Set up test environment"""
        cache.clear()
        Settings.objects.all().delete()

        self.settings = Settings.objects.create(
            embeddings_provider='ollama',
            embeddings_endpoint_url='http://localhost:11434',
            embeddings_model='nomic-embed-text'
        )

        self.user_id = uuid.uuid4()
        self.turn = ConversationTurn.objects.create(
            user_id=self.user_id,
            session_id='test-session',
            turn_number=1,
            user_message='I use dark mode',
            assistant_message='Noted!'
        )

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_multi_attribute_embedding_failure_rolls_back(self, mock_vec, mock_emb, mock_gen):
        """Test that note is rolled back if multi-attribute embedding fails"""
        # Mock extraction and enrichment to succeed
        mock_gen.side_effect = [
            # Pass 1
            {
                'success': True,
                'text': json.dumps({
                    "notes": [{
                        "content": "prefers dark mode",
                        "type": "preference:ui",
                        "confidence": 0.95
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
        ]

        # Mock A-MEM embedding to fail
        mock_emb.return_value = {'success': False, 'error': 'Embedding service timeout'}

        # Run extraction
        result = extract_atomic_notes(str(self.turn.id))

        # Verify note was rolled back (deleted) when embedding fails
        notes = AtomicNote.objects.filter(user_id=self.user_id)
        self.assertEqual(notes.count(), 0)

        # Extraction should report 0 notes created due to rollback
        self.assertEqual(result['notes_created'], 0)
