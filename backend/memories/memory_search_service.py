import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from .llm_service import llm_service
from .models import Memory
from .vector_service import vector_service

logger = logging.getLogger(__name__)

# SVC-P2-08 fix: Extract magic numbers as named constants
DEFAULT_CACHE_SIZE = 1000  # Default embedding cache size (each ~4KB)
MAX_CACHE_SIZE_WARNING = 10000  # Warn if cache size exceeds this
EMBEDDING_SIZE_KB = 4  # Approximate size of each embedding in KB
BYTES_PER_KB = 1024  # Bytes per kilobyte
SETTINGS_CACHE_TTL = 300  # Settings cache TTL in seconds (5 minutes)
DEFAULT_SEARCH_LIMIT = 10  # Default number of memories to return
DEFAULT_SEARCH_THRESHOLD = 0.7  # Default similarity threshold
SEARCH_CANDIDATE_LIMIT = 20  # Number of candidates to fetch for search
CONTENT_PREVIEW_LENGTH = 100  # Length of content preview in logs
MAX_MEMORIES_FOR_SUMMARY = 20  # Maximum memories to include in summary


class MemorySearchService:
    """
    Optimized memory search with caching and batch operations.

    Thread-safe implementation with manual LRU cache using locks.
    """

    def __init__(self):
        # Thread-safe LRU cache implementation
        self._embedding_cache: Dict[str, List[float]] = {}
        self._cache_order: List[str] = []  # Track access order for LRU
        self._cache_lock = threading.RLock()

        # SVC-P1-09 fix: Configurable cache size to prevent unbounded memory growth
        # Each embedding is ~4KB (1024 floats * 4 bytes), so 1000 = ~4MB
        # For production with many users, consider reducing or using Redis
        from django.conf import settings
        self._max_cache_size = getattr(settings, 'EMBEDDING_CACHE_SIZE', DEFAULT_CACHE_SIZE)

        if self._max_cache_size > MAX_CACHE_SIZE_WARNING:
            logger.warning(
                f"Large embedding cache size ({self._max_cache_size}). "
                f"This may use ~{self._max_cache_size * EMBEDDING_SIZE_KB / BYTES_PER_KB:.1f}MB of memory. "
                f"Consider using Redis for larger deployments."
            )

        # Settings cache to avoid hitting DB on every search (SVC-P1-08 fix)
        self._settings_cache = None
        self._settings_cache_time = 0
        self._settings_cache_ttl = SETTINGS_CACHE_TTL

    def _get_cached_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text with thread-safe LRU caching.

        Thread Safety: Uses lock to prevent race conditions during cache access.
        """
        with self._cache_lock:
            # Check if in cache
            if text in self._embedding_cache:
                # Move to end (most recently used)
                self._cache_order.remove(text)
                self._cache_order.append(text)
                return self._embedding_cache[text]

        # Not in cache - generate embedding (outside lock to avoid blocking)
        embedding = self._get_embedding(text)

        # Add to cache with lock
        with self._cache_lock:
            # Check if cache is full
            if len(self._embedding_cache) >= self._max_cache_size:
                # Remove least recently used (first in order list)
                if self._cache_order:
                    oldest = self._cache_order.pop(0)
                    del self._embedding_cache[oldest]

            # Add new embedding
            self._embedding_cache[text] = embedding
            self._cache_order.append(text)

        return embedding

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text (not cached - use _get_cached_embedding instead)"""
        embedding_result = llm_service.get_embeddings([text])
        if not embedding_result["success"]:
            raise ValueError(f"Failed to generate embedding: {embedding_result['error']}")
        return embedding_result["embeddings"][0]

    def _get_cached_settings(self):
        """
        Get LLM settings with caching to avoid DB queries in hot path.

        Thread-safe with TTL of 5 minutes. Fixes SVC-P1-08.
        """
        with self._cache_lock:
            current_time = time.time()

            # Check if cache is valid
            if (self._settings_cache is not None and
                current_time - self._settings_cache_time < self._settings_cache_ttl):
                return self._settings_cache

            # Cache expired or not set, fetch from DB
            # SVC-P2-12 fix: Add error handling for settings access
            from settings_app.models import LLMSettings
            try:
                self._settings_cache = LLMSettings.get_settings()
                self._settings_cache_time = current_time
                logger.debug("Refreshed LLM settings cache")
            except Exception as e:
                logger.warning("Failed to load LLM settings: %s. Using fallback defaults.", e)
                # Create fallback settings object
                from types import SimpleNamespace
                self._settings_cache = SimpleNamespace(
                    enable_semantic_connections=False,
                    semantic_enhancement_threshold=3,
                )
                self._settings_cache_time = current_time

            return self._settings_cache

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
        self, query: str, user_id: str, limit: int = DEFAULT_SEARCH_LIMIT, threshold: float = DEFAULT_SEARCH_THRESHOLD
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
        # Get query embedding (with LRU caching)
        try:
            query_embedding = self._get_cached_embedding(query)
        except ValueError as e:
            logger.error("Failed to generate query embedding: %s", e)
            return []

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

    def search_memories_with_queries(
        self,
        search_queries: List[Dict[str, Any]],
        user_id: str,
        limit: int = SEARCH_CANDIDATE_LIMIT,
        threshold: float = 0.5,  # Lower threshold for broader search
    ) -> List[Memory]:
        """Enhanced search with multiple similarity approaches"""

        all_memory_results = {}

        for search_item in search_queries:
            search_query = search_item.get("search_query", "")
            query_confidence = 0.8  # Default confidence for simplified schema
            search_type = search_item.get("search_type", "direct")

            if not search_query:
                continue

            # Get multiple embeddings for broader semantic search
            search_variations = self._generate_search_variations(
                search_query, search_type
            )

            for variation in search_variations:
                try:
                    query_embedding = self._get_cached_embedding(variation)
                except ValueError:
                    # Skip this variation if embedding fails
                    continue

                # Search with different thresholds based on search type
                search_threshold = self._get_threshold_for_search_type(search_type)

                vector_results = vector_service.search_similar(
                    query_embedding=query_embedding,
                    user_id=user_id,
                    limit=limit,
                    score_threshold=search_threshold,
                )

                # Process results with type-based confidence adjustment
                for result in vector_results:
                    memory_id = result["memory_id"]
                    original_score = result["score"]

                    # Adjust confidence based on search type
                    type_multiplier = self._get_type_multiplier(search_type)
                    boosted_score = original_score * query_confidence * type_multiplier

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
                            "search_type": search_type,
                            "payload": result["payload"],
                        }

        # Enhanced ranking that considers semantic connections
        return self._rank_and_filter_results(all_memory_results, limit)

    def _generate_search_variations(self, query: str, search_type: str) -> List[str]:
        """Generate variations of the search query for broader coverage"""
        variations = [query]

        if search_type == "semantic":
            # Add more abstract versions
            variations.extend(
                [
                    f"topics related to {query}",
                    f"interests connected to {query}",
                    f"experiences involving {query}",
                ]
            )
        elif search_type == "experiential":
            variations.extend(
                [
                    f"user experienced {query}",
                    f"user's memories of {query}",
                    f"when user encountered {query}",
                ]
            )

        return variations

    def _get_threshold_for_search_type(self, search_type: str) -> float:
        """Get similarity threshold based on search type from settings"""
        settings = self._get_cached_settings()

        thresholds = {
            "direct": settings.search_threshold_direct,
            "semantic": settings.search_threshold_semantic,
            "experiential": settings.search_threshold_experiential,
            "contextual": settings.search_threshold_contextual,
            "interest": settings.search_threshold_interest,
        }
        return thresholds.get(search_type, 0.6)

    def _get_type_multiplier(self, search_type: str) -> float:
        """Get confidence multiplier based on search type"""
        multipliers = {
            "direct": 1.0,
            "semantic": 0.8,
            "experiential": 0.9,
            "contextual": 0.6,
            "interest": 0.7,
        }
        return multipliers.get(search_type, 0.8)

    def _rank_and_filter_results(self, results: Dict, limit: int) -> List[Memory]:
        """Enhanced ranking that considers semantic diversity and score quality"""
        settings = self._get_cached_settings()
        
        # Sort by boosted score
        sorted_results = sorted(
            results.values(), key=lambda x: x["score"], reverse=True
        )

        # Apply configurable quality threshold to filter out low-relevance results
        quality_threshold = getattr(settings, 'memory_quality_threshold', 0.35)
        high_quality_results = [
            result for result in sorted_results 
            if result["score"] >= quality_threshold
        ]
        
        # If we have very few high-quality results, relax threshold slightly
        if len(high_quality_results) < 3 and sorted_results:
            relaxed_threshold = max(0.25, quality_threshold * 0.8)
            high_quality_results = [
                result for result in sorted_results 
                if result["score"] >= relaxed_threshold
            ]
        
        # Apply diversity filtering only to remaining high-quality results
        final_results = []
        type_counts = {}

        for result in high_quality_results:
            search_type = result.get("search_type", "direct")
            type_count = type_counts.get(search_type, 0)

            # Allow more direct results, but ensure semantic diversity
            max_per_type = {
                "direct": limit // 2,
                "semantic": limit // 3,
                "experiential": limit // 4,
            }

            if type_count < max_per_type.get(search_type, limit // 4):
                final_results.append(result)
                type_counts[search_type] = type_count + 1

            if len(final_results) >= limit:
                break

        # Fetch Memory objects and attach search metadata
        memory_ids = [r["memory_id"] for r in final_results]
        memories = Memory.objects.filter(id__in=memory_ids)
        memory_dict = {str(m.id): m for m in memories}

        # Attach search metadata to memories
        enhanced_memories = []
        for result in final_results:
            if result["memory_id"] in memory_dict:
                memory = memory_dict[result["memory_id"]]
                # Add search metadata as temporary attributes
                memory._search_score = result["score"]
                memory._search_type = result.get("search_type", "unknown")
                memory._original_score = result.get("original_score", result["score"])
                memory._query_confidence = result.get("query_confidence", 1.0)
                enhanced_memories.append(memory)
        
        return enhanced_memories

    def clear_cache(self):
        """
        Clear embedding cache (useful when settings change).

        Thread-safe: Protected by lock.
        """
        with self._cache_lock:
            self._embedding_cache.clear()
            self._cache_order.clear()
        logger.info("Cleared memory search service cache")

    def get_cache_info(self):
        """
        Get cache statistics for debugging.

        Thread-safe: Protected by lock for consistent snapshot.
        """
        with self._cache_lock:
            return {
                "hits": 0,  # Not tracked in manual implementation
                "misses": 0,  # Not tracked in manual implementation
                "maxsize": self._max_cache_size,
                "currsize": len(self._embedding_cache)
            }

    def find_semantic_connections(
        self, memories: List[Memory], original_query: str, user_id: str
    ) -> List[Memory]:
        """
        Find additional semantic connections using LLM analysis.

        SVC-P1-10 fix: Returns new list instead of modifying input parameter.
        """
        settings = self._get_cached_settings()

        # Check if semantic connections are enabled
        if not settings.enable_semantic_connections:
            logger.info("Semantic connections disabled in settings")
            return memories

        # Check if we have enough results to trigger enhancement
        if len(memories) < settings.semantic_enhancement_threshold:
            logger.info(
                f"Not enough memories ({len(memories)}) to trigger semantic enhancement (threshold: {settings.semantic_enhancement_threshold})"
            )
            return memories

        # SVC-P1-10 fix: Create a copy to avoid modifying input parameter
        enhanced_memories = list(memories)

        # Use the configurable prompt
        memory_summaries = [f"- {m.content}" for m in memories]
        analysis_prompt = f"""{settings.semantic_connection_prompt}

**USER QUERY:** {original_query}

**FOUND MEMORIES:**
{chr(10).join(memory_summaries)}"""

        from .llm_service import SEMANTIC_CONNECTION_FORMAT, llm_service

        llm_result = llm_service.query_llm(
            prompt=analysis_prompt,
            temperature=settings.llm_temperature,
            response_format=SEMANTIC_CONNECTION_FORMAT,
        )

        if llm_result["success"]:
            try:
                analysis_result = json.loads(llm_result["response"])

                if analysis_result.get("has_connections", False):
                    additional_searches = analysis_result.get("additional_searches", [])
                    logger.info(
                        f"Found {len(additional_searches)} semantic connections: {analysis_result.get('reasoning', '')}"
                    )

                    # Perform additional searches with these terms
                    for search_item in additional_searches[
                        :3
                    ]:  # Limit to prevent infinite expansion
                        search_term = search_item.get("search_query", "")
                        # confidence = search_item.get("confidence", 0.4)

                        if search_term:
                            # Use lower threshold for semantic connections
                            additional_memories = self.search_memories(
                                search_term,
                                user_id,
                                limit=3,
                                threshold=0.3,  # Lower threshold for broader search
                            )
                            for mem in additional_memories:
                                if mem not in enhanced_memories:
                                    enhanced_memories.append(mem)
                                    logger.debug(
                                        f"Added semantic connection: {mem.content[:CONTENT_PREVIEW_LENGTH]}..."
                                    )
                else:
                    logger.info("No additional semantic connections found")

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse semantic connections response: {e}")

        return enhanced_memories

    def summarize_relevant_memories(
        self, memories: List[Memory], user_query: str
    ) -> Dict[str, Any]:
        """Analyze and summarize relevant memories for the user's query"""
        settings = self._get_cached_settings()

        if not memories:
            return {
                "summary": "No relevant memories found for this query.",
            }

        # Prepare memory content for analysis
        memory_content = []
        for i, memory in enumerate(memories[:MAX_MEMORIES_FOR_SUMMARY]):
            memory_content.append(f"{i + 1}. {memory.content}")

        memories_text = "\n".join(memory_content)

        # Use the configurable prompt
        summarization_prompt = f"""{settings.memory_summarization_prompt}

**USER QUERY:** {user_query}

**MEMORIES TO ANALYZE:**
{memories_text}"""

        from .llm_service import MEMORY_SUMMARY_FORMAT, llm_service

        llm_result = llm_service.query_llm(
            prompt=summarization_prompt,
            temperature=settings.llm_temperature,  # Lower temperature for analysis
            response_format=MEMORY_SUMMARY_FORMAT,
        )

        if llm_result["success"]:
            try:
                summary_result = json.loads(llm_result["response"])
                logger.info("Generated memory summary successfully")
                return summary_result
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to parse memory summary: {e}")

        # Fallback summary
        return {
            "summary": f"Found {len(memories)} memories related to your query, but unable to generate detailed analysis.",
        }


# Global instance
memory_search_service = MemorySearchService()
