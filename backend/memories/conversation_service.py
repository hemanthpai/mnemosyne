import logging
from typing import List, Dict, Any

from .models import ConversationTurn
from .vector_service import vector_service
from .llm_service import llm_service
from .cache_service import cache_service

logger = logging.getLogger(__name__)

# Lazy import graph service to avoid circular dependency
def _get_graph_service():
    """Lazy import graph service"""
    from .graph_service import graph_service
    return graph_service

# Import tasks for background extraction
# Lazy import to avoid circular dependency
def _schedule_extraction(turn_id: str):
    """Lazy import and schedule extraction task"""
    try:
        from .tasks import schedule_extraction
        schedule_extraction(turn_id)
    except ImportError:
        logger.warning("Django-Q not available, skipping background extraction")


class ConversationService:
    """Simple service for storing and searching conversations"""

    def store_turn(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        assistant_message: str
    ) -> ConversationTurn:
        """
        Store a conversation turn with embedding
        Fast: <100ms target

        Args:
            user_id: UUID of the user
            session_id: Session identifier
            user_message: User's message
            assistant_message: Assistant's response

        Returns:
            ConversationTurn: Created turn instance

        Raises:
            ValueError: If embedding generation fails
        """
        # Get next turn number
        last_turn = ConversationTurn.objects.filter(
            session_id=session_id
        ).order_by('-turn_number').first()
        turn_number = (last_turn.turn_number + 1) if last_turn else 1

        # Create turn (without vector_id first)
        turn = ConversationTurn.objects.create(
            user_id=user_id,
            session_id=session_id,
            turn_number=turn_number,
            user_message=user_message,
            assistant_message=assistant_message
        )

        try:
            # Generate embedding
            full_text = turn.get_full_text()
            embedding_result = llm_service.get_embeddings([full_text])

            if not embedding_result['success']:
                raise ValueError(f"Failed to generate embedding: {embedding_result['error']}")

            # Store in vector DB
            vector_id = vector_service.store_embedding(
                embedding=embedding_result['embeddings'][0],
                user_id=user_id,
                metadata={
                    'type': 'conversation_turn',
                    'turn_id': str(turn.id),
                    'session_id': session_id,
                    'turn_number': turn_number,
                    'timestamp': turn.timestamp.isoformat()
                }
            )

            # Update turn with vector_id
            turn.vector_id = vector_id
            turn.save(update_fields=['vector_id'])

            # Cache in working memory
            cache_service.cache_recent_conversation(user_id, {
                'id': str(turn.id),
                'user_message': user_message,
                'assistant_message': assistant_message,
                'timestamp': turn.timestamp.isoformat(),
                'session_id': session_id,
                'turn_number': turn_number
            })

            # Schedule background extraction (15min delay)
            _schedule_extraction(str(turn.id))

            logger.info(f"Stored turn {turn.id} for user {user_id}")
            return turn

        except Exception as e:
            # Rollback turn creation on failure
            turn.delete()
            logger.error(f"Failed to store turn: {e}")
            raise

    def search_fast(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Fast path search - direct embedding, no LLM calls
        Target: <10ms (cache hit), 100-300ms (cache miss)

        Args:
            query: Search query text
            user_id: UUID of the user
            limit: Maximum number of results
            threshold: Minimum similarity score (0-1)

        Returns:
            List of conversation turns with scores

        Raises:
            ValueError: If embedding generation fails
        """
        # Check cache first
        cached_results = cache_service.get_cached_search(user_id, query)
        if cached_results is not None:
            logger.info(f"Cache hit for search query: {query[:30]}...")
            return cached_results[:limit]

        # Generate query embedding
        embedding_result = llm_service.get_embeddings([query])
        if not embedding_result['success']:
            raise ValueError(f"Failed to generate query embedding: {embedding_result['error']}")

        # Search vector DB
        search_results = vector_service.search_similar(
            embedding=embedding_result['embeddings'][0],
            user_id=user_id,
            limit=limit,
            score_threshold=threshold
        )

        # Filter to only conversation turns (exclude atomic notes)
        conversation_results = [
            r for r in search_results
            if r['metadata'].get('type') == 'conversation_turn'
        ]

        # Get conversation turns from DB
        turn_ids = [r['metadata']['turn_id'] for r in conversation_results]
        turns = ConversationTurn.objects.filter(id__in=turn_ids)
        turns_by_id = {str(t.id): t for t in turns}

        # Combine results
        results = []
        for result in conversation_results:
            turn_id = result['metadata']['turn_id']
            if turn_id in turns_by_id:
                turn = turns_by_id[turn_id]
                results.append({
                    'id': str(turn.id),
                    'user_message': turn.user_message,
                    'assistant_message': turn.assistant_message,
                    'timestamp': turn.timestamp.isoformat(),
                    'score': result['score'],
                    'session_id': turn.session_id,
                    'turn_number': turn.turn_number
                })

        # Cache search results
        cache_service.cache_search_result(user_id, query, results)

        logger.info(f"Search for user {user_id} returned {len(results)} results")
        return results

    def search_deep(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Deep mode: Multi-tier search across all memory stores

        Searches across three tiers for comprehensive context:
        1. Working memory (cache) - <10ms
        2. Raw conversations (vector search) - 100-300ms
        3. Atomic notes + graph traversal - 200-500ms

        Combines and deduplicates results from all tiers.

        Args:
            query: Search query text
            user_id: UUID of the user
            limit: Maximum number of results per tier
            threshold: Minimum similarity score

        Returns:
            Combined and ranked results from all tiers
        """
        try:
            all_results = []
            seen_ids = set()

            # Tier 1: Check working memory cache
            logger.info(f"Deep search tier 1: working memory cache")
            working_memory = cache_service.get_working_memory(user_id, limit=20)

            # Simple keyword matching on cached conversations
            for conv in working_memory:
                # Check if query terms appear in user message
                if any(term.lower() in conv['user_message'].lower()
                       for term in query.split()):
                    conv['source'] = 'working_memory'
                    conv['score'] = 0.8  # High score for recent cached items
                    all_results.append(conv)
                    seen_ids.add(conv['id'])

            # Tier 2: Raw conversation search
            logger.info(f"Deep search tier 2: raw conversations")
            raw_results = self.search_fast(
                query=query,
                user_id=user_id,
                limit=limit,
                threshold=threshold
            )

            for result in raw_results:
                if result['id'] not in seen_ids:
                    result['source'] = 'raw_conversation'
                    all_results.append(result)
                    seen_ids.add(result['id'])

            # Tier 3: Atomic notes with graph traversal
            logger.info(f"Deep search tier 3: atomic notes + graph")
            graph_service = _get_graph_service()
            atomic_results = graph_service.search_with_graph(
                query=query,
                user_id=user_id,
                limit=limit,
                threshold=threshold,
                traverse_depth=1  # 1-hop traversal
            )

            for result in atomic_results:
                if result['id'] not in seen_ids:
                    all_results.append(result)
                    seen_ids.add(result['id'])

            # Rank by score (or combined_score for graph results)
            all_results.sort(
                key=lambda x: x.get('combined_score') or x.get('score', 0),
                reverse=True
            )

            logger.info(
                f"Deep search for user {user_id}: "
                f"{len(working_memory)} cache + "
                f"{len(raw_results)} raw + "
                f"{len(atomic_results)} atomic = "
                f"{len(all_results)} total"
            )

            return all_results

        except Exception as e:
            logger.error(f"Deep search failed: {e}", exc_info=True)
            # Fallback to fast search on error
            return self.search_fast(query, user_id, limit, threshold)

    def list_recent(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[ConversationTurn]:
        """
        List recent conversation turns for a user

        Args:
            user_id: UUID of the user
            limit: Maximum number of turns to return

        Returns:
            List of ConversationTurn instances
        """
        return list(
            ConversationTurn.objects.filter(user_id=user_id)
            .order_by('-timestamp')[:limit]
        )


# Global instance
conversation_service = ConversationService()
