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
        DEPRECATED: This method stores memories with embeddings, which creates redundancy.
        Use store_conversation_and_memories() instead for the new hybrid architecture.
        
        Store memory and its embedding efficiently (synchronous)

        Args:
            content: Memory content text
            user_id: UUID of the user
            metadata: Additional metadata to store

        Returns:
            Memory: Created memory instance
        """
        logger.warning(
            "store_memory_with_embedding() is deprecated. Use store_conversation_and_memories() "
            "for the new conversation-based architecture."
        )
        
        # For backward compatibility, create memory without vector embedding
        memory = Memory.objects.create(
            user_id=user_id,
            content=content,
            metadata=metadata,
        )

        logger.debug(f"Created memory {memory.id} without vector embedding (deprecated method)")
        return memory

    def store_conversation_and_memories(
        self, 
        conversation_text: str, 
        extracted_memories: List[Dict[str, Any]], 
        user_id: str,
        timestamp: str = None
    ) -> Dict[str, Any]:
        """
        NEW METHOD: Store conversation chunks in Vector DB and extracted memories in Graph DB
        This implements the new hybrid architecture eliminating redundancy.

        Args:
            conversation_text: Original conversation text
            extracted_memories: List of memory data extracted from conversation
            user_id: UUID of the user
            timestamp: ISO timestamp when conversation occurred

        Returns:
            Dict containing created memory IDs, chunk IDs, and linking info
        """
        from .models import ConversationChunk
        from .graph_service import graph_service
        import datetime
        
        if timestamp is None:
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        try:
            # Step 1: Chunk the conversation and store in Vector DB
            chunks = vector_service.chunk_conversation(
                text=conversation_text, 
                max_chunk_size=1000, 
                overlap_size=100
            )
            
            # Store conversation chunks with embeddings
            vector_ids = vector_service.store_conversation_chunks(
                chunks=chunks,
                user_id=user_id,
                timestamp=timestamp,
                base_metadata={
                    "source": "conversation_extraction",
                    "total_memories_extracted": len(extracted_memories)
                }
            )
            
            # Create ConversationChunk database records
            chunk_records = []
            for i, (chunk, vector_id) in enumerate(zip(chunks, vector_ids)):
                chunk_record = ConversationChunk.objects.create(
                    user_id=user_id,
                    content=chunk,
                    vector_id=vector_id,
                    timestamp=datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00')),
                    metadata={
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "source": "conversation_extraction"
                    }
                )
                chunk_records.append(chunk_record)
            
            # Step 2: Create Memory records for extracted memories
            created_memories = []
            for memory_data in extracted_memories:
                # Ensure we have required fields
                content = memory_data.get("content", "")
                if not content:
                    continue
                    
                # Create standardized metadata
                standardized_metadata = {
                    "inference_level": memory_data.get("inference_level", "stated"),
                    "evidence": memory_data.get("evidence", ""),
                    "extraction_timestamp": timestamp,
                    "tags": memory_data.get("tags", []),
                    "entity_type": memory_data.get("entity_type", "general"),
                    "relationship_hints": memory_data.get("relationship_hints", []),
                    "model_used": memory_data.get("model_used", "unknown"),
                    "extraction_source": "conversation"
                }
                
                memory = Memory.objects.create(
                    user_id=user_id,
                    content=content,
                    metadata=standardized_metadata,
                    fact_type=memory_data.get("fact_type", "mutable"),
                    original_confidence=memory_data.get("confidence", 0.5),
                    temporal_confidence=memory_data.get("confidence", 0.5)
                )
                created_memories.append(memory)
            
            # Step 3: Link memories to conversation chunks (bidirectional)
            memory_ids = [str(m.id) for m in created_memories]
            chunk_ids = [str(c.id) for c in chunk_records]
            
            # Update conversation chunks with memory IDs
            for chunk_record in chunk_records:
                chunk_record.extracted_memory_ids = memory_ids
                chunk_record.save()
            
            # Update memories with conversation chunk IDs
            for memory in created_memories:
                memory.conversation_chunk_ids = chunk_ids
                memory.save()
            
            # Step 4: Build graph relationships for the new memories
            if created_memories and len(created_memories) > 1:
                try:
                    graph_result = graph_service.build_memory_graph(
                        user_id=user_id, 
                        incremental=True  # Only process new memories
                    )
                    logger.info(f"Built graph relationships: {graph_result}")
                except Exception as e:
                    logger.warning(f"Failed to build graph relationships: {e}")
            
            result = {
                "success": True,
                "memories_created": len(created_memories),
                "chunks_created": len(chunk_records),
                "memory_ids": memory_ids,
                "chunk_ids": chunk_ids,
                "conversation_length": len(conversation_text),
                "chunks_generated": len(chunks)
            }
            
            logger.info(
                f"Successfully stored conversation and extracted {len(created_memories)} memories "
                f"across {len(chunk_records)} conversation chunks"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to store conversation and memories: {e}")
            raise ValueError(f"Failed to store conversation and memories: {e}")

    def search_memories(
        self, query: str, user_id: str, limit: int = 10, threshold: float = 0.7
    ) -> List[Memory]:
        """
        DEPRECATED: Simple search method replaced by hybrid search architecture.
        Use search_memories_with_hybrid_approach() for better results.
        
        Search for relevant memories (synchronous)

        Args:
            query: Search query text
            user_id: UUID of the user
            limit: Maximum number of results
            threshold: Minimum similarity threshold

        Returns:
            List[Memory]: List of relevant memories ordered by similarity
        """
        logger.warning(
            "search_memories() is deprecated. Use search_memories_with_hybrid_approach() "
            "for the new conversation-based architecture."
        )
        
        # For backward compatibility, use hybrid approach
        search_queries = [{"search_query": query, "confidence": 0.8, "search_type": "direct"}]
        return self.search_memories_with_hybrid_approach(search_queries, user_id, limit, threshold)

    def search_memories_with_hybrid_approach(
        self,
        search_queries: List[Dict[str, Any]],
        user_id: str,
        limit: int = 20,
        threshold: float = 0.5,
    ) -> List[Memory]:
        """
        NEW HYBRID SEARCH ARCHITECTURE:
        1. Vector search finds relevant conversation chunks
        2. Extract memory IDs from chunks
        3. Graph traversal expands memory set based on relationships
        4. Rank and filter final results
        """
        from .graph_service import graph_service
        from .models import ConversationChunk
        
        all_memory_results = {}
        conversation_context = {}
        
        for search_item in search_queries:
            search_query = search_item.get("search_query", "")
            query_confidence = search_item.get("confidence", 0.5)
            search_type = search_item.get("search_type", "direct")
            
            if not search_query:
                continue
            
            # Step 1: Search conversation chunks via Vector DB
            embedding_result = llm_service.get_embeddings([search_query])
            if not embedding_result["success"]:
                continue
                
            query_embedding = embedding_result["embeddings"][0]
            
            # Search conversation chunks instead of memories
            conversation_results = vector_service.search_conversation_context(
                query_embedding=query_embedding,
                user_id=user_id,
                limit=limit * 2,  # Get more conversation chunks
                score_threshold=threshold * 0.8,  # Lower threshold for conversations
            )
            
            # Step 2: Extract memory IDs from conversation chunks
            chunk_ids = [result["chunk_id"] for result in conversation_results]
            if not chunk_ids:
                continue
                
            # Get memories linked to these conversation chunks
            conversation_memories = set()
            for chunk_id in chunk_ids:
                try:
                    chunk = ConversationChunk.objects.get(id=chunk_id)
                    conversation_memories.update(chunk.extracted_memory_ids or [])
                    
                    # Store conversation context for later use
                    for memory_id in (chunk.extracted_memory_ids or []):
                        if memory_id not in conversation_context:
                            conversation_context[memory_id] = []
                        conversation_context[memory_id].append({
                            "chunk_id": chunk_id,
                            "content": chunk.content,
                            "timestamp": chunk.timestamp.isoformat(),
                            "relevance_score": next(
                                (r["score"] for r in conversation_results if r["chunk_id"] == chunk_id), 
                                0.5
                            )
                        })
                except ConversationChunk.DoesNotExist:
                    continue
            
            # Step 3: Graph traversal to expand memory set based on relationships
            if conversation_memories:
                expanded_memories = self._expand_memories_via_graph(
                    list(conversation_memories), user_id, limit
                )
                conversation_memories.update(expanded_memories)
            
            # Step 4: Rank and filter final results
            for memory_id in conversation_memories:
                if memory_id in all_memory_results:
                    # Boost score for memories found via multiple queries
                    all_memory_results[memory_id]["score"] += query_confidence * 0.3
                else:
                    # Calculate base score from conversation relevance
                    conversation_score = max(
                        [ctx["relevance_score"] for ctx in conversation_context.get(memory_id, [{"relevance_score": 0.5}])]
                    )
                    
                    all_memory_results[memory_id] = {
                        "memory_id": memory_id,
                        "score": conversation_score * query_confidence,
                        "search_type": search_type,
                        "query_confidence": query_confidence,
                        "conversation_context": conversation_context.get(memory_id, [])
                    }
        
        # Get Memory objects and apply final ranking
        memory_ids = list(all_memory_results.keys())
        if not memory_ids:
            return []
            
        memories = Memory.objects.filter(
            id__in=memory_ids, user_id=user_id, is_active=True
        )
        
        # Apply conversation context and graph relationship scoring
        scored_memories = []
        for memory in memories:
            memory_id = str(memory.id)
            result_data = all_memory_results.get(memory_id, {})
            
            # Enhanced scoring based on hybrid search
            base_score = result_data.get("score", 0.5)
            conversation_boost = len(result_data.get("conversation_context", [])) * 0.1
            temporal_boost = self._calculate_temporal_relevance(memory)
            
            final_score = base_score + conversation_boost + temporal_boost
            
            # Add conversation context to memory for later use
            memory.conversation_context = result_data.get("conversation_context", [])
            memory.hybrid_search_score = final_score
            
            scored_memories.append((memory, final_score))
        
        # Sort by final score and return top results
        scored_memories.sort(key=lambda x: x[1], reverse=True)
        return [memory for memory, score in scored_memories[:limit]]

    def _expand_memories_via_graph(self, memory_ids: List[str], user_id: str, limit: int) -> List[str]:
        """
        Use graph traversal to find related memories via relationships
        """
        from .graph_service import graph_service
        
        if not memory_ids:
            return []
        
        try:
            # Use Neo4j to find related memories
            query = """
            MATCH (m:Memory {user_id: $user_id})
            WHERE m.memory_id IN $memory_ids
            MATCH (m)-[r:RELATES_TO|SUPPORTS|TEMPORAL_SEQUENCE]-(related:Memory {user_id: $user_id})
            WHERE related.is_active = true
            RETURN DISTINCT related.memory_id as memory_id, 
                   type(r) as relationship_type,
                   CASE 
                       WHEN type(r) = 'RELATES_TO' THEN coalesce(r.similarity_score, 0.7)
                       WHEN type(r) = 'SUPPORTS' THEN 0.8
                       WHEN type(r) = 'TEMPORAL_SEQUENCE' THEN 0.6
                       ELSE 0.5
                   END as relationship_strength
            ORDER BY relationship_strength DESC
            LIMIT $limit
            """
            
            if graph_service.driver:
                with graph_service.driver.session() as session:
                    result = session.run(query, {
                        "user_id": user_id,
                        "memory_ids": memory_ids,
                        "limit": limit
                    })
                    
                    related_memory_ids = []
                    for record in result:
                        related_memory_ids.append(record["memory_id"])
                    
                    logger.debug(
                        f"Graph traversal found {len(related_memory_ids)} related memories "
                        f"for {len(memory_ids)} input memories"
                    )
                    return related_memory_ids
                    
        except Exception as e:
            logger.error(f"Failed to expand memories via graph: {e}")
            
        return []

    def _calculate_temporal_relevance(self, memory) -> float:
        """
        Calculate temporal relevance boost based on memory age and confidence
        """
        import datetime
        
        # Recent memories get a slight boost
        days_old = (datetime.datetime.now(datetime.timezone.utc) - memory.created_at).days
        
        if days_old < 1:
            temporal_boost = 0.1  # Recent memories
        elif days_old < 7:
            temporal_boost = 0.05  # This week
        elif days_old < 30:
            temporal_boost = 0.0   # This month
        else:
            temporal_boost = -0.05  # Older memories slight penalty
        
        # Adjust by temporal confidence
        temporal_boost *= memory.temporal_confidence
        
        return temporal_boost

    def _rank_and_filter_results(self, memories_with_context: List[tuple], query_text: str = "") -> List[Memory]:
        """
        Enhanced multi-factor ranking algorithm for hybrid search results
        
        Ranking factors:
        - Conversation relevance score (from vector search)
        - Memory relationship strength (from graph traversal) 
        - Temporal relevance and confidence decay
        - Entity matching (person names, topics)
        - Inference level reliability weighting
        """
        ranked_memories = []
        
        for memory, context_data in memories_with_context:
            # Base factors
            base_score = context_data.get("base_score", 0.5)
            conversation_boost = len(context_data.get("conversation_context", [])) * 0.1
            temporal_boost = self._calculate_temporal_relevance(memory)
            
            # Enhanced factors for better ranking
            inference_penalty = self._calculate_inference_penalty(memory)
            entity_boost = self._calculate_entity_matching_boost(memory, query_text)
            relationship_boost = context_data.get("relationship_strength", 0.0) * 0.2
            confidence_factor = memory.temporal_confidence * 0.15
            
            # Calculate final score with weighted factors
            final_score = (
                base_score * 0.4 +                    # Primary conversation relevance
                conversation_boost * 0.15 +           # Multiple conversation mentions
                temporal_boost * 0.1 +                # Recent vs old memories  
                inference_penalty * 0.1 +             # Stated facts rank higher
                entity_boost * 0.15 +                 # Entity name/topic matching
                relationship_boost * 0.05 +           # Graph relationship strength
                confidence_factor * 0.05              # Memory confidence
            )
            
            # Add scoring details for debugging/transparency
            memory.ranking_details = {
                "base_score": base_score,
                "conversation_boost": conversation_boost,
                "temporal_boost": temporal_boost,
                "inference_penalty": inference_penalty,
                "entity_boost": entity_boost,
                "relationship_boost": relationship_boost,
                "confidence_factor": confidence_factor,
                "final_score": final_score
            }
            
            ranked_memories.append((memory, final_score))
        
        # Sort by final score and return memories only
        ranked_memories.sort(key=lambda x: x[1], reverse=True)
        return [memory for memory, score in ranked_memories]
    
    def _calculate_inference_penalty(self, memory) -> float:
        """Calculate penalty/boost based on inference level reliability"""
        inference_level = memory.metadata.get("inference_level", "stated")
        
        if inference_level == "stated":
            return 0.1   # Boost for directly stated facts
        elif inference_level == "inferred":
            return 0.0   # Neutral for logical inferences
        elif inference_level == "implied":
            return -0.05  # Slight penalty for implied information
        else:
            return 0.0
            
    def _calculate_entity_matching_boost(self, memory, query_text: str) -> float:
        """Calculate boost for entity/name matching between query and memory"""
        if not query_text:
            return 0.0
            
        query_lower = query_text.lower()
        memory_content_lower = memory.content.lower()
        memory_tags = [tag.lower() for tag in memory.metadata.get("tags", [])]
        
        boost = 0.0
        
        # Check for name matches (capitalized words in query)
        import re
        names_in_query = re.findall(r'\b[A-Z][a-z]+\b', query_text)
        for name in names_in_query:
            if name.lower() in memory_content_lower or name.lower() in memory_tags:
                boost += 0.1
        
        # Check for entity type matches
        entity_type = memory.metadata.get("entity_type", "")
        if entity_type and entity_type.lower() in query_lower:
            boost += 0.05
            
        # Check for tag matches
        query_words = set(query_lower.split())
        tag_matches = len(query_words.intersection(set(memory_tags)))
        boost += tag_matches * 0.02
        
        return min(boost, 0.3)  # Cap the boost at 0.3

    def expand_conversation_context(self, memory_ids: List[str], user_id: str) -> Dict[str, Any]:
        """
        Expand conversation context by including surrounding temporal context and related conversation chunks.
        When conversation chunk matches, include surrounding chunks from same conversation session.
        """
        from .models import ConversationChunk
        import datetime
        
        if not memory_ids:
            return {}
        
        try:
            # Get conversation chunks linked to these memories
            memories = Memory.objects.filter(id__in=memory_ids, user_id=user_id, is_active=True)
            all_chunk_ids = set()
            
            for memory in memories:
                if memory.conversation_chunk_ids:
                    all_chunk_ids.update(memory.conversation_chunk_ids)
            
            if not all_chunk_ids:
                return {}
            
            # Get the conversation chunks
            chunks = ConversationChunk.objects.filter(id__in=all_chunk_ids, user_id=user_id).order_by('timestamp')
            
            # Group chunks by conversation session (within 1 hour of each other)
            conversation_sessions = []
            current_session = []
            session_threshold = datetime.timedelta(hours=1)
            
            for chunk in chunks:
                if not current_session:
                    current_session = [chunk]
                else:
                    # Check if this chunk is within the session threshold
                    last_chunk_time = current_session[-1].timestamp
                    if chunk.timestamp - last_chunk_time <= session_threshold:
                        current_session.append(chunk)
                    else:
                        # Start new session
                        conversation_sessions.append(current_session)
                        current_session = [chunk]
            
            # Add the last session
            if current_session:
                conversation_sessions.append(current_session)
            
            # For each session, find surrounding chunks to provide context
            expanded_context = {}
            
            for session in conversation_sessions:
                session_start = session[0].timestamp
                session_end = session[-1].timestamp
                
                # Expand context window by 30 minutes before/after
                context_window = datetime.timedelta(minutes=30)
                context_start = session_start - context_window
                context_end = session_end + context_window
                
                # Get all chunks within the expanded window
                context_chunks = ConversationChunk.objects.filter(
                    user_id=user_id,
                    timestamp__gte=context_start,
                    timestamp__lte=context_end
                ).order_by('timestamp')
                
                # Build expanded context for this session
                session_context = {
                    "session_start": session_start.isoformat(),
                    "session_end": session_end.isoformat(),
                    "primary_chunks": len(session),
                    "expanded_chunks": context_chunks.count(),
                    "conversation_flow": []
                }
                
                for chunk in context_chunks:
                    is_primary = chunk.id in all_chunk_ids
                    session_context["conversation_flow"].append({
                        "chunk_id": str(chunk.id),
                        "content": chunk.content,
                        "timestamp": chunk.timestamp.isoformat(),
                        "is_primary_match": is_primary,
                        "extracted_memories": chunk.extracted_memory_ids or [],
                        "metadata": chunk.metadata
                    })
                
                expanded_context[f"session_{len(expanded_context)}"] = session_context
            
            # Calculate conversation session statistics
            total_expanded_chunks = sum(
                session["expanded_chunks"] for session in expanded_context.values()
            )
            
            result = {
                "expanded_context": expanded_context,
                "total_sessions": len(conversation_sessions),
                "total_expanded_chunks": total_expanded_chunks,
                "context_summary": self._generate_context_summary(expanded_context)
            }
            
            logger.info(
                f"Expanded conversation context for {len(memory_ids)} memories: "
                f"{len(conversation_sessions)} sessions, {total_expanded_chunks} chunks"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to expand conversation context: {e}")
            return {}

    def _generate_context_summary(self, expanded_context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of the expanded conversation context"""
        if not expanded_context:
            return {}
            
        total_content_length = 0
        earliest_timestamp = None
        latest_timestamp = None
        total_memories_referenced = set()
        
        for session in expanded_context.values():
            for chunk_data in session["conversation_flow"]:
                content_length = len(chunk_data["content"])
                total_content_length += content_length
                
                timestamp_str = chunk_data["timestamp"]
                timestamp = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                
                if earliest_timestamp is None or timestamp < earliest_timestamp:
                    earliest_timestamp = timestamp
                if latest_timestamp is None or timestamp > latest_timestamp:
                    latest_timestamp = timestamp
                
                total_memories_referenced.update(chunk_data.get("extracted_memories", []))
        
        time_span = None
        if earliest_timestamp and latest_timestamp:
            time_span = (latest_timestamp - earliest_timestamp).total_seconds() / 3600  # hours
        
        return {
            "total_content_length": total_content_length,
            "time_span_hours": time_span,
            "earliest_timestamp": earliest_timestamp.isoformat() if earliest_timestamp else None,
            "latest_timestamp": latest_timestamp.isoformat() if latest_timestamp else None,
            "memories_referenced": len(total_memories_referenced),
            "avg_chunk_length": total_content_length / max(sum(len(s["conversation_flow"]) for s in expanded_context.values()), 1)
        }

    def search_memories_with_queries(
        self,
        search_queries: List[Dict[str, Any]],
        user_id: str,
        limit: int = 20,  # Increase to get more candidates
        threshold: float = 0.5,  # Lower threshold for broader search
    ) -> List[Memory]:
        """Enhanced search with multiple similarity approaches - LEGACY METHOD"""

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
        
        # Base multipliers by inference level
        base_multipliers = {
            "stated": 1.0,      # Highest reliability - direct user statements
            "inferred": 0.85,   # High reliability - logical conclusions
            "implied": 0.7,     # Moderate reliability - reading between lines
        }
        
        # Apply confidence factor
        base_multiplier = base_multipliers.get(inference_level, 0.8)
        
        # Boost by confidence level 
        confidence_boost = memory.temporal_confidence * 0.15  # Up to 15% boost from high confidence
        
        return min(1.0, base_multiplier + confidence_boost)

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

    def search_with_graph_enhancement(
        self,
        search_queries: List[Dict[str, Any]],
        user_id: str,
        limit: int = 20,
        threshold: float = 0.5,
        use_graph: bool = True
    ) -> List[Memory]:
        """
        Enhanced search with graph-based contextual retrieval
        
        Args:
            search_queries: List of search query dictionaries
            user_id: User ID for filtering
            limit: Maximum number of results
            threshold: Similarity threshold
            use_graph: Whether to use graph enhancement
            
        Returns:
            List of memories enhanced with graph relationships
        """
        # First get standard vector-based results
        vector_memories = self.search_memories_with_queries(
            search_queries, user_id, limit, threshold
        )
        
        if not use_graph or not vector_memories:
            return vector_memories
            
        try:
            from .graph_service import graph_service
            
            # Get graph-enhanced memories through traversal
            graph_enhanced_memories = []
            processed_ids = set()
            
            for memory in vector_memories:
                if str(memory.id) not in processed_ids:
                    # Get related memories through graph traversal
                    related_data = graph_service.traverse_related_memories(
                        str(memory.id), user_id, depth=2
                    )
                    
                    # Convert graph data back to Memory objects
                    related_ids = [data['memory_id'] for data in related_data]
                    if related_ids:
                        related_memories = Memory.objects.filter(
                            id__in=related_ids, 
                            is_active=True
                        )
                        
                        # Sort by graph relevance score
                        related_dict = {data['memory_id']: data for data in related_data}
                        related_memories = sorted(
                            related_memories,
                            key=lambda m: related_dict.get(str(m.id), {}).get('relevance_score', 0),
                            reverse=True
                        )
                        
                        # Add to results with graph context
                        for rel_memory in related_memories[:5]:  # Limit related memories
                            if str(rel_memory.id) not in processed_ids:
                                # Add graph metadata to memory
                                graph_data = related_dict.get(str(rel_memory.id), {})
                                if not hasattr(rel_memory, 'graph_metadata'):
                                    rel_memory.graph_metadata = {}
                                rel_memory.graph_metadata.update({
                                    'relevance_score': graph_data.get('relevance_score', 0),
                                    'path_length': graph_data.get('path_length', 0),
                                    'relationship_types': [
                                        rel['type'] for rel in graph_data.get('relationships', [])
                                    ]
                                })
                                graph_enhanced_memories.append(rel_memory)
                                processed_ids.add(str(rel_memory.id))
                    
                    # Always include the original memory
                    if str(memory.id) not in processed_ids:
                        if not hasattr(memory, 'graph_metadata'):
                            memory.graph_metadata = {}
                        memory.graph_metadata['relevance_score'] = 1.0  # Original search result
                        graph_enhanced_memories.append(memory)
                        processed_ids.add(str(memory.id))
            
            # Combine and re-rank results
            final_memories = self._rerank_with_graph_scores(graph_enhanced_memories, limit)
            
            logger.info(
                f"Graph enhancement: {len(vector_memories)} -> {len(final_memories)} memories"
            )
            
            return final_memories
            
        except Exception as e:
            logger.warning(f"Graph enhancement failed, falling back to vector results: {e}")
            return vector_memories

    def _rerank_with_graph_scores(self, memories: List[Memory], limit: int) -> List[Memory]:
        """
        Re-rank memories combining vector and graph scores
        
        Args:
            memories: List of memories with graph metadata
            limit: Maximum number of results
            
        Returns:
            Re-ranked list of memories
        """
        def combined_score(memory):
            base_score = 1.0  # Default for original vector results
            graph_score = getattr(memory, 'graph_metadata', {}).get('relevance_score', 0)
            path_length = getattr(memory, 'graph_metadata', {}).get('path_length', 1)
            
            # Boost high-confidence direct results
            confidence_boost = memory.temporal_confidence * 0.2
            
            # Boost by inference level reliability
            inference_boost = self._get_inference_level_multiplier(memory) * 0.3
            
            # Combine scores (graph score weighted by path distance)
            graph_weight = 0.4 if graph_score > 0 else 0
            vector_weight = 1.0 - graph_weight
            
            final_score = (
                vector_weight * base_score + 
                graph_weight * (graph_score / max(path_length, 1)) +
                confidence_boost + 
                inference_boost
            )
            
            return final_score
        
        # Sort by combined score
        ranked_memories = sorted(memories, key=combined_score, reverse=True)
        
        return ranked_memories[:limit]

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

        # Prepare memory content for analysis with enhanced hybrid information
        memory_content = []
        inference_stats = {"stated": 0, "inferred": 0, "implied": 0}
        conversation_contexts = []
        relationship_info = []
        
        for i, memory in enumerate(memories[:20]):  # Limit to prevent prompt overflow
            inference_level = memory.metadata.get("inference_level", "stated")
            evidence = memory.metadata.get("evidence", "")
            
            # Include conversation context if available from hybrid search
            conversation_context = ""
            if hasattr(memory, 'conversation_context') and memory.conversation_context:
                context_snippets = []
                for ctx in memory.conversation_context[:2]:  # Limit context snippets
                    context_snippets.append(f"Context: {ctx.get('content', '')[:100]}...")
                conversation_context = " | ".join(context_snippets)
                conversation_contexts.append(f"Memory {i+1} context: {conversation_context}")
            
            # Include ranking information if available
            ranking_info = ""
            if hasattr(memory, 'ranking_details'):
                ranking_info = f" [Score: {memory.ranking_details.get('final_score', 0):.2f}]"
            
            inference_stats[inference_level] += 1
            
            # Include reliability indicators in summary
            reliability_indicator = {
                "stated": "🟢",  # High reliability
                "inferred": "🟡",  # Moderate reliability  
                "implied": "🟠"    # Lower reliability
            }.get(inference_level, "⚪")
            
            memory_line = f"{i + 1}. {reliability_indicator} {memory.content}"
            if memory.temporal_confidence < 0.7:
                memory_line += f" (Confidence: {memory.temporal_confidence:.1f})"
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
- Pay attention to confidence scores and evidence provided

**CRITICAL FILTERING REQUIREMENT - SMART DOMAIN SEPARATION:**
You MUST filter memories intelligently based on the query type. Be strict but nuanced:

**QUERY TYPE IDENTIFICATION:**
1. **Factual/Recommendation queries** (suggest music, recommend restaurant): Need direct domain facts
2. **Explanation/Teaching queries** (explain concept, how does X work): Need domain facts + learning preferences + background knowledge

**FILTERING RULES BY QUERY TYPE:**

**For FACTUAL/RECOMMENDATION queries:**
- ONLY include memories with direct factual content in the query domain
- EXCLUDE all other domains completely
- Example: "suggest music" → ONLY music preferences, EXCLUDE food/physics/work entirely

**For EXPLANATION/TEACHING queries:**
- INCLUDE memories from the query domain (physics for "explain Bell's theorem")
- INCLUDE learning preferences (prefers examples, visual learner, etc.)
- INCLUDE related background knowledge that helps contextualize the explanation
- EXCLUDE unrelated domain content BUT acknowledge learning preferences if found
- Example: "explain Bell's theorem" → physics memories + learning style + academic background, EXCLUDE music content but note learning preferences

**SMART EXCLUSION RULE:**
- For recommendations: Exclude everything not directly relevant
- For explanations: Include learning/teaching context even if from different domains, but exclude content from different domains
- NEVER mention irrelevant content domains in your summary"""

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

        # Enhanced fallback summary for hybrid results
        conversation_context_summary = ""
        if conversation_contexts:
            conversation_context_summary = f" Includes conversation context from {len(conversation_contexts)} sources."
        
        return {
            "summary": f"Found {len(memories)} memories related to your query{conversation_context_summary}",
            "key_points": [memory.content[:100] + "..." for memory in memories[:5]],
            "relevant_context": "Multiple memories found but detailed analysis failed",
            "conversation_context": "\n".join(conversation_contexts[:3]) if conversation_contexts else "",
            "patterns_identified": f"Retrieved via hybrid search with inference levels: {inference_stats}",
            "confidence": 0.3,
            "memory_usage": {
                "total_memories": len(memories),
                "highly_relevant": 0,
                "moderately_relevant": len(memories),
                "context_relevant": 0,
            },
            "source_analysis": {
                "conversation_chunks": len(conversation_contexts),
                "extracted_memories": len(memories),
                "relationship_connections": 0,  # Could be enhanced with graph data
                "inference_breakdown": inference_stats
            }
        }


# Global instance
memory_search_service = MemorySearchService()
