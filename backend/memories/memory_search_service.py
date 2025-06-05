import logging
from typing import Any, Dict, List

from .llm_service import llm_service
from .models import Memory
from .vector_service import vector_service

logger = logging.getLogger(__name__)


class MemorySearchService:
    """Optimized memory search with caching and batch operations"""

    def __init__(self):
        self.embedding_cache = {}  # Simple in-memory cache

    def store_memory_with_embedding(
        self, content: str, user_id: str, metadata: Dict[str, Any]
    ) -> Memory:
        """
        Store memory and its embedding efficiently (synchronous)

        Args:
            content: Memory content text
            user_id: UUID of the user
            metadata: Additional metadata to store

        Returns:
            Memory: Created memory instance
        """
        # Get embedding using synchronous LLM service
        embedding_result = llm_service.get_embeddings([content])
        if not embedding_result["success"]:
            raise ValueError(
                f"Failed to generate embedding: {embedding_result['error']}"
            )

        embedding = embedding_result["embeddings"][0]

        # Create memory record
        memory = Memory.objects.create(
            user_id=user_id,
            content=content,
            metadata=metadata,
        )

        # Store in vector DB
        try:
            vector_id = vector_service.store_embedding(
                memory_id=str(memory.id),
                embedding=embedding,
                user_id=str(user_id),
                metadata={**metadata, "created_at": memory.created_at.isoformat()},
            )

            # Update memory with vector reference
            memory.vector_id = vector_id
            memory.save()

            logger.info("Successfully stored memory %s with embedding", memory.id)
            return memory

        except Exception as e:
            # If vector storage fails, delete the memory to maintain consistency
            logger.error("Failed to store embedding for memory %s: %s", memory.id, e)
            memory.delete()
            raise ValueError(f"Failed to store memory embedding: {e}") from e

    def search_memories(
        self, query: str, user_id: str, limit: int = 10, threshold: float = 0.7
    ) -> List[Memory]:
        """
        Search for relevant memories (synchronous)

        Args:
            query: Search query text
            user_id: UUID of the user
            limit: Maximum number of results
            threshold: Minimum similarity threshold

        Returns:
            List[Memory]: List of relevant memories ordered by similarity
        """
        # Get query embedding (with caching)
        cache_key = f"embedding:{hash(query)}"
        if cache_key in self.embedding_cache:
            query_embedding = self.embedding_cache[cache_key]
        else:
            embedding_result = llm_service.get_embeddings([query])
            if not embedding_result["success"]:
                logger.error(
                    "Failed to generate query embedding: %s", embedding_result["error"]
                )
                return []
            query_embedding = embedding_result["embeddings"][0]
            self.embedding_cache[cache_key] = query_embedding

        # Search vector DB
        vector_results = vector_service.search_similar(
            query_embedding=query_embedding,
            user_id=user_id,
            limit=limit,
            score_threshold=threshold,
        )

        # Filter by threshold and get Memory objects
        memory_ids = [
            result["memory_id"]
            for result in vector_results
            if result["score"] >= threshold
        ]

        if not memory_ids:
            return []

        # Batch fetch memories maintaining order
        memories = Memory.objects.filter(id__in=memory_ids)
        memory_dict = {str(m.id): m for m in memories}

        # Return in similarity order
        return [
            memory_dict[memory_id]
            for memory_id in memory_ids
            if memory_id in memory_dict
        ]

    # Add this new method to MemorySearchService class:

    def search_memories_with_queries(
        self,
        search_queries: List[Dict[str, Any]],
        user_id: str,
        limit: int = 10,
        threshold: float = 0.7,
        boosted_threshold: float = 0.5,
    ) -> List[Memory]:
        """
        Search for relevant memories using provided search queries (synchronous)

        Args:
            search_queries: List of search query objects with 'search_query' and 'confidence'
            user_id: UUID of the user
            limit: Maximum number of results
            threshold: Minimum similarity threshold

        Returns:
            List[Memory]: List of relevant memories ordered by similarity
        """
        logger.info(
            "Starting memory search for user %s with %d queries",
            user_id,
            len(search_queries),
        )

        all_memory_results = {}  # Use dict to avoid duplicates

        for search_item in search_queries:
            search_query = search_item.get("search_query", "")
            query_confidence = search_item.get("confidence", 0.5)

            if not search_query:
                continue

            logger.debug(
                "Processing search query: '%s' (confidence: %s)",
                search_query,
                query_confidence,
            )

            # Get query embedding (with caching)
            cache_key = f"embedding:{hash(search_query)}"
            if cache_key in self.embedding_cache:
                query_embedding = self.embedding_cache[cache_key]
                logger.debug("Using cached embedding for: %s...", search_query[:50])
            else:
                embedding_result = llm_service.get_embeddings([search_query])
                if not embedding_result["success"]:
                    logger.error(
                        "Failed to generate embedding for query '%s': %s",
                        search_query,
                        embedding_result["error"],
                    )
                    continue
                query_embedding = embedding_result["embeddings"][0]
                self.embedding_cache[cache_key] = query_embedding
                logger.debug("Generated new embedding for: %s...", search_query[:50])

            # Search vector DB using vector service
            vector_results = vector_service.search_similar(
                query_embedding=query_embedding,
                user_id=user_id,
                limit=limit,
                score_threshold=threshold,
            )

            logger.info(
                "Found %d vector results for query: %s...",
                len(vector_results),
                search_query[:50],
            )

            # Add results with boosted scores based on query confidence
            for result in vector_results:
                logger.info("Processing vector result: %s", result)
                memory_id = result["memory_id"]
                original_score = result["score"]

                # Boost score based on query confidence
                boosted_score = original_score * query_confidence

                # Keep the best score if we already have this memory
                if (
                    memory_id not in all_memory_results
                    or boosted_score > all_memory_results[memory_id]["score"]
                ):
                    all_memory_results[memory_id] = {
                        "memory_id": memory_id,
                        "score": boosted_score,
                        "original_score": original_score,
                        "query_confidence": query_confidence,
                        "search_query": search_query,
                        "payload": result["payload"],
                    }

        # Sort by score and filter by threshold
        sorted_results = sorted(
            all_memory_results.values(), key=lambda x: x["score"], reverse=True
        )

        # Filter by threshold and limit
        filtered_results = [
            result for result in sorted_results if result["score"] >= boosted_threshold
        ][:limit]

        logger.info("After merging and filtering: %d results", len(filtered_results))

        if not filtered_results:
            logger.info("No memories found matching the search criteria")
            return []

        # Batch fetch Memory objects maintaining order
        memory_ids = [result["memory_id"] for result in filtered_results]
        memories = Memory.objects.filter(id__in=memory_ids)
        memory_dict = {str(m.id): m for m in memories}

        # Return in similarity order with search metadata
        result_memories = []
        for result in filtered_results:
            memory_id = result["memory_id"]
            if memory_id in memory_dict:
                memory = memory_dict[memory_id]
                # Add search metadata to memory object for response formatting
                # memory._search_score = result["score"]
                # memory._original_score = result["original_score"]
                # memory._query_confidence = result["query_confidence"]
                # memory._search_query = result["search_query"]
                result_memories.append(memory)

        logger.info("Returning %d memories for user %s", len(result_memories), user_id)
        return result_memories

    def clear_cache(self):
        """Clear embedding cache (useful when settings change)"""
        self.embedding_cache.clear()
        logger.info("Cleared memory search service cache")


# Global instance
memory_search_service = MemorySearchService()
