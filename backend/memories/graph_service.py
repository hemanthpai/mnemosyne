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
from .reranking_service import get_reranking_service
from .bm25_service import get_bm25_service, reciprocal_rank_fusion

logger = logging.getLogger(__name__)

QUERY_EXPANSION_PROMPT = """Expand this search query into 3-5 concrete variations that capture different aspects.

Query: "{query}"

Generate variations that:
- Use specific, concrete language (avoid abstract terms)
- Cover different facets of the query topic
- Are suitable for matching against factual statements about a person
- Include both direct terms and related concepts
- Consider different ways people might express the same information

Return ONLY a JSON array of strings (no other text or explanation):
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

    def rewrite_query_with_context(
        self,
        query: str,
        recent_context: List[str] = None
    ) -> str:
        """
        Rewrite query using conversation context for better relevance

        Uses recent conversation turns to disambiguate and refine the search query.
        Example:
        - Context: ["User: What does Sarah like?"]
        - Query: "frontend development tools"
        - Rewritten: "Sarah's preferred frontend frameworks and libraries"

        Args:
            query: Original search query
            recent_context: List of recent conversation messages (last 3-5 turns)

        Returns:
            Rewritten query (or original if rewriting fails or no context)
        """
        # If no context provided, return original query
        if not recent_context or len(recent_context) == 0:
            return query

        try:
            # Build context string
            context_str = "\n".join(recent_context[-3:])  # Last 3 turns

            # Prompt for context-aware rewriting
            prompt = f"""Given this conversation context and search query, rewrite the query to be more specific and targeted.

Recent conversation:
{context_str}

Original query: {query}

Rewrite the query to capture exactly what information would be most relevant to continue this conversation. Consider:
- What aspect of the topic matters (preferences, skills, experiences, opinions, facts)
- Who or what is being asked about (specific person, concept, etc.)
- Any implied filters from context (time period, category, etc.)

Respond with ONLY the rewritten query, nothing else.

Rewritten query:"""

            # Call generation LLM
            response = llm_service.generate_text(
                prompt=prompt,
                max_tokens=50,
                temperature=0.3  # Lower temperature for focused rewriting
            )

            if not response['success']:
                logger.warning(f"Query rewriting failed: {response.get('error')}. Using original query.")
                return query

            # Get rewritten query
            rewritten = response['text'].strip()

            # Basic validation
            if len(rewritten) < 3 or len(rewritten) > 200:
                logger.warning(f"Invalid rewritten query length: {len(rewritten)}. Using original.")
                return query

            logger.info(f"Rewrote query: '{query}' → '{rewritten}'")
            return rewritten

        except Exception as e:
            logger.error(f"Query rewriting error: {e}. Using original query.")
            return query

    def search_atomic_notes_with_expansion(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        threshold: float = 0.5,
        use_expansion: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search atomic notes with optional query expansion, hybrid search, and reranking

        When expansion is enabled, expands the query into multiple variations
        and fuses results using maximum score across all variations.

        When hybrid search is enabled, combines vector search with BM25 keyword search
        using Reciprocal Rank Fusion (RRF) for improved recall.

        When reranking is enabled, retrieves more candidates and reranks them
        for improved precision.

        Args:
            query: Search query text
            user_id: UUID of the user
            limit: Maximum number of results to return
            threshold: Minimum similarity score
            use_expansion: Whether to use query expansion

        Returns:
            List of atomic notes with scores
        """
        # Get settings
        settings = Settings.get_settings()
        
        # Determine candidate limit for reranking
        enable_reranking = settings.enable_reranking
        enable_hybrid = getattr(settings, 'enable_hybrid_search', True)  # Default to True
        
        if enable_reranking:
            # Retrieve more candidates for reranking
            candidate_limit = limit * settings.reranking_candidate_multiplier
            logger.info(f"Reranking enabled: retrieving {candidate_limit} candidates to rerank top {limit}")
        else:
            candidate_limit = limit

        # STEP 1: Perform vector search (with or without expansion)
        if not use_expansion or not settings.enable_query_expansion:
            # No expansion: use original search
            vector_results = self.search_atomic_notes(query, user_id, candidate_limit, threshold)
        else:
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
                        limit=candidate_limit * 2,  # Get even more candidates with expansion
                        threshold=max(0.0, threshold - 0.2)  # Lower threshold for recall
                    )

                    # Merge results, keeping best score for each note
                    for result in variant_results:
                        note_id = result['id']
                        score = result['score']

                        if note_id not in all_results or score > all_results[note_id]['score']:
                            all_results[note_id] = result

                # Sort by score and take top candidates
                vector_results = sorted(
                    all_results.values(),
                    key=lambda x: x['score'],
                    reverse=True
                )[:candidate_limit]

                logger.info(
                    f"Query expansion search: {len(query_variations)} variations → "
                    f"{len(all_results)} unique results → top {len(vector_results)} candidates"
                )

            except Exception as e:
                logger.error(f"Search with expansion failed: {e}. Falling back to basic search.")
                vector_results = self.search_atomic_notes(query, user_id, candidate_limit, threshold)

        # STEP 2: Apply hybrid search (BM25 + Vector) if enabled
        if enable_hybrid and vector_results:
            try:
                logger.info(f"Hybrid search enabled: combining vector search with BM25")
                
                # Get BM25 service
                bm25_service = get_bm25_service()
                
                # Perform BM25 search (get more candidates for diversity)
                bm25_results = bm25_service.search(
                    query=query,
                    user_id=user_id,
                    limit=candidate_limit
                )
                
                if bm25_results:
                    # Fetch full note data for BM25 results
                    bm25_note_ids = [r['note_id'] for r in bm25_results]
                    bm25_notes = AtomicNote.objects.filter(
                        id__in=bm25_note_ids,
                        user_id=user_id
                    ).values('id', 'content', 'contextual_description', 'importance', 'created_at')
                    
                    # Build lookup dict for BM25 scores
                    bm25_score_map = {r['note_id']: r['bm25_score'] for r in bm25_results}
                    
                    # Convert to result format with BM25 scores
                    bm25_results_full = []
                    for note in bm25_notes:
                        note_id = str(note['id'])
                        bm25_results_full.append({
                            'id': note_id,
                            'note_id': note_id,
                            'content': note['content'],
                            'contextual_description': note['contextual_description'],
                            'importance': note['importance'],
                            'created_at': note['created_at'],
                            'bm25_score': bm25_score_map.get(note_id, 0.0),
                            'score': bm25_score_map.get(note_id, 0.0)  # Use BM25 as score for RRF
                        })
                    
                    # Prepare for RRF: normalize note_id field
                    vector_results_normalized = [
                        {**r, 'note_id': r.get('id', r.get('note_id'))} 
                        for r in vector_results
                    ]
                    
                    # Apply Reciprocal Rank Fusion
                    fused_results = reciprocal_rank_fusion(
                        rankings=[vector_results_normalized, bm25_results_full],
                        k=60,
                        id_key='note_id'
                    )
                    
                    # Take top candidates after fusion
                    results = fused_results[:candidate_limit]
                    
                    logger.info(
                        f"Hybrid search: {len(vector_results)} vector + {len(bm25_results_full)} BM25 "
                        f"→ {len(fused_results)} fused → top {len(results)} candidates"
                    )
                else:
                    logger.info("BM25 returned no results, using vector results only")
                    results = vector_results
                    
            except Exception as e:
                logger.error(f"Hybrid search failed: {e}. Using vector results only.")
                results = vector_results
        else:
            # No hybrid search, use vector results as-is
            results = vector_results

        # STEP 3: Apply reranking if enabled
        if enable_reranking and results and len(results) > limit:
            try:
                logger.info(f"Reranking {len(results)} candidates with provider: {settings.reranking_provider}")
                
                # Get reranking service
                reranker = get_reranking_service()
                
                # Extract document texts for reranking
                documents = [result.get('content', '') for result in results]
                
                # Rerank
                reranked_indices = reranker.rerank(query, documents, top_k=limit)
                
                # Reorder results based on reranker output
                reranked_results = []
                for idx, rerank_score in reranked_indices:
                    result = results[idx].copy()
                    # Store all scores (vector, BM25 if present, RRF if present, and rerank)
                    if 'rrf_score' in result:
                        result['hybrid_rrf_score'] = result.get('rrf_score')
                    if 'bm25_score' not in result and 'score' in result:
                        result['vector_score'] = result['score']
                    result['rerank_score'] = rerank_score
                    result['score'] = rerank_score  # Use rerank score as primary
                    reranked_results.append(result)
                
                logger.info(f"Reranking complete: {len(reranked_results)} results returned")
                return reranked_results
                
            except Exception as e:
                logger.error(f"Reranking failed: {e}. Returning original results.")
                # Fall through to return original results
        
        # Return top-k results (no reranking or reranking disabled)
        return results[:limit]

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
