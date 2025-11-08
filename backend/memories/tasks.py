"""
Phase 3: Background tasks for atomic note extraction and relationship building

These tasks run asynchronously via Django-Q to extract structured knowledge
from conversation turns without blocking user interactions.
"""

import logging
import json
from typing import List, Dict, Any
from django_q.tasks import async_task, schedule
from django.utils import timezone

from .models import ConversationTurn, AtomicNote, NoteRelationship
from .llm_service import llm_service
from .vector_service import vector_service

logger = logging.getLogger(__name__)


# =============================================================================
# Extraction Prompt
# =============================================================================

EXTRACTION_PROMPT = """Extract atomic facts from this conversation turn.

**Conversation:**
User: {user_message}
Assistant: {assistant_message}

**Instructions:**
Extract individual, atomic facts about the user. Each fact should be:
1. A single, granular piece of information
2. Self-contained and understandable on its own
3. About the user's preferences, skills, interests, or personal information

**Format your response as JSON:**
```json
{{
  "notes": [
    {{
      "content": "single atomic fact",
      "type": "category:subcategory",
      "context": "brief context about when/why mentioned",
      "confidence": 0.95,
      "tags": ["tag1", "tag2"]
    }}
  ]
}}
```

**Note Types:**
- preference:ui - UI/UX preferences
- preference:editor - Editor/IDE preferences
- preference:tool - Tool preferences
- skill:programming - Programming skills
- skill:language - Language skills
- interest:topic - Topic interests
- interest:hobby - Hobbies and activities
- personal:location - Location information
- personal:background - Background information
- goal:career - Career goals
- goal:learning - Learning goals

**Guidelines:**
- Only extract facts explicitly stated or strongly implied
- Do NOT extract assistant responses unless they reveal user information
- Break compound statements into multiple atomic facts
- Set confidence lower (0.6-0.8) for implied facts
- Set confidence higher (0.9-1.0) for explicit statements

**Examples:**

User: "I prefer dark mode and use vim keybindings in VSCode"
```json
{{
  "notes": [
    {{
      "content": "prefers dark mode",
      "type": "preference:ui",
      "context": "mentioned while discussing editor preferences",
      "confidence": 1.0,
      "tags": ["ui", "dark-mode"]
    }},
    {{
      "content": "uses vim keybindings",
      "type": "preference:editor",
      "context": "mentioned while discussing editor preferences",
      "confidence": 1.0,
      "tags": ["vim", "keybindings"]
    }},
    {{
      "content": "primary editor is VSCode",
      "type": "preference:tool",
      "context": "mentioned while discussing editor preferences",
      "confidence": 1.0,
      "tags": ["vscode", "editor"]
    }}
  ]
}}
```

Now extract facts from the conversation above:
"""


# =============================================================================
# Task 1: Extract Atomic Notes
# =============================================================================

def extract_atomic_notes(turn_id: str, retry_count: int = 0) -> Dict[str, Any]:
    """
    Extract atomic notes from a conversation turn (background task)

    Args:
        turn_id: UUID of the ConversationTurn to extract from
        retry_count: Current retry attempt (0-2)

    Returns:
        Dict with extraction results

    This task is scheduled 15 minutes after conversation storage to allow
    time for the conversation to complete and to avoid blocking the user.
    """
    try:
        # Get the conversation turn
        turn = ConversationTurn.objects.get(id=turn_id)

        # Skip if already extracted
        if turn.extracted:
            logger.info(f"Turn {turn_id} already extracted, skipping")
            return {"status": "skipped", "reason": "already_extracted"}

        logger.info(f"Extracting atomic notes from turn {turn_id} (attempt {retry_count + 1}/3)")

        # Generate extraction prompt
        prompt = EXTRACTION_PROMPT.format(
            user_message=turn.user_message,
            assistant_message=turn.assistant_message
        )

        # Call LLM for extraction
        # Adjust temperature based on retry count (higher = more creative)
        temperature = 0.3 + (retry_count * 0.2)  # 0.3, 0.5, 0.7

        response = llm_service.generate_text(
            prompt=prompt,
            temperature=temperature,
            max_tokens=1000
        )

        if not response['success']:
            raise ValueError(f"LLM generation failed: {response.get('error')}")

        # Parse JSON response
        response_text = response['text'].strip()

        # Extract JSON from markdown code blocks if present
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()

        extraction_data = json.loads(response_text)
        notes_data = extraction_data.get('notes', [])

        if not notes_data:
            logger.warning(f"No notes extracted from turn {turn_id}")
            turn.extracted = True
            turn.save(update_fields=['extracted'])
            return {"status": "completed", "notes_created": 0}

        # Validate and store notes
        notes_created = 0
        for note_data in notes_data:
            # Validate required fields
            if not note_data.get('content') or not note_data.get('type'):
                logger.warning(f"Skipping invalid note: {note_data}")
                continue

            # Check for duplicates (similar content for same user)
            existing = AtomicNote.objects.filter(
                user_id=turn.user_id,
                content__iexact=note_data['content']
            ).first()

            if existing:
                logger.info(f"Note already exists: {note_data['content'][:50]}...")
                continue

            # Create atomic note
            note = AtomicNote.objects.create(
                user_id=turn.user_id,
                content=note_data['content'],
                note_type=note_data['type'],
                context=note_data.get('context', ''),
                confidence=note_data.get('confidence', 0.8),
                tags=note_data.get('tags', []),
                source_turn=turn
            )

            # Generate embedding for the note
            embedding_result = llm_service.get_embeddings([note.content])

            if not embedding_result['success']:
                logger.error(f"Failed to embed note {note.id}: {embedding_result['error']}")
                note.delete()  # Rollback
                continue

            # Store in vector DB
            vector_id = vector_service.store_embedding(
                embedding=embedding_result['embeddings'][0],
                user_id=str(turn.user_id),
                metadata={
                    'type': 'atomic_note',
                    'note_id': str(note.id),
                    'note_type': note.note_type,
                    'confidence': note.confidence,
                    'timestamp': note.created_at.isoformat()
                }
            )

            # Update note with vector_id
            note.vector_id = vector_id
            note.save(update_fields=['vector_id'])

            notes_created += 1
            logger.info(f"Created atomic note: {note.content[:50]}... (type: {note.note_type})")

        # Mark turn as extracted
        turn.extracted = True
        turn.save(update_fields=['extracted'])

        logger.info(f"Successfully extracted {notes_created} notes from turn {turn_id}")

        return {
            "status": "completed",
            "notes_created": notes_created,
            "turn_id": str(turn_id)
        }

    except ConversationTurn.DoesNotExist:
        logger.error(f"ConversationTurn {turn_id} not found")
        return {"status": "error", "error": "turn_not_found"}

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response for turn {turn_id}: {e}")
        logger.error(f"Response text: {response_text[:500]}")

        # Retry up to 3 times
        if retry_count < 2:
            logger.info(f"Retrying extraction for turn {turn_id} (attempt {retry_count + 2}/3)")
            # Schedule retry in 5 minutes
            async_task(
                'memories.tasks.extract_atomic_notes',
                turn_id,
                retry_count + 1,
                task_name=f"retry_extract_{turn_id}_{retry_count + 1}"
            )
            return {"status": "retry_scheduled", "attempt": retry_count + 1}
        else:
            logger.error(f"Failed to extract notes from turn {turn_id} after 3 attempts")
            return {"status": "failed", "error": "max_retries_exceeded"}

    except Exception as e:
        logger.error(f"Unexpected error extracting notes from turn {turn_id}: {e}", exc_info=True)

        # Retry on unexpected errors too
        if retry_count < 2:
            async_task(
                'memories.tasks.extract_atomic_notes',
                turn_id,
                retry_count + 1,
                task_name=f"retry_extract_{turn_id}_{retry_count + 1}"
            )
            return {"status": "retry_scheduled", "attempt": retry_count + 1}
        else:
            return {"status": "failed", "error": str(e)}


# =============================================================================
# Task 2: Build Note Relationships (Placeholder for future)
# =============================================================================

def build_note_relationships(user_id: str) -> Dict[str, Any]:
    """
    Build relationships between atomic notes for a user (nightly task)

    This is a placeholder for Phase 3.2. Will analyze atomic notes to find
    implicit connections and create NoteRelationship edges.

    Args:
        user_id: UUID of the user

    Returns:
        Dict with relationship building results
    """
    logger.info(f"Relationship building for user {user_id} - not yet implemented")
    return {"status": "not_implemented"}


# =============================================================================
# Helper: Schedule Extraction Task
# =============================================================================

def schedule_extraction(turn_id: str, delay_seconds: int = 900):
    """
    Schedule extraction task for a conversation turn

    Args:
        turn_id: UUID of the ConversationTurn
        delay_seconds: Delay before extraction (default: 900s = 15min)
    """
    async_task(
        'memories.tasks.extract_atomic_notes',
        turn_id,
        0,  # retry_count starts at 0
        task_name=f"extract_{turn_id}",
        hook='memories.tasks.extraction_hook',
        timeout=600,  # 10 minutes max
        q_options={'delay': delay_seconds}
    )
    logger.info(f"Scheduled extraction for turn {turn_id} in {delay_seconds}s")


def extraction_hook(task):
    """Hook called after extraction task completes"""
    if task.success:
        logger.info(f"Extraction task {task.name} completed successfully")
    else:
        logger.error(f"Extraction task {task.name} failed: {task.result}")
