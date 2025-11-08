"""
Tests for relationship building between atomic notes
"""

import uuid
import json
from unittest.mock import Mock, patch
from django.test import TestCase
from django.core.cache import cache

from memories.models import AtomicNote, NoteRelationship
from memories.tasks import build_note_relationships_for_note, _update_importance_score
from memories.settings_model import Settings


class NoteRelationshipBuildingTest(TestCase):
    """Test relationship building between atomic notes"""

    def setUp(self):
        """Create test atomic notes"""
        cache.clear()
        Settings.objects.all().delete()

        self.user_id = uuid.uuid4()

        # Create test notes
        self.note1 = AtomicNote.objects.create(
            user_id=self.user_id,
            content="prefers VSCode",
            note_type="preference:editor",
            vector_id="vec-1",
            confidence=1.0
        )

        self.note2 = AtomicNote.objects.create(
            user_id=self.user_id,
            content="uses vim keybindings",
            note_type="preference:editor",
            vector_id="vec-2",
            confidence=1.0
        )

        self.note3 = AtomicNote.objects.create(
            user_id=self.user_id,
            content="learning Python",
            note_type="skill:programming",
            vector_id="vec-3",
            confidence=0.8
        )

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.graph_service.graph_service.search_atomic_notes')
    def test_build_relationships_success(self, mock_search, mock_generate):
        """Test successful relationship building"""
        # Mock search to return similar notes
        mock_search.return_value = [
            {'id': str(self.note1.id), 'content': self.note1.content, 'note_type': self.note1.note_type},
            {'id': str(self.note3.id), 'content': self.note3.content, 'note_type': self.note3.note_type}
        ]

        # Mock LLM response
        mock_generate.return_value = {
            'success': True,
            'text': json.dumps({
                "relationships": [
                    {
                        "to_note_id": str(self.note1.id),
                        "relationship_type": "context_for",
                        "strength": 0.9,
                        "reasoning": "vim keybindings are used within VSCode"
                    }
                ]
            })
        }

        # Build relationships for note2
        result = build_note_relationships_for_note(str(self.note2.id))

        # Check result
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['relationships_created'], 1)

        # Check relationship was created
        rel = NoteRelationship.objects.get(
            from_note=self.note2,
            to_note=self.note1
        )
        self.assertEqual(rel.relationship_type, 'context_for')
        self.assertEqual(rel.strength, 0.9)

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.graph_service.graph_service.search_atomic_notes')
    def test_build_relationships_skips_weak_relationships(self, mock_search, mock_generate):
        """Test that weak relationships (< 0.3) are skipped"""
        mock_search.return_value = [
            {'id': str(self.note1.id), 'content': self.note1.content, 'note_type': self.note1.note_type}
        ]

        # Return weak relationship
        mock_generate.return_value = {
            'success': True,
            'text': json.dumps({
                "relationships": [
                    {
                        "to_note_id": str(self.note1.id),
                        "relationship_type": "related_to",
                        "strength": 0.2,  # Too weak
                        "reasoning": "weak connection"
                    }
                ]
            })
        }

        result = build_note_relationships_for_note(str(self.note2.id))

        # Should skip weak relationship
        self.assertEqual(result['relationships_created'], 0)
        self.assertEqual(NoteRelationship.objects.count(), 0)

    @patch('memories.tasks.llm_service.generate_text')
    @patch('memories.graph_service.graph_service.search_atomic_notes')
    def test_build_relationships_updates_existing(self, mock_search, mock_generate):
        """Test that existing relationships are updated if new strength is higher"""
        # Create existing relationship
        existing = NoteRelationship.objects.create(
            from_note=self.note2,
            to_note=self.note1,
            relationship_type='related_to',
            strength=0.5
        )

        mock_search.return_value = [
            {'id': str(self.note1.id), 'content': self.note1.content, 'note_type': self.note1.note_type}
        ]

        # Return stronger relationship
        mock_generate.return_value = {
            'success': True,
            'text': json.dumps({
                "relationships": [
                    {
                        "to_note_id": str(self.note1.id),
                        "relationship_type": "context_for",
                        "strength": 0.9,  # Stronger
                        "reasoning": "stronger connection found"
                    }
                ]
            })
        }

        result = build_note_relationships_for_note(str(self.note2.id))

        # Should update existing relationship
        self.assertEqual(result['relationships_created'], 0)  # Not new

        existing.refresh_from_db()
        self.assertEqual(existing.strength, 0.9)
        self.assertEqual(existing.relationship_type, 'context_for')

    @patch('memories.graph_service.graph_service.search_atomic_notes')
    def test_build_relationships_no_similar_notes(self, mock_search):
        """Test behavior when no similar notes found"""
        # No similar notes
        mock_search.return_value = []

        result = build_note_relationships_for_note(str(self.note2.id))

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['relationships_created'], 0)

    @patch('memories.graph_service.graph_service.search_atomic_notes')
    def test_build_relationships_excludes_self(self, mock_search):
        """Test that note doesn't create relationship with itself"""
        # Search returns the note itself
        mock_search.return_value = [
            {'id': str(self.note2.id), 'content': self.note2.content, 'note_type': self.note2.note_type},
            {'id': str(self.note1.id), 'content': self.note1.content, 'note_type': self.note1.note_type}
        ]

        with patch('memories.tasks.llm_service.generate_text') as mock_gen:
            mock_gen.return_value = {
                'success': True,
                'text': json.dumps({"relationships": []})
            }

            result = build_note_relationships_for_note(str(self.note2.id))

            # Should filter out self from search results
            # LLM should only see note1, not note2
            call_args = mock_gen.call_args
            prompt = call_args.kwargs['prompt']  # Get prompt from keyword arguments

            self.assertNotIn(str(self.note2.id), prompt)
            self.assertIn(str(self.note1.id), prompt)


class ImportanceScoreTest(TestCase):
    """Test importance score calculation"""

    def setUp(self):
        """Create test notes and relationships"""
        cache.clear()

        self.user_id = uuid.uuid4()

        self.note1 = AtomicNote.objects.create(
            user_id=self.user_id,
            content="test note 1",
            note_type="test:type",
            vector_id="vec-1",
            confidence=0.8
        )

        self.note2 = AtomicNote.objects.create(
            user_id=self.user_id,
            content="test note 2",
            note_type="test:type",
            vector_id="vec-2",
            confidence=0.9
        )

        self.note3 = AtomicNote.objects.create(
            user_id=self.user_id,
            content="test note 3",
            note_type="test:type",
            vector_id="vec-3",
            confidence=0.7
        )

    def test_importance_score_with_no_relationships(self):
        """Test importance score equals confidence when no relationships"""
        _update_importance_score(self.note1)

        self.note1.refresh_from_db()
        self.assertEqual(self.note1.importance_score, 0.8)  # Just confidence

    def test_importance_score_with_outgoing_relationships(self):
        """Test importance score increases with outgoing relationships"""
        # Create outgoing relationships
        NoteRelationship.objects.create(
            from_note=self.note1,
            to_note=self.note2,
            relationship_type='related_to',
            strength=0.8
        )
        NoteRelationship.objects.create(
            from_note=self.note1,
            to_note=self.note3,
            relationship_type='refines',
            strength=0.6
        )

        _update_importance_score(self.note1)

        self.note1.refresh_from_db()

        # Score = confidence + (sum of outgoing strengths * 0.2)
        # = 0.8 + ((0.8 + 0.6) * 0.2)
        # = 0.8 + 0.28 = 1.08
        self.assertAlmostEqual(self.note1.importance_score, 1.08, places=2)

    def test_importance_score_with_incoming_relationships(self):
        """Test importance score increases with incoming relationships"""
        # Create incoming relationships
        NoteRelationship.objects.create(
            from_note=self.note2,
            to_note=self.note1,
            relationship_type='related_to',
            strength=0.9
        )

        _update_importance_score(self.note1)

        self.note1.refresh_from_db()

        # Score = confidence + (sum of incoming strengths * 0.2)
        # = 0.8 + (0.9 * 0.2)
        # = 0.8 + 0.18 = 0.98
        self.assertAlmostEqual(self.note1.importance_score, 0.98, places=2)

    def test_importance_score_caps_at_max(self):
        """Test that importance score is capped"""
        # Create many strong relationships
        for i in range(20):
            other_note = AtomicNote.objects.create(
                user_id=self.user_id,
                content=f"note {i}",
                note_type="test:type",
                vector_id=f"vec-cap-{i}",  # Unique prefix to avoid collision
                confidence=0.8
            )
            NoteRelationship.objects.create(
                from_note=self.note1,
                to_note=other_note,
                relationship_type='related_to',
                strength=1.0
            )

        _update_importance_score(self.note1)

        self.note1.refresh_from_db()

        # Max connectivity bonus is 2.0, so max score is confidence + 2.0
        # = 0.8 + 2.0 = 2.8
        self.assertLessEqual(self.note1.importance_score, 2.8)

    def test_importance_score_both_directions(self):
        """Test importance score with both incoming and outgoing relationships"""
        # Outgoing
        NoteRelationship.objects.create(
            from_note=self.note1,
            to_note=self.note2,
            relationship_type='related_to',
            strength=0.7
        )
        # Incoming
        NoteRelationship.objects.create(
            from_note=self.note3,
            to_note=self.note1,
            relationship_type='related_to',
            strength=0.6
        )

        _update_importance_score(self.note1)

        self.note1.refresh_from_db()

        # Score = confidence + ((outgoing + incoming) * 0.2)
        # = 0.8 + ((0.7 + 0.6) * 0.2)
        # = 0.8 + 0.26 = 1.06
        self.assertAlmostEqual(self.note1.importance_score, 1.06, places=2)


class RelationshipConstraintsTest(TestCase):
    """Test relationship model constraints"""

    def setUp(self):
        """Create test notes"""
        self.user_id = uuid.uuid4()

        self.note1 = AtomicNote.objects.create(
            user_id=self.user_id,
            content="note 1",
            note_type="test:type",
            vector_id="vec-1",
            confidence=0.8
        )

        self.note2 = AtomicNote.objects.create(
            user_id=self.user_id,
            content="note 2",
            note_type="test:type",
            vector_id="vec-2",
            confidence=0.8
        )

    def test_unique_together_constraint(self):
        """Test that duplicate relationships are prevented"""
        # Create relationship
        NoteRelationship.objects.create(
            from_note=self.note1,
            to_note=self.note2,
            relationship_type='related_to',
            strength=0.8
        )

        # Try to create duplicate - should raise error
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            NoteRelationship.objects.create(
                from_note=self.note1,
                to_note=self.note2,
                relationship_type='related_to',  # Same type
                strength=0.9
            )

    def test_different_relationship_types_allowed(self):
        """Test that same notes can have different relationship types"""
        # Create first relationship
        rel1 = NoteRelationship.objects.create(
            from_note=self.note1,
            to_note=self.note2,
            relationship_type='related_to',
            strength=0.8
        )

        # Create second relationship with different type - should work
        rel2 = NoteRelationship.objects.create(
            from_note=self.note1,
            to_note=self.note2,
            relationship_type='refines',  # Different type
            strength=0.9
        )

        self.assertEqual(NoteRelationship.objects.count(), 2)
