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

        # Batch fetch only active memories maintaining order
        memories = Memory.objects.filter(id__in=memory_ids, is_active=True)
        memory_dict = {str(m.id): m for m in memories}

        # Apply temporal decay and return in similarity order
        from .conflict_resolution_service import conflict_resolution_service
        
        result_memories = []
        for memory_id in memory_ids:
            if memory_id in memory_dict:
                memory = memory_dict[memory_id]
                # Apply temporal decay to update confidence
                conflict_resolution_service.apply_temporal_decay(memory)
                result_memories.append(memory)
                
        return result_memories

    def search_memories_with_queries(
        self,
        search_queries: List[Dict[str, Any]],
        user_id: str,
        limit: int = 20,  # Increase to get more candidates
        threshold: float = 0.5,  # Lower threshold for broader search
    ) -> List[Memory]:
        """Enhanced search with multiple similarity approaches"""

        all_memory_results = {}

        for search_item in search_queries:
            search_query = search_item.get("search_query", "")
            query_confidence = search_item.get("confidence", 0.5)
            search_type = search_item.get("search_type", "direct")

            if not search_query:
                continue

            # Get multiple embeddings for broader semantic search
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
    
    def _get_inference_level_multiplier(self, memory: Memory) -> float:
        """Get reliability multiplier based on inference level"""
        inference_level = memory.metadata.get("inference_level", "stated")
        certainty = memory.metadata.get("certainty", 0.5)
        
        # Base multipliers by inference level
        base_multipliers = {
            "stated": 1.0,      # Highest reliability - direct user statements
            "inferred": 0.85,   # High reliability - logical conclusions
            "implied": 0.7,     # Moderate reliability - reading between lines
        }
        
        # Apply certainty factor
        base_multiplier = base_multipliers.get(inference_level, 0.8)
        
        # Boost by certainty level (certainty acts as additional confidence)
        certainty_boost = certainty * 0.2  # Up to 20% boost from high certainty
        
        return min(1.0, base_multiplier + certainty_boost)

    def _rank_and_filter_results(self, results: Dict, limit: int) -> List[Memory]:
        """Enhanced ranking that considers semantic diversity and inference levels"""
        # Get Memory objects to access metadata for inference-level scoring
        memory_ids = list(results.keys())
        memories = Memory.objects.filter(id__in=memory_ids, is_active=True)
        memory_dict = {str(m.id): m for m in memories}
        
        # Apply inference-level scoring
        for memory_id, result in results.items():
            if memory_id in memory_dict:
                memory = memory_dict[memory_id]
                inference_multiplier = self._get_inference_level_multiplier(memory)
                result["inference_boosted_score"] = result["score"] * inference_multiplier
                result["inference_level"] = memory.metadata.get("inference_level", "stated")
            else:
                result["inference_boosted_score"] = result["score"]
                result["inference_level"] = "stated"
        
        # Sort by inference-boosted score
        sorted_results = sorted(
            results.values(), key=lambda x: x["inference_boosted_score"], reverse=True
        )

        # Take top results ensuring diversity of search types and inference levels
        final_results = []
        type_counts = {}
        inference_counts = {}

        for result in sorted_results:
            search_type = result.get("search_type", "direct")
            inference_level = result.get("inference_level", "stated")
            
            type_count = type_counts.get(search_type, 0)
            inference_count = inference_counts.get(inference_level, 0)

            # Allow more direct results and stated facts, but ensure diversity
            max_per_type = {
                "direct": limit // 2,
                "semantic": limit // 3,
                "experiential": limit // 4,
            }
            
            # Prioritize stated facts, but allow some inferred/implied for completeness
            max_per_inference = {
                "stated": int(limit * 0.6),      # Up to 60% stated facts
                "inferred": int(limit * 0.3),    # Up to 30% inferred facts  
                "implied": int(limit * 0.2),     # Up to 20% implied facts
            }

            # Check both constraints
            type_ok = type_count < max_per_type.get(search_type, limit // 4)
            inference_ok = inference_count < max_per_inference.get(inference_level, limit // 5)
            
            if type_ok and inference_ok:
                final_results.append(result)
                type_counts[search_type] = type_count + 1
                inference_counts[inference_level] = inference_count + 1

            if len(final_results) >= limit:
                break

        # Fetch and return only active Memory objects
        memory_ids = [r["memory_id"] for r in final_results]
        memories = Memory.objects.filter(id__in=memory_ids, is_active=True)
        memory_dict = {str(m.id): m for m in memories}

        # Apply temporal decay to all retrieved memories
        from .conflict_resolution_service import conflict_resolution_service
        
        result_memories = []
        for r in final_results:
            memory_id = r["memory_id"]
            if memory_id in memory_dict:
                memory = memory_dict[memory_id]
                # Apply temporal decay to update confidence
                conflict_resolution_service.apply_temporal_decay(memory)
                result_memories.append(memory)
                
        return result_memories

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

        # Prepare memory content for analysis with inference level information
        memory_content = []
        inference_stats = {"stated": 0, "inferred": 0, "implied": 0}
        
        for i, memory in enumerate(memories[:20]):  # Limit to prevent prompt overflow
            inference_level = memory.metadata.get("inference_level", "stated")
            certainty = memory.metadata.get("certainty", 0.5)
            evidence = memory.metadata.get("evidence", "")
            
            inference_stats[inference_level] += 1
            
            # Include reliability indicators in summary
            reliability_indicator = {
                "stated": "🟢",  # High reliability
                "inferred": "🟡",  # Moderate reliability  
                "implied": "🟠"    # Lower reliability
            }.get(inference_level, "⚪")
            
            memory_line = f"{i + 1}. {reliability_indicator} {memory.content}"
            if certainty < 0.7:
                memory_line += f" (Certainty: {certainty:.1f})"
            if evidence and len(evidence) < 100:
                memory_line += f" | Evidence: {evidence}"
                
            memory_content.append(memory_line)

        memories_text = "\n".join(memory_content)
        
        # Add inference level breakdown to the prompt
        inference_breakdown = f"""
INFERENCE LEVEL BREAKDOWN:
- 🟢 Stated facts (direct quotes): {inference_stats['stated']}
- 🟡 Inferred facts (logical conclusions): {inference_stats['inferred']}
- 🟠 Implied facts (contextual reading): {inference_stats['implied']}
"""

        # Use the configurable prompt
        summarization_prompt = f"""{settings.memory_summarization_prompt}

**USER QUERY:** {user_query}

{inference_breakdown}

**MEMORIES TO ANALYZE:**
{memories_text}

**ANALYSIS INSTRUCTIONS:**
When analyzing these memories, consider the inference levels:
- 🟢 Stated facts have highest reliability and should be prioritized in your summary
- 🟡 Inferred facts are logical conclusions and generally reliable
- 🟠 Implied facts are contextual interpretations and should be noted as such
- Pay attention to certainty scores and evidence provided"""

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
