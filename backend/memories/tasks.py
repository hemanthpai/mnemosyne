"""
Background tasks for atomic note extraction and relationship building

These tasks run asynchronously via Django-Q to extract structured knowledge
from conversation turns without blocking user interactions.

Based on A-MEM research (NeurIPS 2025):
"A-MEM: Agentic Memory for LLM Agents" by Xu et al.
Paper: docs/research/A-MEM_NeurIPS_2025.pdf
ArXiv: 2502.12110

Key principles from A-MEM:
- Atomic notes: discrete, self-contained units of knowledge
- Zettelkasten method: single fact per note
- Rich metadata: context, tags, relationships
- Dynamic knowledge graph through note relationships
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

EXTRACTION_PROMPT = """Extract atomic facts from this user message.

**User Message:**
{user_message}

**Instructions:**
Extract ALL individual, atomic facts about the user from their message. Each fact should be:
1. A single, granular piece of information
2. Self-contained and understandable on its own
3. About the user's preferences, skills, interests, or personal information
4. Stated by the USER (not assistant responses)

Be comprehensive - extract every distinct piece of information about the user.

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

**What to Extract:**
- Direct statements: "I use Python" → extract "uses Python" as a skill
- Preferences: "I prefer X for Y" → extract BOTH the preference AND the usage/skill
- Tool mentions: "I work with X, Y, and Z" → extract SEPARATE facts for EACH tool (X, Y, and Z)
- Experiences: "I've worked with X" → extract experience/skill with X
- Qualitative statements: "I love jazz" → extract interest in jazz
- Compound statements: ALWAYS break into multiple atomic facts
- Skills from usage: If user mentions using/working with a tool/language, extract as skill
- Ongoing activities: "I volunteer every weekend" → extract both the activity AND frequency
- List items with "and": "especially X and Y" → extract SEPARATE facts for X and Y
- Job titles/roles: "working as a developer" → extract "works as developer"
- Certifications: "got AWS certified" → extract "holds AWS certification"
- Benefits/effects: "X helps me do Y" → extract both the activity X AND the benefit Y
- Tool switching: "switched to X" → extract "uses X" (current tool)
- Named entities in lists: "Miles Davis and John Coltrane" → extract interest in EACH person
- Reasons for preferences: "I prefer X for its Y" → extract preference for X AND values Y
- Implied tools: "using Pinia" (Vue library) → extract both "uses Pinia" AND "uses Vue"

**Confidence Scoring:**
- High (0.9-1.0): Explicit direct statements ("I use X", "I prefer Y", "I love Z")
- Medium (0.7-0.9): Clear implications ("I work with X" implies skill in X)
- Lower (0.6-0.7): Tentative or uncertain statements ("I might try X")

**What NOT to Extract:**
- Subjective opinions about topics/things (not about the user themselves)
- Facts from assistant responses
- Pure questions without assertions

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

        # Get extraction prompt (custom from settings or default)
        from .settings_model import Settings
        settings = Settings.get_settings()
        extraction_template = settings.extraction_prompt or EXTRACTION_PROMPT

        # Generate extraction prompt (only from user message)
        prompt = extraction_template.format(
            user_message=turn.user_message
        )

        # Call LLM for extraction using configured temperature
        response = llm_service.generate_text(
            prompt=prompt,
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
# Relationship Building Prompt
# =============================================================================

RELATIONSHIP_PROMPT = """Analyze relationships between atomic notes.

**New Note:**
Content: {new_note_content}
Type: {new_note_type}
Context: {new_note_context}

**Existing Notes:**
{existing_notes}

**Instructions:**
Identify relationships between the new note and existing notes. For each relationship found:
1. Determine the relationship type
2. Assess the strength (0.0-1.0, where 1.0 is strongest)

**Relationship Types:**
- **related_to**: General thematic connection (e.g., both about Python, both preferences)
- **contradicts**: Direct contradiction (e.g., "prefers dark mode" vs "prefers light mode")
- **refines**: The new note adds detail/nuance to an existing note
- **context_for**: The new note provides context for understanding an existing note
- **follows_from**: The new note is a logical consequence of an existing note

**Strength Guidelines:**
- 1.0: Very strong/direct relationship
- 0.7-0.9: Clear relationship
- 0.5-0.6: Moderate relationship
- 0.3-0.4: Weak relationship
- Below 0.3: Don't create relationship

**Format your response as JSON:**
```json
{{
  "relationships": [
    {{
      "to_note_id": "note-id",
      "relationship_type": "related_to|contradicts|refines|context_for|follows_from",
      "strength": 0.85,
      "reasoning": "brief explanation"
    }}
  ]
}}
```

**Guidelines:**
- Only create relationships with strength >= 0.3
- Contradictions should be rare and obvious
- Most relationships will be "related_to" or "refines"
- Focus on meaningful connections, not superficial similarities
- Limit to top 5 strongest relationships

**Example:**

New Note: "uses vim keybindings"
Existing Notes:
1. [abc123] prefers VSCode | preference:editor
2. [def456] learning Python | skill:programming
3. [ghi789] prefers keyboard shortcuts | preference:ui

Response:
```json
{{
  "relationships": [
    {{
      "to_note_id": "abc123",
      "relationship_type": "context_for",
      "strength": 0.9,
      "reasoning": "vim keybindings are used within VSCode editor"
    }},
    {{
      "to_note_id": "ghi789",
      "relationship_type": "related_to",
      "strength": 0.7,
      "reasoning": "both relate to keyboard-driven workflow preferences"
    }}
  ]
}}
```

Now analyze the relationships for the note above:
"""


# =============================================================================
# Task 2: Build Note Relationships
# =============================================================================

def build_note_relationships_for_note(note_id: str, retry_count: int = 0) -> Dict[str, Any]:
    """
    Build relationships for a single atomic note (dynamic task)

    Called after a note is extracted to find connections with existing notes.

    Args:
        note_id: UUID of the AtomicNote to build relationships for
        retry_count: Current retry attempt (0-2)

    Returns:
        Dict with relationship building results
    """
    try:
        # Get the new note
        note = AtomicNote.objects.get(id=note_id)

        logger.info(f"Building relationships for note {note_id}: {note.content[:50]}...")

        # Find similar existing notes via vector search (excluding the note itself)
        # Use graph service to search for related atomic notes
        from .graph_service import graph_service

        # Search for similar notes
        similar_notes = graph_service.search_atomic_notes(
            query=note.content,
            user_id=str(note.user_id),
            limit=10,
            threshold=0.3  # Lower threshold to catch more potential relationships
        )

        # Filter out the note itself
        similar_notes = [n for n in similar_notes if n['id'] != str(note.id)]

        if not similar_notes:
            logger.info(f"No similar notes found for {note_id}")
            return {"status": "completed", "relationships_created": 0}

        # Format existing notes for prompt
        existing_notes_text = "\n".join([
            f"{i+1}. [{n['id']}] {n['content']} | {n['note_type']}"
            for i, n in enumerate(similar_notes[:5])  # Limit to top 5 for prompt
        ])

        # Get relationship prompt (custom from settings or default)
        from .settings_model import Settings
        settings = Settings.get_settings()
        relationship_template = settings.relationship_prompt or RELATIONSHIP_PROMPT

        # Generate relationship analysis prompt
        prompt = relationship_template.format(
            new_note_content=note.content,
            new_note_type=note.note_type,
            new_note_context=note.context or "none",
            existing_notes=existing_notes_text
        )

        # Call LLM for relationship analysis using configured temperature
        response = llm_service.generate_text(
            prompt=prompt,
            max_tokens=800
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

        relationship_data = json.loads(response_text)
        relationships_list = relationship_data.get('relationships', [])

        # Create relationships
        relationships_created = 0
        for rel_data in relationships_list:
            to_note_id = rel_data.get('to_note_id')
            rel_type = rel_data.get('relationship_type')
            strength = rel_data.get('strength', 0.5)

            # Validate
            if not to_note_id or not rel_type:
                logger.warning(f"Skipping invalid relationship: {rel_data}")
                continue

            if strength < 0.3:
                logger.info(f"Skipping weak relationship (strength={strength})")
                continue

            # Check if relationship already exists
            existing_rel = NoteRelationship.objects.filter(
                from_note_id=note.id,
                to_note_id=to_note_id
            ).first()

            if existing_rel:
                # Update strength if new analysis is stronger
                if strength > existing_rel.strength:
                    existing_rel.strength = strength
                    existing_rel.relationship_type = rel_type
                    existing_rel.save()
                    logger.info(f"Updated relationship strength: {note.id} -> {to_note_id}")
                continue

            # Create new relationship
            NoteRelationship.objects.create(
                from_note_id=note.id,
                to_note_id=to_note_id,
                relationship_type=rel_type,
                strength=strength
            )

            relationships_created += 1
            logger.info(f"Created relationship: {note.id} --[{rel_type}, {strength:.2f}]--> {to_note_id}")

        # Update importance scores based on connectivity
        _update_importance_score(note)

        logger.info(f"Built {relationships_created} relationships for note {note_id}")

        return {
            "status": "completed",
            "relationships_created": relationships_created,
            "note_id": str(note_id)
        }

    except AtomicNote.DoesNotExist:
        logger.error(f"AtomicNote {note_id} not found")
        return {"status": "error", "error": "note_not_found"}

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response for note {note_id}: {e}")
        logger.error(f"Response text: {response_text[:500]}")

        # Retry up to 3 times
        if retry_count < 2:
            logger.info(f"Retrying relationship building for note {note_id} (attempt {retry_count + 2}/3)")
            async_task(
                'memories.tasks.build_note_relationships_for_note',
                note_id,
                retry_count + 1,
                task_name=f"retry_relationships_{note_id}_{retry_count + 1}"
            )
            return {"status": "retry_scheduled", "attempt": retry_count + 1}
        else:
            logger.error(f"Failed to build relationships for note {note_id} after 3 attempts")
            return {"status": "failed", "error": "max_retries_exceeded"}

    except Exception as e:
        logger.error(f"Unexpected error building relationships for note {note_id}: {e}", exc_info=True)

        # Retry on unexpected errors too
        if retry_count < 2:
            async_task(
                'memories.tasks.build_note_relationships_for_note',
                note_id,
                retry_count + 1,
                task_name=f"retry_relationships_{note_id}_{retry_count + 1}"
            )
            return {"status": "retry_scheduled", "attempt": retry_count + 1}
        else:
            return {"status": "failed", "error": str(e)}


def _update_importance_score(note: AtomicNote):
    """
    Update importance score based on connectivity in the graph

    More connected notes are more important. Score is based on:
    - Number of relationships (incoming + outgoing)
    - Strength of relationships
    - Confidence of the note itself
    """
    # Count relationships
    outgoing = NoteRelationship.objects.filter(from_note_id=note.id)
    incoming = NoteRelationship.objects.filter(to_note_id=note.id)

    # Calculate score based on connectivity
    outgoing_score = sum(rel.strength for rel in outgoing)
    incoming_score = sum(rel.strength for rel in incoming)

    # Importance = base confidence + connectivity bonus
    # Max connectivity bonus is 2.0 (so max total importance is 3.0)
    connectivity_bonus = min(2.0, (outgoing_score + incoming_score) * 0.2)
    importance = note.confidence + connectivity_bonus

    # Update note
    note.importance_score = importance
    note.save(update_fields=['importance_score'])

    logger.info(f"Updated importance score for note {note.id}: {importance:.2f} (confidence={note.confidence:.2f}, connections={len(outgoing) + len(incoming)})")


def build_note_relationships(user_id: str) -> Dict[str, Any]:
    """
    Build relationships for all notes for a user (nightly batch task)

    This is the batch version that processes all notes for a user.
    Used as a backup to catch any missed relationships.

    Args:
        user_id: UUID of the user

    Returns:
        Dict with relationship building results
    """
    logger.info(f"Starting batch relationship building for user {user_id}")

    # Get all notes for user
    notes = AtomicNote.objects.filter(user_id=user_id).order_by('-created_at')

    total_relationships = 0
    notes_processed = 0

    for note in notes:
        result = build_note_relationships_for_note(str(note.id))
        if result['status'] == 'completed':
            total_relationships += result.get('relationships_created', 0)
            notes_processed += 1

    logger.info(f"Batch relationship building complete: {total_relationships} relationships for {notes_processed} notes")

    return {
        "status": "completed",
        "user_id": user_id,
        "notes_processed": notes_processed,
        "relationships_created": total_relationships
    }


# =============================================================================
# Helper: Schedule Extraction Task
# =============================================================================

def schedule_extraction(turn_id: str, delay_seconds: int = 0):
    """
    Schedule extraction task for a conversation turn

    Args:
        turn_id: UUID of the ConversationTurn
        delay_seconds: Delay before extraction (default: 0s = immediate)
                      Queue will naturally space out processing
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

        # Schedule relationship building for newly created notes
        try:
            result = task.result
            if isinstance(result, dict) and result.get('status') == 'completed':
                notes_created = result.get('notes_created', 0)

                if notes_created > 0:
                    # Get the turn_id from the task result
                    turn_id = result.get('turn_id')
                    if turn_id:
                        # Find notes created from this turn and schedule relationship building
                        from .models import AtomicNote
                        notes = AtomicNote.objects.filter(source_turn_id=turn_id)

                        for note in notes:
                            async_task(
                                'memories.tasks.build_note_relationships_for_note',
                                str(note.id),
                                0,  # retry_count starts at 0
                                task_name=f"relationships_{note.id}",
                                timeout=600
                            )
                            logger.info(f"Scheduled relationship building for note {note.id}")

        except Exception as e:
            logger.error(f"Failed to schedule relationship building: {e}", exc_info=True)

    else:
        logger.error(f"Extraction task {task.name} failed: {task.result}")


# =============================================================================
# Nightly Relationship Building for All Users
# =============================================================================

def nightly_relationship_building_all_users() -> Dict[str, Any]:
    """
    Nightly task to build relationships for all users (scheduled task)

    This is a backup/catch-all task that runs at 2am daily to:
    1. Process any users who have new notes
    2. Catch any missed relationships from dynamic processing
    3. Update importance scores across the graph

    Returns:
        Dict with processing results
    """
    from .models import AtomicNote
    from django.db.models import Count

    logger.info("Starting nightly relationship building for all users")

    # Get users who have atomic notes
    users_with_notes = (
        AtomicNote.objects
        .values('user_id')
        .annotate(note_count=Count('id'))
        .filter(note_count__gt=0)
    )

    total_users = len(users_with_notes)
    total_relationships = 0
    users_processed = 0

    for user_data in users_with_notes:
        user_id = str(user_data['user_id'])
        note_count = user_data['note_count']

        logger.info(f"Processing user {user_id} ({note_count} notes)")

        try:
            result = build_note_relationships(user_id)

            if result['status'] == 'completed':
                total_relationships += result.get('relationships_created', 0)
                users_processed += 1

        except Exception as e:
            logger.error(f"Failed to process relationships for user {user_id}: {e}")
            continue

    logger.info(
        f"Nightly relationship building complete: "
        f"{total_relationships} relationships created for {users_processed}/{total_users} users"
    )

    return {
        "status": "completed",
        "users_processed": users_processed,
        "total_users": total_users,
        "relationships_created": total_relationships
    }
