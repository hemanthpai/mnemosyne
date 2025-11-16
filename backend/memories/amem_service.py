"""
A-MEM Service

Implements A-MEM's note construction and evolution from the NeurIPS 2025 paper.
Based on: "A-Mem: Agentic Memory for LLM Agents" by Xu et al.

Key Components:
- Note Construction (Section 3.1): Generate keywords, tags, and contextual descriptions
- Multi-Attribute Embeddings (Equation 3): Embed concat(content, keywords, tags, context)
- Link Generation (Section 3.2): LLM-driven relationship building
- Memory Evolution (Section 3.3): Continuous refinement of existing memories
"""

import logging
import json
from typing import Dict, Any, List
from .prompts import (
    AMEM_NOTE_CONSTRUCTION_PROMPT,
    AMEM_LINK_GENERATION_PROMPT,
    AMEM_MEMORY_EVOLUTION_PROMPT
)

logger = logging.getLogger(__name__)


class AMEMService:
    """
    Service for A-MEM-style note construction and evolution

    Implements the A-MEM architecture for atomic note enrichment,
    multi-attribute embeddings, and knowledge graph evolution.
    """

    def __init__(self):
        """Initialize AMEM service"""
        # Lazy load services to avoid circular imports
        self._llm_service = None
        self._vector_service = None

    @property
    def llm_service(self):
        """Lazy load LLM service"""
        if self._llm_service is None:
            from .llm_service import llm_service
            self._llm_service = llm_service
        return self._llm_service

    @property
    def vector_service(self):
        """Lazy load vector service"""
        if self._vector_service is None:
            from .vector_service import vector_service
            self._vector_service = vector_service
        return self._vector_service

    # =========================================================================
    # Phase 1: Note Enrichment (Section 3.1)
    # =========================================================================

    def enrich_note(self, note) -> Dict[str, Any]:
        """
        Enrich atomic note with A-MEM attributes (Ki, Gi, Xi)

        Implements Equation 2 from A-MEM paper:
        Ki, Gi, Xi ← LLM(ci || ti || Ps1)

        Args:
            note: AtomicNote instance to enrich

        Returns:
            Dict with:
            - keywords: List[str] - LLM-generated keywords (Ki)
            - llm_tags: List[str] - LLM-generated tags (Gi)
            - contextual_description: str - Rich contextual summary (Xi)
        """
        try:
            logger.info(f"Enriching note {note.id} with A-MEM attributes")

            # Get settings for configurable parameters
            from .settings_model import Settings
            settings = Settings.get_settings()

            # Format prompt with note content and timestamp
            prompt = AMEM_NOTE_CONSTRUCTION_PROMPT.format(
                content=note.content,
                timestamp=note.created_at.isoformat()
            )

            # Call generation LLM (Equation 2)
            response = self.llm_service.generate_text(
                prompt=prompt,
                max_tokens=settings.amem_enrichment_max_tokens,
                temperature=settings.amem_enrichment_temperature
            )

            if not response['success']:
                logger.error(f"LLM enrichment failed: {response.get('error')}")
                return self._fallback_enrichment(note)

            # Parse JSON response
            enrichment = self._parse_enrichment_response(response['text'])

            if not enrichment:
                logger.warning("Failed to parse LLM response, using fallback")
                return self._fallback_enrichment(note)

            logger.info(
                f"Successfully enriched note {note.id}: "
                f"{len(enrichment['keywords'])} keywords, "
                f"{len(enrichment['llm_tags'])} tags"
            )
            return enrichment

        except Exception as e:
            logger.error(f"Note enrichment error for {note.id}: {e}")
            return self._fallback_enrichment(note)

    def _parse_enrichment_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON response from LLM"""
        try:
            # Extract JSON from response (handle extra text)
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
                data = json.loads(json_text)

                # Validate structure
                if 'keywords' in data and 'context' in data and 'tags' in data:
                    return {
                        'keywords': data['keywords'][:5],  # Max 5 keywords
                        'contextual_description': data['context'],
                        'llm_tags': data['tags'][:5]  # Max 5 tags
                    }

            return None

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}. Response: {response_text[:200]}")
            return None

    def _fallback_enrichment(self, note) -> Dict[str, Any]:
        """Fallback enrichment if LLM fails"""
        logger.warning(f"Using fallback enrichment for note {note.id}")
        return {
            'keywords': [],
            'contextual_description': note.content[:200],  # First 200 chars
            'llm_tags': [note.note_type] if note.note_type else []
        }

    # =========================================================================
    # Phase 2: Multi-Attribute Embeddings (Equation 3)
    # =========================================================================

    def generate_amem_embedding(self, note) -> List[float]:
        """
        Generate A-MEM-style embedding from all note attributes

        Implements Equation 3 from A-MEM paper:
        ei = fenc[concat(ci, Ki, Gi, Xi)]

        This is the KEY INNOVATION of A-MEM: instead of embedding only content,
        we embed the concatenation of content, keywords, tags, and contextual
        description. This creates semantically richer embeddings that dramatically
        improve recall.

        Args:
            note: Enriched AtomicNote with A-MEM attributes

        Returns:
            Embedding vector (List[float])
        """
        try:
            # Concatenate ALL textual attributes (Equation 3)
            combined_text = self._concatenate_attributes(note)

            # Generate embedding from combined text
            embedding_result = self.llm_service.get_embeddings([combined_text])

            if not embedding_result['success']:
                raise ValueError(
                    f"Embedding generation failed: {embedding_result['error']}"
                )

            embedding = embedding_result['embeddings'][0]

            logger.debug(
                f"Generated A-MEM embedding for note {note.id} "
                f"(combined_text_length={len(combined_text)})"
            )

            return embedding

        except Exception as e:
            logger.error(f"A-MEM embedding generation failed for {note.id}: {e}")
            raise

    def _concatenate_attributes(self, note) -> str:
        """
        Concatenate note attributes following A-MEM Equation 3 (optimized)

        Format: content [repeated for emphasis] keywords tags contextual_description

        Optimizations:
        - Content repeated for 2x weight (most important for matching)
        - Keywords limited to top 3 (most discriminative)
        - Tags limited to top 3 (avoid noise)
        - Context truncated to 100 chars (avoid dilution)
        - No literal "Keywords:", "Tags:" strings (save embedding space)
        - Space-separated (not newline) for better semantic cohesion

        Args:
            note: AtomicNote with A-MEM attributes

        Returns:
            Combined text string for embedding
        """
        parts = []

        # Content (ci) - The core atomic fact (BOOSTED by repetition)
        if note.content:
            parts.append(note.content)
            parts.append(note.content)  # Repeat for 2x weight

        # Keywords (Ki) - Specific terms capturing key concepts (TOP 3 ONLY)
        if note.keywords:
            top_keywords = note.keywords[:3]
            parts.append(" ".join(top_keywords))

        # Tags (Gi) - Broad categorical labels (TOP 3 ONLY)
        if note.llm_tags:
            top_tags = note.llm_tags[:3]
            parts.append(" ".join(top_tags))

        # Contextual Description (Xi) - Rich semantic summary (TRUNCATED)
        if note.contextual_description:
            # Limit to 100 chars to avoid diluting content semantics
            context_short = note.contextual_description[:100]
            parts.append(context_short)

        # Join with spaces (not newlines) for better semantic cohesion
        combined = " ".join(parts)

        logger.debug(
            f"Concatenated attributes for note {note.id} "
            f"(length={len(combined)}, content_weight=2x, keywords={len(note.keywords or [])}→{len(note.keywords[:3] if note.keywords else [])}): "
            f"{combined[:150]}..."
        )

        return combined

    # =========================================================================
    # Phase 3: Link Generation (Section 3.2) - TODO: Implement later
    # =========================================================================

    def generate_links(self, new_note, k: int = None) -> List[Dict[str, Any]]:
        """
        Generate links using A-MEM's LLM-driven approach

        Implements Section 3.2, Equations 4-6:
        1. Find top-k similar notes by embedding (Equations 4-5)
        2. Use LLM to analyze and create meaningful connections (Equation 6)

        Args:
            new_note: Newly created note
            k: Number of nearest neighbors to consider (None = use settings default)

        Returns:
            List of link specifications with structure:
            [
                {
                    'target_note_id': str,
                    'relationship_type': str,
                    'strength': float,
                    'rationale': str
                }
            ]
        """
        try:
            # Get settings for configurable parameters
            from .settings_model import Settings
            settings = Settings.get_settings()

            # Use settings k if not provided
            if k is None:
                k = settings.amem_link_generation_k

            logger.info(f"Generating links for note {new_note.id} (k={k})")

            # Step 1: Find top-k similar notes (Equations 4-5)
            if not new_note.is_amem_enriched:
                logger.warning(f"Note {new_note.id} is not A-MEM enriched, skipping link generation")
                return []

            # Generate embedding for similarity search
            note_embedding = self.generate_amem_embedding(new_note)

            # Search for similar notes using vector similarity
            similar_results = self.vector_service.search_similar(
                embedding=note_embedding,
                user_id=str(new_note.user_id),
                limit=k + 1,  # +1 to account for self-match
                score_threshold=0.5  # Only consider reasonably similar notes
            )

            # Filter out self and get note objects
            from .models import AtomicNote
            neighbor_ids = [
                r['metadata']['note_id']
                for r in similar_results
                if r['metadata'].get('note_id') != str(new_note.id)
            ][:k]

            if not neighbor_ids:
                logger.info(f"No similar notes found for {new_note.id}")
                return []

            neighbors = AtomicNote.objects.filter(id__in=neighbor_ids)
            logger.info(f"Found {len(neighbors)} candidate neighbors for linking")

            # Step 2: Format neighbors for LLM prompt
            neighbors_text = self._format_neighbors_for_prompt(neighbors)

            # Step 3: Generate link prompt (Equation 6)
            prompt = AMEM_LINK_GENERATION_PROMPT.format(
                new_content=new_note.content,
                new_keywords=", ".join(new_note.keywords) if new_note.keywords else "None",
                new_context=new_note.contextual_description or new_note.context or "None",
                nearest_neighbors=neighbors_text
            )

            # Step 4: Call LLM for link analysis
            response = self.llm_service.generate_text(
                prompt=prompt,
                max_tokens=settings.amem_link_generation_max_tokens,
                temperature=settings.amem_link_generation_temperature
            )

            if not response['success']:
                logger.error(f"LLM link generation failed: {response.get('error')}")
                return []

            # Step 5: Parse link decisions
            links = self._parse_link_response(response['text'])

            logger.info(f"Generated {len(links)} links for note {new_note.id}")
            return links

        except Exception as e:
            logger.error(f"Link generation error for {new_note.id}: {e}")
            return []

    def _format_neighbors_for_prompt(self, neighbors) -> str:
        """Format neighbor notes for LLM prompt"""
        lines = []
        for i, note in enumerate(neighbors, 1):
            lines.append(f"{i}. ID: {note.id}")
            lines.append(f"   Content: {note.content}")
            lines.append(f"   Type: {note.note_type}")
            if note.keywords:
                lines.append(f"   Keywords: {', '.join(note.keywords)}")
            if note.contextual_description:
                lines.append(f"   Context: {note.contextual_description}")
            lines.append("")  # Blank line between notes
        return "\n".join(lines)

    def _parse_link_response(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse JSON response from link generation LLM"""
        try:
            # Extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
                data = json.loads(json_text)

                # Validate structure
                if not data.get('should_link', False):
                    logger.info("LLM decided no links should be created")
                    return []

                links = data.get('links', [])

                # Validate each link
                validated_links = []
                for link in links:
                    if all(k in link for k in ['target_note_id', 'relationship_type']):
                        # Validate UUID format
                        target_id = str(link['target_note_id'])
                        try:
                            import uuid
                            uuid.UUID(target_id)  # Will raise ValueError if invalid
                            validated_links.append({
                                'target_note_id': target_id,
                                'relationship_type': link['relationship_type'],
                                'strength': float(link.get('strength', 0.8)),
                                'rationale': link.get('rationale', '')
                            })
                        except ValueError:
                            logger.warning(f"Invalid UUID in link target_note_id: '{target_id}' - skipping link")
                    else:
                        logger.warning(f"Invalid link structure: {link}")

                return validated_links

            return []

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse link JSON: {e}. Response: {response_text[:200]}")
            return []
        except Exception as e:
            logger.error(f"Error parsing link response: {e}")
            return []

    # =========================================================================
    # Phase 4: Memory Evolution (Section 3.3) - TODO: Implement later
    # =========================================================================

    def evolve_memories(
        self,
        new_note,
        neighbor_notes: List
    ) -> Dict[str, Any]:
        """
        Evolve neighbor memories based on new note

        Implements Section 3.3, Equation 7:
        m*j ← LLM(mn || Mnear \ mj || mj || Ps3)

        This analyzes whether the new note suggests updates to existing
        neighbors (e.g., updated tags, refined context, merged notes).

        Args:
            new_note: Newly added note
            neighbor_notes: Similar notes to potentially evolve

        Returns:
            Dict with:
            - evolved: List[note_id] - IDs of notes that were updated
            - actions: List[str] - Actions taken
            - merged: List[note_id] - IDs of notes that were merged/deleted
        """
        try:
            if not neighbor_notes:
                return {'evolved': [], 'actions': [], 'merged': []}

            # Get settings for configurable parameters
            from .settings_model import Settings
            settings = Settings.get_settings()

            logger.info(f"Analyzing memory evolution for note {new_note.id} with {len(neighbor_notes)} neighbors")

            # Format neighbors for LLM prompt
            neighbors_text = self._format_neighbors_for_prompt(neighbor_notes)

            # Generate evolution prompt (Equation 7)
            prompt = AMEM_MEMORY_EVOLUTION_PROMPT.format(
                new_content=new_note.content,
                new_keywords=", ".join(new_note.keywords) if new_note.keywords else "None",
                new_context=new_note.contextual_description or new_note.context or "None",
                nearest_neighbors=neighbors_text
            )

            # Call LLM for evolution analysis
            response = self.llm_service.generate_text(
                prompt=prompt,
                max_tokens=settings.amem_evolution_max_tokens,
                temperature=settings.amem_evolution_temperature
            )

            if not response['success']:
                logger.error(f"LLM evolution analysis failed: {response.get('error')}")
                return {'evolved': [], 'actions': [], 'merged': []}

            # Parse evolution decisions
            evolution_result = self._parse_evolution_response(
                response['text'],
                new_note,
                neighbor_notes
            )

            if evolution_result['evolved']:
                logger.info(
                    f"Memory evolution: {len(evolution_result['evolved'])} notes evolved, "
                    f"actions: {evolution_result['actions']}"
                )

            return evolution_result

        except Exception as e:
            logger.error(f"Memory evolution error for {new_note.id}: {e}")
            return {'evolved': [], 'actions': [], 'merged': []}

    def _parse_evolution_response(
        self,
        response_text: str,
        new_note,
        neighbor_notes: List
    ) -> Dict[str, Any]:
        """Parse JSON response from memory evolution LLM"""
        try:
            # Extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
                data = json.loads(json_text)

                # Check if evolution is recommended
                if not data.get('should_evolve', False):
                    logger.info("LLM decided no memory evolution needed")
                    return {'evolved': [], 'actions': [], 'merged': []}

                actions = data.get('actions', [])
                evolved_ids = []
                merged_ids = []

                # Process evolution actions
                if 'strengthen' in actions or 'update_neighbor' in actions:
                    # Get tags and context updates
                    tags_to_update = data.get('tags_to_update', [])
                    new_contexts = data.get('new_context_neighborhood', [])
                    new_tags_list = data.get('new_tags_neighborhood', [])

                    # Update neighbors if we have new information
                    neighbors_by_id = {str(n.id): n for n in neighbor_notes}

                    for i, note in enumerate(neighbor_notes):
                        updated = False

                        # Update tags if provided
                        if i < len(new_tags_list) and new_tags_list[i]:
                            old_tags = note.llm_tags if note.llm_tags else []
                            new_tags = new_tags_list[i]
                            if new_tags != old_tags:
                                note.llm_tags = new_tags
                                updated = True
                                logger.info(f"Updated tags for {note.id}: {old_tags} → {new_tags}")

                        # Update context if provided
                        if i < len(new_contexts) and new_contexts[i]:
                            old_context = note.contextual_description
                            new_context = new_contexts[i]
                            if new_context != old_context:
                                note.contextual_description = new_context
                                updated = True
                                logger.info(f"Updated context for {note.id}")

                        if updated:
                            note.save(update_fields=['llm_tags', 'contextual_description'])
                            evolved_ids.append(str(note.id))

                # Check for merge suggestions
                if 'merge' in actions:
                    suggested_connections = data.get('suggested_connections', [])
                    # For now, just log merge suggestions - actual merging is complex
                    if suggested_connections:
                        logger.info(f"Merge suggested for notes: {suggested_connections}")
                        # Could implement actual merging later if needed

                return {
                    'evolved': evolved_ids,
                    'actions': actions,
                    'merged': merged_ids
                }

            return {'evolved': [], 'actions': [], 'merged': []}

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse evolution JSON: {e}. Response: {response_text[:200]}")
            return {'evolved': [], 'actions': [], 'merged': []}
        except Exception as e:
            logger.error(f"Error parsing evolution response: {e}")
            return {'evolved': [], 'actions': [], 'merged': []}


# Global instance
amem_service = AMEMService()
