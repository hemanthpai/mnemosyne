"""
Graph search and traversal service

Implements A-MEM style knowledge graph operations:
- Vector search for atomic notes
- Graph traversal to find related notes
- Ranking by relevance and importance

Based on A-MEM's dynamic knowledge graph approach where notes
are interconnected through relationships, enabling richer context retrieval.
"""

import logging
import json
from typing import List, Dict, Any, Set
from collections import deque

from .models import AtomicNote, NoteRelationship
from .vector_service import vector_service
from .llm_service import llm_service
from .settings_model import Settings

logger = logging.getLogger(__name__)

QUERY_EXPANSION_PROMPT = """Expand this search query into 3-5 concrete variations that capture different aspects.

Query: "{query}"

Generate variations that:
- Use specific, concrete language (avoid abstract terms)
- Cover different facets of the query topic
- Are suitable for matching against factual statements
- Include both direct terms and related concepts

Examples:
Query: "music preferences"
Variations:
- "favorite music genres"
- "artists they listen to"
- "concert experiences"
- "music they enjoy"

Query: "programming languages they know"
Variations:
- "programming languages they use"
- "coding skills"
- "languages they write code in"
- "technical programming expertise"

Now expand the query above. Return ONLY a JSON array of strings (no other text):
["variation1", "variation2", "variation3"]"""


class GraphService:
    """Service for graph-based search and traversal of atomic notes"""

    def search_atomic_notes(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Search atomic notes using vector similarity

        Args:
            query: Search query text
            user_id: UUID of the user
            limit: Maximum number of results
            threshold: Minimum similarity score

        Returns:
            List of atomic notes with scores
        """
        try:
            # Generate query embedding
            embedding_result = llm_service.get_embeddings([query])
            if not embedding_result['success']:
                raise ValueError(f"Failed to generate query embedding: {embedding_result['error']}")

            # Search vector DB for atomic notes
            search_results = vector_service.search_similar(
                embedding=embedding_result['embeddings'][0],
                user_id=user_id,
                limit=limit * 2,  # Get more results for filtering
                score_threshold=threshold
            )

            # Filter for atomic notes only (not conversation turns)
            note_results = [
                r for r in search_results
                if r['metadata'].get('type') == 'atomic_note'
            ][:limit]

            # Get note IDs
            note_ids = [r['metadata']['note_id'] for r in note_results]
            notes = AtomicNote.objects.filter(id__in=note_ids)
            notes_by_id = {str(n.id): n for n in notes}

            # Combine results
            results = []
            for result in note_results:
                note_id = result['metadata']['note_id']
                if note_id in notes_by_id:
                    note = notes_by_id[note_id]
                    results.append({
                        'id': str(note.id),
                        'content': note.content,
                        'note_type': note.note_type,
                        'context': note.context,
                        'confidence': note.confidence,
                        'importance_score': note.importance_score,
                        'tags': note.tags,
                        'created_at': note.created_at.isoformat(),
                        'score': result['score'],
                        'source': 'atomic_note'
                    })

            logger.info(f"Found {len(results)} atomic notes for query: {query[:50]}...")
            return results

        except Exception as e:
            logger.error(f"Atomic note search failed: {e}")
            return []

    def expand_query(self, query: str) -> List[str]:
        """
        Expand query into multiple semantic variations using LLM

        Uses the generation LLM to expand abstract queries into concrete variations
        that better match against specific atomic notes.

        Args:
            query: Original search query

        Returns:
            List of query variations (includes original query + expansions)
        """
        try:
            # Generate expansion prompt
            prompt = QUERY_EXPANSION_PROMPT.format(query=query)

            # Call generation LLM
            response = llm_service.generate_text(
                prompt=prompt,
                max_tokens=200,
                temperature=0.3  # Lower temperature for more focused expansions
            )

            if not response['success']:
                logger.warning(f"Query expansion failed: {response.get('error')}. Using original query only.")
                return [query]

            # Parse JSON response
            response_text = response['text'].strip()

            # Extract JSON array from response (handle cases where LLM adds extra text)
            try:
                # Try to find JSON array in response
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1

                if start_idx >= 0 and end_idx > start_idx:
                    json_text = response_text[start_idx:end_idx]
                    variations = json.loads(json_text)
                else:
                    raise ValueError("No JSON array found in response")

            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse query expansion JSON: {e}. Response: {response_text[:100]}")
                return [query]

            # Validate result
            if not isinstance(variations, list) or not variations:
                logger.warning(f"Invalid query expansion result. Using original query only.")
                return [query]

            # Always include original query + variations
            all_queries = [query] + [str(v) for v in variations if v and str(v) != query]

            logger.info(f"Expanded query '{query[:50]}...' into {len(all_queries)} variations")
            return all_queries[:6]  # Cap at 6 total (original + 5 variations)

        except Exception as e:
            logger.error(f"Query expansion error: {e}. Using original query only.")
            return [query]

    def search_atomic_notes_with_expansion(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        threshold: float = 0.5,
        use_expansion: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search atomic notes with optional query expansion

        When expansion is enabled, expands the query into multiple variations
        and fuses results using maximum score across all variations.

        Args:
            query: Search query text
            user_id: UUID of the user
            limit: Maximum number of results
            threshold: Minimum similarity score
            use_expansion: Whether to use query expansion

        Returns:
            List of atomic notes with scores
        """
        # Check settings
        settings = Settings.get_settings()
        if not use_expansion or not settings.enable_query_expansion:
            # No expansion: use original search
            return self.search_atomic_notes(query, user_id, limit, threshold)

        try:
            # Expand query
            query_variations = self.expand_query(query)

            # Search with each variation and collect results
            all_results: Dict[str, Dict[str, Any]] = {}  # note_id → best result

            for variant in query_variations:
                # Search with larger limit to cast wider net
                variant_results = self.search_atomic_notes(
                    query=variant,
                    user_id=user_id,
                    limit=limit * 3,  # Get more candidates
                    threshold=max(0.0, threshold - 0.2)  # Lower threshold for recall
                )

                # Merge results, keeping best score for each note
                for result in variant_results:
                    note_id = result['id']
                    score = result['score']

                    if note_id not in all_results or score > all_results[note_id]['score']:
                        all_results[note_id] = result

            # Sort by score and return top-k
            final_results = sorted(
                all_results.values(),
                key=lambda x: x['score'],
                reverse=True
            )[:limit]

            logger.info(
                f"Query expansion search: {len(query_variations)} variations → "
                f"{len(all_results)} unique results → top {len(final_results)} returned"
            )

            return final_results

        except Exception as e:
            logger.error(f"Search with expansion failed: {e}. Falling back to basic search.")
            return self.search_atomic_notes(query, user_id, limit, threshold)

    def traverse_graph(
        self,
        start_note_ids: List[str],
        depth: int = 2,
        relationship_types: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Traverse the knowledge graph from starting notes

        Uses BFS (breadth-first search) to explore related notes up to
        a specified depth, following relationship edges.

        Args:
            start_note_ids: List of note IDs to start traversal from
            depth: Maximum depth to traverse (default: 2 hops)
            relationship_types: Filter by relationship types (None = all types)

        Returns:
            List of related notes with their relationship info
        """
        if not start_note_ids:
            return []

        try:
            visited: Set[str] = set()
            results: List[Dict[str, Any]] = []
            queue = deque()

            # Initialize queue with starting notes
            for note_id in start_note_ids:
                queue.append((note_id, 0, None, None))  # (note_id, current_depth, rel_type, rel_strength)
                visited.add(note_id)

            while queue:
                note_id, current_depth, rel_type, rel_strength = queue.popleft()

                # Get the note
                try:
                    note = AtomicNote.objects.get(id=note_id)
                except AtomicNote.DoesNotExist:
                    continue

                # Add to results (skip start notes at depth 0)
                if current_depth > 0:
                    results.append({
                        'id': str(note.id),
                        'content': note.content,
                        'note_type': note.note_type,
                        'context': note.context,
                        'confidence': note.confidence,
                        'importance_score': note.importance_score,
                        'tags': note.tags,
                        'created_at': note.created_at.isoformat(),
                        'depth': current_depth,
                        'relationship_type': rel_type,
                        'relationship_strength': rel_strength,
                        'source': 'graph_traversal'
                    })

                # Stop if we've reached max depth
                if current_depth >= depth:
                    continue

                # Get outgoing relationships
                relationships = NoteRelationship.objects.filter(
                    from_note_id=note_id
                )

                # Filter by relationship type if specified
                if relationship_types:
                    relationships = relationships.filter(
                        relationship_type__in=relationship_types
                    )

                # Add connected notes to queue
                for rel in relationships:
                    connected_id = str(rel.to_note_id)
                    if connected_id not in visited:
                        visited.add(connected_id)
                        queue.append((
                            connected_id,
                            current_depth + 1,
                            rel.relationship_type,
                            rel.strength
                        ))

            logger.info(f"Graph traversal found {len(results)} related notes (depth={depth})")
            return results

        except Exception as e:
            logger.error(f"Graph traversal failed: {e}")
            return []

    def search_with_graph(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        threshold: float = 0.5,
        traverse_depth: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Search atomic notes and traverse graph for related context

        Combines vector search with graph traversal to find both directly
        relevant notes and their related context.

        Args:
            query: Search query text
            user_id: UUID of the user
            limit: Maximum number of direct results
            threshold: Minimum similarity score
            traverse_depth: Depth to traverse graph (0 = no traversal)

        Returns:
            List of notes (direct matches + graph-traversed related notes)
        """
        try:
            # Step 1: Vector search for directly relevant notes
            direct_results = self.search_atomic_notes(
                query=query,
                user_id=user_id,
                limit=limit,
                threshold=threshold
            )

            if not direct_results:
                return []

            # If no graph traversal requested, return direct results
            if traverse_depth == 0:
                return direct_results

            # Step 2: Traverse graph from direct results
            start_note_ids = [r['id'] for r in direct_results]
            related_results = self.traverse_graph(
                start_note_ids=start_note_ids,
                depth=traverse_depth
            )

            # Step 3: Combine and deduplicate
            all_results = direct_results.copy()
            seen_ids = {r['id'] for r in direct_results}

            for related in related_results:
                if related['id'] not in seen_ids:
                    all_results.append(related)
                    seen_ids.add(related['id'])

            # Step 4: Rank by combined score
            # Direct results get their vector similarity score
            # Related results get importance_score * relationship_strength * depth_penalty
            for result in all_results:
                if result.get('source') == 'atomic_note':
                    # Direct match: use vector score as-is
                    result['combined_score'] = result['score']
                else:
                    # Graph-traversed: importance * strength / depth
                    depth_penalty = 1.0 / (result['depth'] + 1)
                    result['combined_score'] = (
                        result['importance_score'] *
                        result.get('relationship_strength', 0.5) *
                        depth_penalty
                    )

            # Sort by combined score
            all_results.sort(key=lambda x: x['combined_score'], reverse=True)

            logger.info(
                f"Search with graph: {len(direct_results)} direct + "
                f"{len(related_results)} related = {len(all_results)} total"
            )

            return all_results

        except Exception as e:
            logger.error(f"Search with graph failed: {e}")
            return []


# Global instance
graph_service = GraphService()
