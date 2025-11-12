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
import sys
from io import StringIO
from typing import List, Dict, Any
from django_q.tasks import async_task, schedule
from django.utils import timezone
from django.core.management import call_command

from .models import ConversationTurn, AtomicNote, NoteRelationship
from .llm_service import llm_service
from .vector_service import vector_service

logger = logging.getLogger(__name__)


# =============================================================================
# Benchmark Task
# =============================================================================

def run_benchmark_task(tracking_id, test_type, dataset):
    """
    Async task to run benchmarks
    Django-Q will automatically store the result

    Args:
        tracking_id: UUID for tracking progress (passed from views.py)
        test_type: Type of benchmark to run
        dataset: Dataset filename
    """
    try:
        logger.info(f"Starting benchmark task with tracking_id={tracking_id}, test_type={test_type}, dataset={dataset}")

        # Capture stdout
        output = StringIO()
        sys.stdout = output

        # Run benchmark command with tracking_id for progress tracking
        call_command('run_benchmark', test_type=test_type, dataset=dataset, task_id=tracking_id)

        # Restore stdout
        sys.stdout = sys.__stdout__

        # Return the output - django-q will store this as the task result
        return {
            'success': True,
            'output': output.getvalue(),
            'test_type': test_type,
            'dataset': dataset,
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        sys.stdout = sys.__stdout__
        logger.error(f"Benchmark task failed: {e}", exc_info=True)

        # Return error - django-q will store this as the task result
        return {
            'success': False,
            'error': str(e),
            'test_type': test_type,
            'dataset': dataset,
            'timestamp': timezone.now().isoformat()
        }


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

**IMPORTANT:**
- Extract each fact separately - DO NOT combine related facts into one note
- Include both explicit statements AND clear implications from context
- When in doubt, create separate notes rather than merging them

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
- "primarily with X" → extract "experienced with X" and "uses X"
- "mainly X" → extract "focuses on X" and interest/activity in X
- Experiences: "I've worked with X" → extract experience/skill with X
- Qualitative statements: "I love jazz" / "I'm a huge X fan" → extract strong interest in X
- Compound statements: ALWAYS break into multiple atomic facts
- Skills from usage: If user mentions using/working with a tool/language, extract as skill
- Ongoing activities: "I volunteer every weekend" → extract both the activity AND frequency
- List items with "and": "especially X and Y" → extract SEPARATE facts for X and Y
- Job titles/roles: "working as a developer" → extract "works as developer"
- Certifications: "got AWS certified" → extract "holds AWS certification"
- Benefits/effects: "X helps me do Y" → extract BOTH the activity X AND the benefit Y separately
- "It's rewarding to X" / "I find X rewarding" → extract "finds X rewarding"
- Tool switching: "switched to X" → extract "uses X" (current tool)
- Named entities in lists: "Miles Davis and John Coltrane" → extract interest in EACH person separately
- Reasons for preferences: "I prefer X for its Y" → extract preference for X AND "values Y"
- Implied tools: "using Pinia" (Vue library) → extract both "uses Pinia" AND "uses Vue"
- Temporal contexts: "before work", "every morning" → extract both activity and timing
- Repeated actions: "read X three times", "for the third time" → extract "re-reads X" or "revisits X"
- Frequency patterns: "tries to X" / "try to X" → extract "attempts to X" or "regularly does X" (medium confidence)
- Proficiency levels: "know some X but not conversational" → extract both knowledge AND proficiency level
- Value statements: When user explains WHY they prefer something, extract the value ("values X")

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

# Second pass prompt for contextual and implied facts
EXTRACTION_PROMPT_PASS2 = """You are doing a second pass extraction to find additional atomic facts that require deeper analysis.

**User Message:**
{user_message}

**Facts Already Extracted (Pass 1):**
{pass1_facts}

**Instructions for Pass 2:**
Find ADDITIONAL atomic facts that were missed in Pass 1. Focus on:

1. **Implied Facts** - Facts not explicitly stated but clearly implied by context
2. **Causal Relationships** - When user says "X was challenging" or "X was the hardest part", extract "learned importance of Y" or "struggled with X"
3. **Motivations & Reasons** - "keeps me going" → "motivated by X", "that's why I..." → extract the motivation
4. **Learning Outcomes** - "X has been a learning curve" → "learned about X", "discovered that Y" → "learned Y"
5. **Temporal Changes** - "used to X" / "previously X" → extract past state, "now Y" → extract current state
6. **Complex Multi-Clause Facts** - Facts embedded in complex sentences that require parsing multiple clauses
7. **Quantities & Durations** - Specific numbers, time periods that weren't captured
8. **Context-Dependent Facts** - Facts that only make sense with surrounding context

**What NOT to Extract:**
- Do NOT repeat any facts already found in Pass 1 above
- Do NOT extract facts from assistant responses
- Do NOT extract subjective opinions about topics (only facts about the user)

**Format your response as JSON:**
```json
{{
  "notes": [
    {{
      "content": "single atomic fact",
      "type": "category:subcategory",
      "context": "brief context about when/why mentioned",
      "confidence": 0.80,
      "tags": ["tag1", "tag2"]
    }}
  ]
}}
```

**Confidence Scoring for Pass 2:**
- Medium-High (0.75-0.9): Strong implications from context
- Medium (0.6-0.75): Reasonable inferences from stated information
- Lower (0.5-0.6): Weak implications that might be subjective

Extract additional facts that Pass 1 missed:
"""


# =============================================================================
# Task 1: Extract Atomic Notes
# =============================================================================

def update_extraction_progress(turn_id: str, phase: str, current: int, total: int, detail: str = ''):
    """Update extraction progress in cache for UI monitoring"""
    from django.core.cache import cache
    progress_data = {
        'phase': phase,
        'current': current,
        'total': total,
        'percentage': int((current / total * 100)) if total > 0 else 0,
        'detail': detail,
        'turn_id': turn_id
    }
    cache.set(f'extraction_progress_{turn_id}', progress_data, timeout=3600)  # 1 hour


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
        # Initialize progress tracking
        update_extraction_progress(turn_id, 'Starting extraction', 0, 4, '')

        # Get the conversation turn
        turn = ConversationTurn.objects.get(id=turn_id)

        # Skip if already extracted
        if turn.extracted:
            logger.info(f"Turn {turn_id} already extracted, skipping")
            return {"status": "skipped", "reason": "already_extracted"}

        logger.info(f"Extracting atomic notes from turn {turn_id} (attempt {retry_count + 1}/3)")

        # Phase 1: Pass 1 Extraction
        update_extraction_progress(turn_id, 'Extracting notes (Pass 1)', 1, 4, 'Running LLM extraction...')

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

        # Validate notes have required fields
        valid_notes = []
        for note in notes_data:
            if 'content' in note and 'type' in note and note['content'].strip():
                valid_notes.append(note)
            else:
                logger.debug(f"Skipping invalid note (missing required fields): {note}")
        notes_data = valid_notes

        # Multi-pass extraction (Pass 2) if enabled
        if settings.enable_multipass_extraction and notes_data:
            logger.info(f"Running Pass 2 extraction for turn {turn_id} (found {len(notes_data)} notes in Pass 1)")
            update_extraction_progress(turn_id, 'Extracting notes (Pass 2)', 1, 4, f'Found {len(notes_data)} notes in Pass 1, running Pass 2...')

            # Format Pass 1 facts for Pass 2 prompt
            pass1_facts_str = "\n".join([
                f"- {note['content']}" for note in notes_data
            ])

            # Generate Pass 2 prompt
            pass2_prompt = EXTRACTION_PROMPT_PASS2.format(
                user_message=turn.user_message,
                pass1_facts=pass1_facts_str
            )

            # Call LLM for Pass 2 extraction
            try:
                pass2_response = llm_service.generate_text(
                    prompt=pass2_prompt,
                    max_tokens=1000
                )

                if pass2_response['success']:
                    # Parse Pass 2 JSON response
                    pass2_text = pass2_response['text'].strip()

                    # Extract JSON from markdown code blocks if present
                    if "```json" in pass2_text:
                        json_start = pass2_text.find("```json") + 7
                        json_end = pass2_text.find("```", json_start)
                        pass2_text = pass2_text[json_start:json_end].strip()
                    elif "```" in pass2_text:
                        json_start = pass2_text.find("```") + 3
                        json_end = pass2_text.find("```", json_start)
                        pass2_text = pass2_text[json_start:json_end].strip()

                    pass2_data = json.loads(pass2_text)
                    pass2_notes = pass2_data.get('notes', [])

                    if pass2_notes:
                        logger.info(f"Pass 2 found {len(pass2_notes)} additional notes")
                        # Merge Pass 2 notes into notes_data
                        notes_data.extend(pass2_notes)
                    else:
                        logger.info("Pass 2 found no additional notes")
                else:
                    logger.warning(f"Pass 2 extraction failed: {pass2_response.get('error')}")
            except Exception as e:
                logger.warning(f"Pass 2 extraction failed with exception: {e}. Continuing with Pass 1 results only.")

        if not notes_data:
            logger.warning(f"No notes extracted from turn {turn_id}")
            turn.extracted = True
            turn.save(update_fields=['extracted'])
            update_extraction_progress(turn_id, 'Completed', 4, 4, 'No notes extracted')
            return {"status": "completed", "notes_created": 0}

        # Phase 2-4: Process each note (enrichment, embedding, linking, evolution)
        total_notes = len(notes_data)
        update_extraction_progress(turn_id, 'Processing notes', 2, 4, f'Processing {total_notes} notes...')

        # Validate and store notes
        notes_created = 0
        for idx, note_data in enumerate(notes_data, 1):
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

            # Phase 2: A-MEM enrichment
            update_extraction_progress(turn_id, f'Enriching note {idx}/{total_notes}', 2, 4,
                                      f'{note_data["content"][:50]}...')

            from .amem_service import amem_service
            try:
                enrichment = amem_service.enrich_note(note)

                # Update note with A-MEM attributes
                note.keywords = enrichment['keywords']
                note.llm_tags = enrichment['llm_tags']
                note.contextual_description = enrichment['contextual_description']
                note.is_amem_enriched = True
                note.save(update_fields=['keywords', 'llm_tags', 'contextual_description', 'is_amem_enriched'])

                logger.info(f"A-MEM enrichment: {len(enrichment['keywords'])} keywords, {len(enrichment['llm_tags'])} tags")
            except Exception as e:
                logger.warning(f"A-MEM enrichment failed for note {note.id}: {e}. Continuing with basic note.")
                # Continue with non-enriched note

            # Generate A-MEM embedding (multi-attribute if enriched, content-only as fallback)
            try:
                if note.is_amem_enriched:
                    embedding = amem_service.generate_amem_embedding(note)
                else:
                    # Fallback to content-only embedding
                    embedding_result = llm_service.get_embeddings([note.content])
                    if not embedding_result['success']:
                        raise ValueError(f"Embedding generation failed: {embedding_result['error']}")
                    embedding = embedding_result['embeddings'][0]
            except Exception as e:
                logger.error(f"Failed to embed note {note.id}: {e}")
                note.delete()  # Rollback
                continue

            # Store in vector DB with A-MEM metadata
            vector_id = vector_service.store_embedding(
                embedding=embedding,
                user_id=str(turn.user_id),
                metadata={
                    'type': 'atomic_note',
                    'note_id': str(note.id),
                    'note_type': note.note_type,
                    'confidence': note.confidence,
                    'timestamp': note.created_at.isoformat(),
                    # A-MEM attributes for rich metadata
                    'keywords': note.keywords if note.is_amem_enriched else [],
                    'llm_tags': note.llm_tags if note.is_amem_enriched else [],
                    'is_amem_enriched': note.is_amem_enriched
                }
            )

            # Update note with vector_id
            note.vector_id = vector_id
            note.save(update_fields=['vector_id'])

            # Phase 3 & 4: Link Generation + Memory Evolution
            update_extraction_progress(turn_id, f'Generating links {idx}/{total_notes}', 3, 4,
                                      f'{note_data["content"][:50]}...')

            # Generate links to related notes and evolve neighbor memories
            try:
                # Get neighbor notes for both linking and evolution
                if note.is_amem_enriched:
                    # Find similar notes (same process as link generation)
                    note_embedding = amem_service.generate_amem_embedding(note)
                    similar_results = vector_service.search_similar(
                        embedding=note_embedding,
                        user_id=str(note.user_id),
                        limit=6,  # top-5 + self
                        score_threshold=0.5
                    )

                    # Get neighbor note objects
                    neighbor_ids = [
                        r['metadata']['note_id']
                        for r in similar_results
                        if r['metadata'].get('note_id') != str(note.id)
                    ][:5]

                    if neighbor_ids:
                        neighbors = list(AtomicNote.objects.filter(id__in=neighbor_ids))

                        # Phase 3: Generate links
                        link_specs = amem_service.generate_links(note, k=5)
                        links_created = 0

                        from .models import NoteRelationship
                        for link_spec in link_specs:
                            try:
                                relationship = NoteRelationship.objects.create(
                                    from_note_id=note.id,
                                    to_note_id=link_spec['target_note_id'],
                                    relationship_type=link_spec['relationship_type'],
                                    strength=link_spec['strength']
                                )
                                links_created += 1
                                logger.info(
                                    f"Created link: {note.id} -{link_spec['relationship_type']}-> "
                                    f"{link_spec['target_note_id']} (strength: {link_spec['strength']:.2f})"
                                )
                            except Exception as e:
                                logger.warning(f"Failed to create link: {e}")

                        if links_created > 0:
                            logger.info(f"Created {links_created} links for note {note.id}")

                        # Phase 4: Memory Evolution
                        update_extraction_progress(turn_id, f'Evolving memories {idx}/{total_notes}', 4, 4,
                                                  f'Updating {len(neighbors)} related notes...')

                        # Evolve neighbor memories based on new information
                        try:
                            evolution_result = amem_service.evolve_memories(note, neighbors)
                            if evolution_result['evolved']:
                                logger.info(
                                    f"Memory evolution: {len(evolution_result['evolved'])} notes evolved "
                                    f"for note {note.id}"
                                )
                        except Exception as e:
                            logger.warning(f"Memory evolution failed for note {note.id}: {e}")

            except Exception as e:
                logger.warning(f"Link generation/evolution failed for note {note.id}: {e}")
                # Continue anyway - note is already created

            notes_created += 1
            logger.info(f"Created atomic note: {note.content[:50]}... (type: {note.note_type})")

        # Mark turn as extracted
        turn.extracted = True
        turn.save(update_fields=['extracted'])

        # Final progress update
        update_extraction_progress(turn_id, 'Completed', 4, 4, f'Successfully extracted {notes_created} notes')

        logger.info(f"Successfully extracted {notes_created} notes from turn {turn_id}")

        # Clean up progress cache after a short delay (task is done)
        from django.core.cache import cache
        cache.delete(f'extraction_progress_{turn_id}')

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
# Helper: Schedule Extraction Task
# =============================================================================

def schedule_extraction(turn_id: str, delay_seconds: int = 0):
    """
    Schedule extraction task for a conversation turn

    Args:
        turn_id: UUID of the ConversationTurn
        delay_seconds: Optional delay before queueing (default: 0 = queue immediately)
                      Worker processes async when available. Delay only needed for
                      specific use cases (e.g., waiting for conversation to complete)
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

        # NOTE: Relationship building has been removed as it was causing worker failures
        # The extraction task already handles A-MEM link generation and evolution inline
        # See extract_atomic_notes() lines 451-513 for in-task relationship handling

    else:
        logger.error(f"Extraction task {task.name} failed: {task.result}")


# =============================================================================
# Nightly Relationship Building for All Users
# =============================================================================

def nightly_relationship_building_all_users() -> Dict[str, Any]:
    """
    Nightly task to build relationships for all users (scheduled task)

    NOTE: This task has been disabled as relationship building now happens
    inline during extraction (see extract_atomic_notes lines 451-513).
    A-MEM link generation and memory evolution are handled automatically
    when each note is created.

    This function is kept for backward compatibility with scheduled tasks
    but performs no operations.

    Returns:
        Dict with processing results
    """
    logger.info("Nightly relationship building task called (currently disabled - relationships built inline)")

    return {
        "status": "completed",
        "users_processed": 0,
        "total_users": 0,
        "relationships_created": 0,
        "message": "Relationship building now happens inline during extraction"
    }
