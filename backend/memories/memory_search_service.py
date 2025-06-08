import json
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
        Search for relevant memories using optimized vector search

        Args:
            query: Search query text
            user_id: UUID of the user
            limit: Maximum number of results
            threshold: Minimum similarity threshold

        Returns:
            List[Memory]: List of relevant memories ordered by similarity
        """
        # Generate query embedding
        embedding_result = llm_service.get_embeddings([query])
        if not embedding_result["success"]:
            logger.error(
                "Failed to generate query embedding: %s", embedding_result["error"]
            )
            return []

        query_embedding = embedding_result["embeddings"][0]

        # Use optimized search with dynamic ef parameter based on query complexity
        ef_value = self._calculate_optimal_ef(query, limit)

        # Use optimized search if available, fallback to regular search
        if hasattr(vector_service, "search_similar_optimized"):
            vector_results = vector_service.search_similar_optimized(
                query_embedding=query_embedding,
                user_id=user_id,
                limit=limit,
                score_threshold=threshold,
                ef=ef_value,
            )
        else:
            # Fallback to regular search
            vector_results = vector_service.search_similar(
                query_embedding=query_embedding,
                user_id=user_id,
                limit=limit,
            )
            # Filter by threshold manually if using fallback
            vector_results = [r for r in vector_results if r["score"] >= threshold]

        # Get Memory objects maintaining order
        memory_ids = [result["memory_id"] for result in vector_results]

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
        limit: int = 20,
        threshold: float = 0.5,
    ) -> List[Memory]:
        """Enhanced search with multiple similarity approaches using optimized search"""

        all_memory_results = {}

        for search_item in search_queries:
            search_query = search_item.get("search_query", "")
            query_confidence = search_item.get("confidence", 0.5)
            search_type = search_item.get("search_type", "direct")

            if not search_query:
                continue

            # Generate search variations
            search_variations = self._generate_search_variations(
                search_query, search_type
            )

            for variation in search_variations:
                cache_key = f"embedding:{hash(variation)}"
                if cache_key in self.embedding_cache:
                    query_embedding = self.embedding_cache[cache_key]
                else:
                    embedding_result = llm_service.get_embeddings([variation])
                    if embedding_result["success"]:
                        query_embedding = embedding_result["embeddings"][0]
                        self.embedding_cache[cache_key] = query_embedding
                    else:
                        continue

                # Calculate optimal ef based on search type and query complexity
                ef_value = self._calculate_optimal_ef_for_type(search_type, variation)
                search_threshold = self._get_threshold_for_search_type(search_type)

                # Use optimized search
                vector_results = vector_service.search_similar_optimized(
                    query_embedding=query_embedding,
                    user_id=user_id,
                    limit=limit,
                    score_threshold=search_threshold,
                    ef=ef_value,
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

    def _calculate_optimal_ef(self, query: str, limit: int) -> int:
        """
        Calculate optimal ef parameter based on query complexity and desired results

        Args:
            query: Search query text
            limit: Number of results requested

        Returns:
            Optimal ef value for HNSW search
        """
        # Base ef should be at least 2x the limit for good results
        base_ef = max(limit * 2, 64)

        # Adjust based on query complexity
        query_words = len(query.split())

        if query_words <= 2:
            # Simple queries can use lower ef
            return min(base_ef, 128)
        elif query_words <= 5:
            # Medium complexity
            return int(min(base_ef * 1.5, 200))
        else:
            # Complex queries need higher ef for accuracy
            return int(min(base_ef * 2, 300))

    def _calculate_optimal_ef_for_type(self, search_type: str, query: str) -> int:
        """Calculate ef based on search type requirements"""
        base_ef = self._calculate_optimal_ef(query, 20)

        # Different search types have different accuracy requirements
        type_multipliers = {
            "direct": 1.0,  # Standard accuracy
            "semantic": 1.5,  # Need higher accuracy for semantic search
            "experiential": 1.2,  # Slightly higher for experiences
            "contextual": 1.3,  # Higher for contextual understanding
            "interest": 1.1,  # Slightly higher for interests
        }

        multiplier = type_multipliers.get(search_type, 1.0)
        return int(base_ef * multiplier)

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
        from settings_app.models import LLMSettings

        settings = LLMSettings.get_settings()

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
        """Enhanced ranking that considers semantic diversity"""
        # Sort by boosted score
        sorted_results = sorted(
            results.values(), key=lambda x: x["score"], reverse=True
        )

        # Take top results but ensure diversity of search types
        final_results = []
        type_counts = {}

        for result in sorted_results:
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

        # Fetch and return Memory objects
        memory_ids = [r["memory_id"] for r in final_results]
        memories = Memory.objects.filter(id__in=memory_ids)
        memory_dict = {str(m.id): m for m in memories}

        return [
            memory_dict[r["memory_id"]]
            for r in final_results
            if r["memory_id"] in memory_dict
        ]

    def clear_cache(self):
        """Clear embedding cache (useful when settings change)"""
        self.embedding_cache.clear()
        logger.info("Cleared memory search service cache")

    def find_semantic_connections(
        self, memories: List[Memory], original_query: str, user_id: str
    ) -> List[Memory]:
        """Find additional semantic connections using LLM analysis"""
        from settings_app.models import LLMSettings

        settings = LLMSettings.get_settings()

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
                                if mem not in memories:
                                    memories.append(mem)
                                    logger.debug(
                                        f"Added semantic connection: {mem.content[:100]}..."
                                    )
                else:
                    logger.info("No additional semantic connections found")

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse semantic connections response: {e}")

        return memories

    def summarize_relevant_memories(
        self, memories: List[Memory], user_query: str
    ) -> Dict[str, Any]:
        """Analyze and summarize relevant memories for the user's query"""
        from settings_app.models import LLMSettings

        settings = LLMSettings.get_settings()

        if not memories:
            return {
                "summary": "No relevant memories found.",
                "key_points": [],
                "relevant_context": "",
                "confidence": 0.0,
                "memory_usage": {
                    "total_memories": 0,
                    "highly_relevant": 0,
                    "moderately_relevant": 0,
                    "context_relevant": 0,
                },
            }

        # Prepare memory content for analysis
        memory_content = []
        for i, memory in enumerate(memories[:20]):  # Limit to prevent prompt overflow
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
                logger.info(
                    f"Generated memory summary with confidence {summary_result.get('confidence', 0)}"
                )
                return summary_result
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to parse memory summary: {e}")

        # Fallback summary
        return {
            "summary": f"Found {len(memories)} memories related to your query, but unable to generate detailed summary.",
            "key_points": [memory.content[:100] + "..." for memory in memories[:5]],
            "relevant_context": "Multiple memories found but analysis failed",
            "confidence": 0.3,
            "memory_usage": {
                "total_memories": len(memories),
                "highly_relevant": 0,
                "moderately_relevant": len(memories),
                "context_relevant": 0,
            },
        }


# Global instance
memory_search_service = MemorySearchService()
