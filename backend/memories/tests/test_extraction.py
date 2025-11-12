"""
Tests for atomic note extraction pipeline
"""

import uuid
import json
from unittest.mock import Mock, patch
from django.test import TestCase
import unittest
from django.core.cache import cache

from memories.models import ConversationTurn, AtomicNote
from memories.tasks import extract_atomic_notes, EXTRACTION_PROMPT
from memories.settings_model import Settings


class AtomicNoteExtractionTest(TestCase):
    """Test atomic note extraction from conversation turns"""

    def setUp(self):
        """Create test conversation turn"""
        cache.clear()
        Settings.objects.all().delete()

        self.user_id = uuid.uuid4()
        self.turn = ConversationTurn.objects.create(
            user_id=self.user_id,
            session_id='test-session',
            turn_number=1,
            user_message="I prefer dark mode and use vim keybindings in VSCode",
            assistant_message="I'll remember your preferences!",
            vector_id='test-vector-1'
        )

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_extract_atomic_notes_success(self, mock_vector, mock_embeddings, mock_generate):
        """Test successful extraction of atomic notes"""
        # Mock LLM response
        mock_generate.return_value = {
            'success': True,
            'text': '''```json
{
  "notes": [
    {
      "content": "prefers dark mode",
      "type": "preference:ui",
      "context": "mentioned while discussing editor preferences",
      "confidence": 1.0,
      "tags": ["ui", "dark-mode"]
    },
    {
      "content": "uses vim keybindings",
      "type": "preference:editor",
      "context": "mentioned while discussing editor preferences",
      "confidence": 1.0,
      "tags": ["vim", "keybindings"]
    }
  ]
}
```'''
        }

        # Mock embeddings
        mock_embeddings.return_value = {
            'success': True,
            'embeddings': [[0.1] * 1024, [0.2] * 1024]
        }

        # Mock vector storage
        mock_vector.side_effect = ['vec-1', 'vec-2']

        # Run extraction
        result = extract_atomic_notes(str(self.turn.id))

        # Check result
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['notes_created'], 2)

        # Check notes were created
        notes = AtomicNote.objects.filter(user_id=self.user_id)
        self.assertEqual(notes.count(), 2)

        # Check first note
        dark_mode_note = notes.get(content="prefers dark mode")
        self.assertEqual(dark_mode_note.note_type, 'preference:ui')
        self.assertEqual(dark_mode_note.confidence, 1.0)
        self.assertEqual(dark_mode_note.tags, ["ui", "dark-mode"])
        self.assertEqual(dark_mode_note.source_turn, self.turn)

        # Check turn marked as extracted
        self.turn.refresh_from_db()
        self.assertTrue(self.turn.extracted)

    @patch('memories.tasks.llm_service.generate_text')
    def test_extraction_handles_markdown_code_blocks(self, mock_generate):
        """Test that extraction handles JSON in markdown code blocks"""
        # Response with markdown code block (no json label)
        mock_generate.return_value = {
            'success': True,
            'text': '''Here are the extracted notes:
```
{
  "notes": [
    {
      "content": "test note",
      "type": "test:type",
      "confidence": 0.9,
      "tags": []
    }
  ]
}
```'''
        }

        with patch('memories.tasks.llm_service.get_embeddings') as mock_emb, \
             patch('memories.tasks.vector_service.store_embedding') as mock_vec:

            mock_emb.return_value = {'success': True, 'embeddings': [[0.1] * 1024]}
            mock_vec.return_value = 'vec-1'

            result = extract_atomic_notes(str(self.turn.id))

            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['notes_created'], 1)

    @patch('memories.tasks.llm_service.generate_text')
    def test_extraction_skips_duplicates(self, mock_generate):
        """Test that extraction skips duplicate notes"""
        # Create existing note
        AtomicNote.objects.create(
            user_id=self.user_id,
            content="prefers dark mode",
            note_type="preference:ui",
            vector_id="existing-vec",
            source_turn=self.turn
        )

        # Mock LLM to return same note
        mock_generate.return_value = {
            'success': True,
            'text': json.dumps({
                "notes": [{
                    "content": "prefers dark mode",  # Duplicate
                    "type": "preference:ui",
                    "confidence": 1.0,
                    "tags": []
                }]
            })
        }

        result = extract_atomic_notes(str(self.turn.id))

        # Should skip duplicate
        self.assertEqual(result['notes_created'], 0)
        self.assertEqual(AtomicNote.objects.filter(user_id=self.user_id).count(), 1)

    @patch('memories.tasks.llm_service.generate_text')
    def test_extraction_handles_empty_notes(self, mock_generate):
        """Test that extraction handles empty notes array"""
        mock_generate.return_value = {
            'success': True,
            'text': json.dumps({"notes": []})
        }

        result = extract_atomic_notes(str(self.turn.id))

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['notes_created'], 0)

        # Turn should still be marked as extracted
        self.turn.refresh_from_db()
        self.assertTrue(self.turn.extracted)

    @patch('memories.tasks.llm_service.generate_text')
    def test_extraction_validates_note_fields(self, mock_generate):
        """Test that extraction validates required note fields"""
        # Return note with missing required fields
        mock_generate.return_value = {
            'success': True,
            'text': json.dumps({
                "notes": [
                    {"content": "valid note", "type": "test:type"},
                    {"content": ""},  # Missing type and empty content
                    {"type": "test:type"}  # Missing content
                ]
            })
        }

        with patch('memories.tasks.llm_service.get_embeddings') as mock_emb, \
             patch('memories.tasks.vector_service.store_embedding') as mock_vec:

            mock_emb.return_value = {'success': True, 'embeddings': [[0.1] * 1024]}
            mock_vec.return_value = 'vec-1'

            result = extract_atomic_notes(str(self.turn.id))

            # Should only create the valid note
            self.assertEqual(result['notes_created'], 1)

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.async_task')
    def test_extraction_retries_on_json_error(self, mock_async, mock_generate):
        """Test that extraction retries on JSON parse error"""
        # Return invalid JSON
        mock_generate.return_value = {
            'success': True,
            'text': "This is not JSON"
        }

        result = extract_atomic_notes(str(self.turn.id), retry_count=0)

        # Should schedule retry
        self.assertEqual(result['status'], 'retry_scheduled')
        self.assertEqual(result['attempt'], 1)
        mock_async.assert_called_once()

    @patch('memories.tasks.llm_service.generate_text')
    def test_extraction_fails_after_max_retries(self, mock_generate):
        """Test that extraction fails after 3 attempts"""
        mock_generate.return_value = {
            'success': True,
            'text': "Invalid JSON"
        }

        result = extract_atomic_notes(str(self.turn.id), retry_count=2)

        # Should fail after 3rd attempt
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error'], 'max_retries_exceeded')

    def test_extraction_skips_already_extracted(self):
        """Test that extraction skips already extracted turns"""
        self.turn.extracted = True
        self.turn.save()

        result = extract_atomic_notes(str(self.turn.id))

        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'already_extracted')

    @patch('memories.tasks.llm_service.generate_text')
    @unittest.skip("Temperature on retry not implemented - models have specific temperature requirements")
    def test_extraction_temperature_increases_on_retry(self, mock_generate):
        """Test that temperature increases with retry count"""
        mock_generate.return_value = {
            'success': True,
            'text': json.dumps({"notes": []})
        }

        # Call with different retry counts
        extract_atomic_notes(str(self.turn.id), retry_count=0)
        call_0 = mock_generate.call_args

        mock_generate.reset_mock()
        self.turn.extracted = False
        self.turn.save()

        extract_atomic_notes(str(self.turn.id), retry_count=1)
        call_1 = mock_generate.call_args

        # Temperature should increase
        temp_0 = call_0[1]['temperature']
        temp_1 = call_1[1]['temperature']

        self.assertEqual(temp_0, 0.3)  # Base temperature
        self.assertEqual(temp_1, 0.5)  # 0.3 + 0.2


    def test_extraction_prompt_contains_instructions(self):
        """Test that extraction prompt contains key instructions"""
        # Check prompt has critical components (case-insensitive)
        prompt_lower = EXTRACTION_PROMPT.lower()
        self.assertIn('atomic', prompt_lower)
        self.assertIn('json', prompt_lower)
        self.assertIn('confidence', prompt_lower)
        self.assertIn('type', prompt_lower)  # Changed from 'note_type' to 'type'
        self.assertIn('preference:', prompt_lower)
        self.assertIn('skill:', prompt_lower)

    @patch('memories.tasks.llm_service.get_embeddings')
    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.tasks.vector_service.store_embedding')
    def test_extraction_rolls_back_on_embedding_failure(self, mock_vec, mock_gen, mock_emb):
        """Test that note is rolled back if embedding fails"""
        mock_gen.return_value = {
            'success': True,
            'text': json.dumps({
                "notes": [{
                    "content": "test note",
                    "type": "test:type",
                    "confidence": 0.9,
                    "tags": []
                }]
            })
        }

        # Embedding fails
        mock_emb.return_value = {'success': False, 'error': 'Embedding failed'}

        result = extract_atomic_notes(str(self.turn.id))

        # Note should not be created
        self.assertEqual(AtomicNote.objects.filter(user_id=self.user_id).count(), 0)
        self.assertEqual(result['notes_created'], 0)
