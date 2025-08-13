import json
import logging
import uuid

from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from settings_app.models import LLMSettings

from .llm_service import MEMORY_EXTRACTION_FORMAT, MEMORY_SEARCH_FORMAT, llm_service
from .memory_search_service import memory_search_service
from .models import Memory, ConversationChunk
from .serializers import MemorySerializer
from .vector_service import vector_service
from .graph_service import graph_service
from .conflict_resolution_service import conflict_resolution_service
from .memory_consolidation_service import memory_consolidation_service

logger = logging.getLogger(__name__)


class MemoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CRUD operations on memories
    """

    serializer_class = MemorySerializer
    queryset = Memory.objects.all()

    def get_queryset(self):
        """Filter memories by user_id if provided in query params"""
        user_id = self.request.GET.get("user_id")
        if user_id:
            try:
                uuid.UUID(user_id)  # Validate UUID format
                return Memory.objects.filter(user_id=user_id).order_by("-created_at")
            except ValueError:
                logger.warning(f"Invalid user_id format: {user_id}")
                return Memory.objects.none()
        # Return all memories if no user_id filter provided
        return Memory.objects.all().order_by("-created_at")

    def retrieve(self, request, *args, pk=None, **kwargs):
        """Get a specific memory by ID"""
        try:
            # Validate UUID format
            uuid.UUID(pk)
            memory = self.get_object()
            serializer = self.get_serializer(memory)
            return Response(serializer.data)
        except ValueError:
            return Response(
                {"success": False, "error": "Invalid memory ID format"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(
                {"success": False, "error": "Memory not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def list(self, request, *args, **kwargs):
        """List memories with optional user_id filtering"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        return Response(
            {
                "success": True,
                "count": len(serializer.data),
                "memories": serializer.data,
            }
        )

    def create(self, request, *args, **kwargs):
        """Create a new memory"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Validate user_id
            user_id = serializer.validated_data.get("user_id")
            if user_id:
                try:
                    uuid.UUID(str(user_id))
                except ValueError:
                    return Response(
                        {"success": False, "error": "Invalid user_id format"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            memory = serializer.save()
            return Response(
                {"success": True, "memory": self.get_serializer(memory).data},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ExtractMemoriesView(APIView):
    """
    API endpoint to extract memories from conversation text using LLM
    """

    def post(self, request):
        conversation_text = request.data.get("conversation_text", "")
        user_id = request.data.get("user_id")

        if not conversation_text:
            return Response(
                {"success": False, "error": "conversation_text is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user_id:
            return Response(
                {"success": False, "error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate user_id format
        try:
            uuid.UUID(user_id)
        except ValueError:
            return Response(
                {"success": False, "error": "Invalid user_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Get LLM settings for the extraction prompt
            settings = LLMSettings.get_settings()
            system_prompt = settings.memory_extraction_prompt

            logger.info("Extracting memories for user %s", user_id)

            # Add the current datetime to system prompt for time awareness
            system_prompt_with_date = system_prompt
            try:
                now = timezone.now()
                system_prompt_with_date = f"{system_prompt}\n\nCurrent date and time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            except Exception as e:
                logger.warning("Could not add date to system prompt: %s", e)

            # Query LLM to extract memories with higher token limit
            llm_result = llm_service.query_llm(
                system_prompt=system_prompt_with_date,
                prompt=conversation_text,
                response_format=MEMORY_EXTRACTION_FORMAT,
                max_tokens=16384,  # Increased token limit for memory extraction
            )

            if not llm_result["success"]:
                logger.error("LLM extraction failed: %s", llm_result["error"])
                return Response(
                    {
                        "success": False,
                        "error": f"Memory extraction failed: {llm_result['error']}",
                        "memories_extracted": 0,
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Parse the JSON response with robust error handling
            try:
                response_text = llm_result["response"].strip()
                memories_data = json.loads(response_text)
                if not isinstance(memories_data, list):
                    raise ValueError("Expected a JSON array")

            except (json.JSONDecodeError, ValueError) as e:
                logger.error("Failed to parse LLM response as JSON: %s", e)
                logger.debug(
                    "LLM response length: %d chars", len(llm_result.get("response", ""))
                )
                logger.debug(
                    "LLM response preview: %s...", llm_result.get("response", "")[:500]
                )

                # Try to recover partial results from truncated JSON
                try:
                    response_text = llm_result["response"].strip()

                    # Handle truncated JSON array by finding the last complete object
                    if response_text.startswith("[") and "{" in response_text:
                        # Find the position of the last complete JSON object
                        last_complete_brace = response_text.rfind("}")
                        if last_complete_brace != -1:
                            # Try to create valid JSON by truncating after the last complete object
                            truncated_json = response_text[: last_complete_brace + 1]
                            if not truncated_json.endswith("]"):
                                truncated_json += "]"

                            memories_data = json.loads(truncated_json)
                            if (
                                isinstance(memories_data, list)
                                and len(memories_data) > 0
                            ):
                                logger.warning(
                                    "Recovered %d memories from truncated JSON response",
                                    len(memories_data),
                                )
                            else:
                                raise ValueError(
                                    "No valid memories found in truncated response"
                                )
                        else:
                            raise ValueError("Could not find any complete JSON objects")
                    else:
                        raise ValueError(
                            "Response does not appear to contain a JSON array"
                        )

                except Exception as recovery_error:
                    logger.error(
                        "Failed to recover memories from malformed JSON: %s",
                        recovery_error,
                    )
                    return Response(
                        {
                            "success": False,
                            "error": "Failed to parse memory extraction results. The response may have been truncated due to token limits.",
                            "memories_extracted": 0,
                            "debug_info": {
                                "response_length": len(llm_result.get("response", "")),
                                "parse_error": str(e),
                                "recovery_error": str(recovery_error),
                            },
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

            # NEW HYBRID ARCHITECTURE: Store conversation chunks and extracted memories
            
            # Prepare memories for the new storage method
            extracted_memories = []
            for memory_data in memories_data:
                if not isinstance(memory_data, dict):
                    continue

                content = memory_data.get("content", "")
                if not content:
                    continue

                # Extract all fields including new entity_type and relationship_hints
                # Validate and normalize entity_type
                entity_type = memory_data.get("entity_type", "general")
                if entity_type not in ["person", "place", "preference", "skill", "fact", "event", "general"]:
                    entity_type = "general"
                
                # Validate and normalize fact_type
                fact_type = memory_data.get("fact_type", "mutable")
                if fact_type not in ["mutable", "immutable", "temporal"]:
                    fact_type = "mutable"
                
                # Validate and normalize inference_level
                inference_level = memory_data.get("inference_level", "stated")
                if inference_level not in ["stated", "inferred", "implied"]:
                    inference_level = "stated"
                
                # Validate relationship_hints
                valid_hints = ["supports", "contradicts", "relates_to", "temporal_sequence", "updates"]
                relationship_hints = [h for h in memory_data.get("relationship_hints", []) if h in valid_hints]
                
                memory_info = {
                    "content": content,
                    "tags": memory_data.get("tags", []),
                    "confidence": min(max(memory_data.get("confidence", 0.5), 0.0), 1.0),  # Clamp to [0,1]
                    "entity_type": entity_type,
                    "relationship_hints": relationship_hints,
                    "fact_type": fact_type,
                    "inference_level": inference_level,
                    "evidence": memory_data.get("evidence", ""),
                    "model_used": llm_result.get("model", "unknown"),
                }
                extracted_memories.append(memory_info)
            
            # Store using the new hybrid approach
            timestamp = timezone.now().isoformat()
            try:
                storage_result = memory_search_service.store_conversation_and_memories(
                    conversation_text=conversation_text,
                    extracted_memories=extracted_memories,
                    user_id=user_id,
                    timestamp=timestamp
                )
                
                # Get created memories for conflict resolution
                memory_ids = storage_result.get("memory_ids", [])
                stored_memories = list(Memory.objects.filter(id__in=memory_ids))
                
                # Perform conflict resolution on the new memories
                conflicts_resolved = 0
                duplicates_consolidated = 0  # Initialize before the loop
                existing_memories = list(Memory.objects.filter(
                    user_id=user_id, 
                    is_active=True
                ).exclude(id__in=memory_ids))
                
                for memory in stored_memories:
                    # Detect and resolve conflicts
                    conflicts = conflict_resolution_service.detect_conflicts(
                        memory.content, memory.metadata, existing_memories
                    )
                    
                    if conflicts:
                        conflicts_resolved += len(conflicts)
                        for conflicting_memory, similarity, conflict_type in conflicts:
                            logger.info(
                                f"Resolving {conflict_type} conflict (similarity: {similarity:.2f}) "
                                f"between new memory {memory.id} and existing memory {conflicting_memory.id}"
                            )
                        memory = conflict_resolution_service.resolve_conflict(
                            memory, conflicting_memory, conflict_type
                        )

                    # Check for duplicates after conflict resolution
                    duplicates = memory_consolidation_service.find_duplicates(
                        memory, user_id
                    )
                    
                    if duplicates:
                        # Filter duplicates that might be suitable for consolidation
                        consolidation_candidates = [
                            (dup_memory, score, dup_type) for dup_memory, score, dup_type in duplicates
                            if dup_type in ['exact_duplicate', 'near_duplicate'] and score >= 0.90
                        ]
                        
                        if consolidation_candidates:
                            duplicates_consolidated += len(consolidation_candidates)
                            
                            # Consolidate with the most similar duplicate
                            memories_to_consolidate = [memory] + [dup[0] for dup in consolidation_candidates[:2]]  # Limit to avoid over-consolidation
                            
                            consolidated_memory = memory_consolidation_service.merge_memories(
                                memories_to_consolidate, 
                                consolidation_strategy="llm_guided"
                            )
                            
                            if consolidated_memory:
                                memory = consolidated_memory
                                logger.info(
                                    f"Consolidated {len(memories_to_consolidate)} duplicate memories into {memory.id}"
                                )

                # Collect enhanced memory data for response (outside the loop)
                enhanced_memories = []
                for memory in stored_memories:
                    enhanced_memories.append(
                        {
                            "id": str(memory.id),
                            "content": memory.content,
                            "metadata": memory.metadata,
                            "fact_type": memory.fact_type,
                            "entity_type": memory.metadata.get("entity_type", "general"),
                            "inference_level": memory.metadata.get("inference_level", "stated"),
                            "evidence": memory.metadata.get("evidence", ""),
                            "confidence": memory.temporal_confidence,
                            "is_active": memory.is_active,
                            "created_at": memory.created_at.isoformat(),
                            "supersedes": str(memory.supersedes.id) if memory.supersedes else None,
                            "conversation_chunk_ids": memory.conversation_chunk_ids if hasattr(memory, 'conversation_chunk_ids') else [],
                        }
                    )
                
                logger.info(
                    "Successfully extracted and stored %d memories with %d conflicts resolved and %d duplicates consolidated via hybrid architecture", 
                    len(enhanced_memories), conflicts_resolved, duplicates_consolidated
                )

                # Auto-build graph if graph-enhanced retrieval is enabled and we have new memories
                graph_build_result = None
                if settings.enable_graph_enhanced_retrieval and enhanced_memories:
                    try:
                        logger.info("Auto-building graph relationships for %d new memories", len(enhanced_memories))
                        graph_build_result = graph_service.build_memory_graph(user_id, incremental=True)
                        if graph_build_result.get("success"):
                            logger.info("Auto-build successful: %d relationships created", 
                                      graph_build_result.get("relationships_created", 0))
                        else:
                            logger.warning("Auto-build failed: %s", graph_build_result.get("error"))
                    except Exception as e:
                        logger.error("Error during auto-build: %s", e)

                response_data = {
                    "success": True,
                    "memories_extracted": len(enhanced_memories),
                    "conflicts_resolved": conflicts_resolved,
                    "duplicates_consolidated": duplicates_consolidated,
                    "memories": enhanced_memories,
                    "model_used": llm_result.get("model", "unknown"),
                    # New hybrid architecture information
                    "hybrid_storage": {
                        "conversation_chunks_created": storage_result.get("chunks_created", 0),
                        "chunk_ids": storage_result.get("chunk_ids", []),
                        "conversation_length": storage_result.get("conversation_length", 0),
                        "chunks_generated": storage_result.get("chunks_generated", 0),
                    }
                }

                # Include graph build results if auto-building occurred
                if graph_build_result:
                    response_data["graph_build_result"] = {
                        "success": graph_build_result.get("success", False),
                        "relationships_created": graph_build_result.get("relationships_created", 0),
                        "incremental": graph_build_result.get("incremental", True)
                    }

                return Response(response_data)
            
            except Exception as storage_error:
                logger.error("Failed to store conversation and memories: %s", storage_error)
                return Response(
                    {
                        "success": False,
                        "error": f"Failed to store memories: {str(storage_error)}",
                        "memories_extracted": len(extracted_memories),
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            logger.error("Unexpected error during memory extraction: %s", e)
            return Response(
                {
                    "success": False,
                    "error": "An unexpected error occurred during memory extraction",
                    "memories_extracted": 0,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RetrieveMemoriesView(APIView):
    """
    API endpoint to retrieve relevant memories for a prompt using vector search
    """

    def post(self, request):
        prompt = request.data.get("prompt", "")
        user_id = request.data.get("user_id")
        limit = request.data.get("limit", 99)
        threshold = request.data.get("threshold", 0.7)
        boosted_threshold = request.data.get("boosted_threshold", 0.5)

        if not prompt:
            return Response(
                {"success": False, "error": "prompt is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user_id:
            return Response(
                {"success": False, "error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate user_id format
        try:
            uuid.UUID(user_id)
        except ValueError:
            return Response(
                {"success": False, "error": "Invalid user_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate limit and threshold
        try:
            limit = int(limit)
            if limit <= 0 or limit > 100:
                limit = 10
        except (ValueError, TypeError):
            limit = 10

        try:
            threshold = float(threshold)
            if threshold < 0.0 or threshold > 1.0:
                threshold = 0.7
        except (ValueError, TypeError):
            threshold = 0.7

        try:
            boosted_threshold = float(boosted_threshold)
            if boosted_threshold < 0.0 or boosted_threshold > 1.0:
                boosted_threshold = 0.5
        except (ValueError, TypeError):
            boosted_threshold = 0.5

        try:
            # Step 1: Get LLM settings and determine graph usage from app-level setting
            settings = LLMSettings.get_settings()
            use_graph = settings.enable_graph_enhanced_retrieval
            search_prompt = settings.memory_search_prompt

            logger.info(
                "Generating search queries for user %s with prompt: %s... (graph: %s)",
                user_id,
                prompt,
                use_graph
            )

            # Query LLM to generate search queries
            llm_result = llm_service.query_llm(
                prompt=prompt,
                system_prompt=search_prompt,
                response_format=MEMORY_SEARCH_FORMAT,
            )

            if not llm_result["success"]:
                logger.error(
                    "Failed to generate search queries: %s", llm_result["error"]
                )
                return Response(
                    {
                        "success": False,
                        "error": f"Search query generation failed: {llm_result['error']}",
                        "memories": [],
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Step 2: Parse the search queries JSON
            try:
                search_queries = json.loads(llm_result["response"])
                if not isinstance(search_queries, list):
                    raise ValueError("Expected a JSON array of search queries")
            except (json.JSONDecodeError, ValueError) as e:
                logger.error("Failed to parse search queries as JSON: %s", e)
                logger.debug("LLM response: %s", llm_result["response"])
                # Fallback: use original prompt as single search query
                search_queries = [{"search_query": prompt, "confidence": 0.5}]

            logger.info("Generated %d search queries", len(search_queries))

            # Step 3: Use new hybrid search architecture
            # The hybrid approach automatically uses both conversation search and graph expansion
            relevant_memories = memory_search_service.search_memories_with_hybrid_approach(
                search_queries=search_queries,
                user_id=user_id,
                limit=limit,
                threshold=threshold,
            )
            
            # Get expanded conversation context if available
            conversation_context = None
            if relevant_memories and use_graph:
                memory_ids = [str(m.id) for m in relevant_memories[:10]]  # Top 10 for context expansion
                conversation_context = memory_search_service.expand_conversation_context(
                    memory_ids=memory_ids,
                    user_id=user_id
                )

            # Step 4: Find additional semantic connections if enabled and we have enough results
            settings = LLMSettings.get_settings()
            if (
                settings.enable_semantic_connections
                and relevant_memories
                and len(relevant_memories) >= settings.semantic_enhancement_threshold
            ):
                logger.info("Finding additional semantic connections...")
                relevant_memories = memory_search_service.find_semantic_connections(
                    memories=relevant_memories,
                    original_query=prompt,
                    user_id=user_id,
                )
                logger.info(
                    "After semantic connection analysis: %d memories",
                    len(relevant_memories),
                )
            else:
                logger.info(
                    "Skipping semantic connections: enabled=%s, memories=%d, threshold=%d",
                    settings.enable_semantic_connections,
                    len(relevant_memories),
                    settings.semantic_enhancement_threshold,
                )

            # Step 5: Generate memory summary for AI assistance
            memory_summary = None
            if relevant_memories:
                logger.info("Generating memory summary...")
                memory_summary = memory_search_service.summarize_relevant_memories(
                    memories=relevant_memories, user_query=prompt
                )
                logger.info(
                    "Memory summary generated with %d key points",
                    len(memory_summary.get("key_points", [])),
                )

            # Step 6: Format memories for response with enhanced hybrid information
            formatted_memories = []
            for memory in relevant_memories:
                memory_data = {
                    "id": str(memory.id),
                    "content": memory.content,
                    "metadata": memory.metadata,
                    "created_at": memory.created_at.isoformat(),
                    "updated_at": memory.updated_at.isoformat(),
                    # Include hybrid search scoring if available
                    "hybrid_search_score": getattr(memory, 'hybrid_search_score', None),
                    "conversation_chunk_ids": memory.conversation_chunk_ids if hasattr(memory, 'conversation_chunk_ids') else [],
                }
                formatted_memories.append(memory_data)

            logger.info("Found %d relevant memories via hybrid search", len(formatted_memories))

            response_data = {
                "success": True,
                "memories": formatted_memories,
                "memory_summary": memory_summary,
                "count": len(formatted_memories),
                "search_queries_generated": len(search_queries),
                "model_used": llm_result.get("model", "unknown"),
                "query_params": {
                    "limit": limit,
                    "threshold": threshold,
                },
                "hybrid_search_info": {
                    "graph_enabled": use_graph,
                    "conversation_context_available": conversation_context is not None,
                }
            }
            
            # Include conversation context if available
            if conversation_context:
                response_data["conversation_context"] = {
                    "total_sessions": conversation_context.get("total_sessions", 0),
                    "total_expanded_chunks": conversation_context.get("total_expanded_chunks", 0),
                    "context_summary": conversation_context.get("context_summary", {})
                }

            return Response(response_data)

        except Exception as e:
            logger.error("Unexpected error during memory retrieval: %s", e)
            return Response(
                {
                    "success": False,
                    "error": "An unexpected error occurred during memory retrieval",
                    "memories": [],
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TestConnectionView(APIView):
    """
    API endpoint to test connections to LLM and vector services
    """

    def get(self, request):
        try:
            # Refresh LLM settings
            llm_service.refresh_settings()

            # Test LLM connection
            llm_result = llm_service.test_connection()

            # Test vector service
            from .vector_service import vector_service

            vector_health = vector_service.health_check()
            vector_info = vector_service.get_collection_info()

            return Response(
                {
                    "llm_connection": llm_result.get("llm_connection", False),
                    "llm_error": llm_result.get("llm_error"),
                    "embeddings_connection": llm_result.get(
                        "embeddings_connection", False
                    ),
                    "embeddings_error": llm_result.get("embeddings_error"),
                    "vector_service_health": vector_health,
                    "vector_collection_info": vector_info,
                }
            )

        except Exception as e:
            logger.error("Error testing connections: %s", e)
            return Response(
                {
                    "error": "Failed to test connections",
                    "llm_connection": False,
                    "embeddings_connection": False,
                    "vector_service_health": False,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MemoryStatsView(APIView):
    """
    API endpoint to get memory statistics for a user
    """

    def get(self, request):
        user_id = request.query_params.get("user_id")

        if not user_id:
            return Response(
                {"success": False, "error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            uuid.UUID(user_id)
        except ValueError:
            return Response(
                {"success": False, "error": "Invalid user_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            memories = Memory.objects.filter(user_id=user_id)

            # Basic stats
            total_memories = memories.count()

            # Count tags (remove memory_banks grouping)
            tags_count = {}
            domain_tags = {}  # Track domain-related tags separately if needed

            for memory in memories:
                metadata = memory.metadata or {}

                # Count all tags
                tags = metadata.get("tags", [])
                for tag in tags:
                    tags_count[tag] = tags_count.get(tag, 0) + 1

                    # Optionally group domain tags for insights
                    if tag in ["personal", "professional", "academic", "creative"]:
                        domain_tags[tag] = domain_tags.get(tag, 0) + 1

            # Get vector service stats
            from .vector_service import vector_service

            collection_info = vector_service.get_collection_info()

            return Response(
                {
                    "success": True,
                    "total_memories": total_memories,
                    "domain_distribution": domain_tags,  # Replace memory_banks with domain_distribution
                    "top_tags": dict(
                        sorted(
                            tags_count.items(), key=lambda x: x[1], reverse=True
                        )  # Show more tags
                    ),
                    "vector_collection_info": collection_info,
                }
            )

        except Exception as e:
            logger.error("Error getting memory stats: %s", e)
            return Response(
                {"success": False, "error": "Failed to get memory statistics"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DeleteAllMemoriesView(APIView):
    """Delete all memories for a user or all users"""

    def delete(self, request):
        user_id = request.data.get("user_id")
        confirm = request.data.get("confirm", False)

        if not confirm:
            return Response(
                {"success": False, "error": "Confirmation required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if user_id:
                # Validate user_id format
                try:
                    uuid.UUID(user_id)
                except ValueError:
                    return Response(
                        {"success": False, "error": "Invalid user_id format"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Delete memories for specific user
                memories_to_delete = Memory.objects.filter(user_id=user_id)
                count = memories_to_delete.count()

                if count == 0:
                    return Response(
                        {
                            "success": True,
                            "message": f"No memories found for user {user_id}",
                            "deleted_count": 0,
                        }
                    )

                # Delete from vector database first
                memory_ids = [str(memory.id) for memory in memories_to_delete]
                vector_delete_result = vector_service.delete_memories(
                    memory_ids, user_id
                )

                if not vector_delete_result["success"]:
                    logger.error(
                        f"Failed to delete vectors for user {user_id}: {vector_delete_result['error']}"
                    )
                    return Response(
                        {
                            "success": False,
                            "error": f"Failed to delete from vector database: {vector_delete_result['error']}",
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                # Delete from main database
                memories_to_delete.delete()

                logger.info(f"Deleted {count} memories for user {user_id}")
                return Response(
                    {
                        "success": True,
                        "message": f"Successfully deleted {count} memories for user {user_id}",
                        "deleted_count": count,
                        "user_id": user_id,
                    }
                )
            else:
                # Delete ALL memories (admin operation)
                total_count = Memory.objects.count()

                if total_count == 0:
                    return Response(
                        {
                            "success": True,
                            "message": "No memories found in database",
                            "deleted_count": 0,
                        }
                    )

                # Clear entire vector database
                vector_clear_result = vector_service.clear_all_memories()

                if not vector_clear_result["success"]:
                    logger.error(
                        f"Failed to clear vector database: {vector_clear_result['error']}"
                    )
                    return Response(
                        {
                            "success": False,
                            "error": f"Failed to clear vector database: {vector_clear_result['error']}",
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                # Delete all memories from main database
                Memory.objects.all().delete()

                logger.warning(
                    f"ADMIN ACTION: Deleted ALL {total_count} memories from database"
                )
                return Response(
                    {
                        "success": True,
                        "message": f"Successfully deleted ALL {total_count} memories",
                        "deleted_count": total_count,
                    }
                )

        except Exception as e:
            logger.error(f"Error deleting memories: {e}")
            return Response(
                {"success": False, "error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TextToGraphView(APIView):
    """
    DEPRECATED: API endpoint to convert text to graph documents and store in Neo4j
    Use the memory extraction endpoint with hybrid architecture instead.
    """

    def post(self, request):
        text = request.data.get("text", "")
        user_id = request.data.get("user_id")

        if not text:
            return Response(
                {"success": False, "error": "text is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user_id:
            return Response(
                {"success": False, "error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate user_id format
        try:
            uuid.UUID(user_id)
        except ValueError:
            return Response(
                {"success": False, "error": "Invalid user_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Return deprecation notice
        logger.warning("TextToGraphView is deprecated. User %s attempted to use deprecated endpoint.", user_id)
        
        return Response(
            {
                "success": False,
                "error": "This endpoint is deprecated. Use the memory extraction endpoint (/extract-memories/) with the new hybrid architecture instead.",
                "deprecated": True,
                "recommendation": "Use POST /extract-memories/ with conversation_text to store both conversation chunks and extracted memories."
            },
            status=status.HTTP_410_GONE,
        )


class GraphStatsView(APIView):
    """
    API endpoint to get graph statistics for a user
    """

    def get(self, request):
        user_id = request.query_params.get("user_id")

        if not user_id:
            return Response(
                {"success": False, "error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            uuid.UUID(user_id)
        except ValueError:
            return Response(
                {"success": False, "error": "Invalid user_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Get user-specific graph statistics
            stats = graph_service.get_user_graph_stats(user_id)
            
            if "error" in stats:
                return Response(
                    {"success": False, "error": stats["error"]},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            
            # Get overall database info
            db_info = graph_service.get_database_info()
            
            return Response(
                {
                    "success": True,
                    "user_stats": stats,
                    "database_info": db_info,
                }
            )

        except Exception as e:
            logger.error("Error getting graph stats: %s", e)
            return Response(
                {"success": False, "error": "Failed to get graph statistics"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GraphHealthView(APIView):
    """
    API endpoint to check graph database health
    """

    def get(self, request):
        try:
            health_check = graph_service.health_check()
            
            if health_check["healthy"]:
                return Response(
                    {
                        "success": True,
                        "healthy": True,
                        "message": health_check["message"],
                        "database_info": graph_service.get_database_info(),
                    }
                )
            else:
                return Response(
                    {
                        "success": False,
                        "healthy": False,
                        "error": health_check["error"],
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            logger.error("Error checking graph health: %s", e)
            return Response(
                {
                    "success": False,
                    "healthy": False,
                    "error": "Failed to check graph database health",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GraphQueryView(APIView):
    """
    API endpoint to execute Cypher queries against the graph database
    """

    def post(self, request):
        query = request.data.get("query", "")

        if not query:
            return Response(
                {"success": False, "error": "query is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            logger.info("Executing graph query: %s", query)
            
            # Execute the Cypher query
            result = graph_service.query_graph(query)
            
            if result["success"]:
                return Response(
                    {
                        "success": True,
                        "results": result["results"],
                        "count": result["count"],
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                logger.error("Graph query failed: %s", result["error"])
                return Response(
                    {
                        "success": False,
                        "error": f"Graph query failed: {result['error']}",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            logger.error("Unexpected error during graph query: %s", e)
            return Response(
                {
                    "success": False,
                    "error": "An unexpected error occurred during graph query execution",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BuildMemoryGraphView(APIView):
    """
    API endpoint to build memory relationship graph for all users or a specific user
    """
    
    def post(self, request):
        user_id = request.data.get("user_id")
        build_for_all = request.data.get("build_for_all", False)
        incremental = request.data.get("incremental", True)  # Default to incremental
        
        # If build_for_all is True, build graph for all users
        if build_for_all:
            try:
                logger.info("Building memory graph for ALL users (incremental: %s)", incremental)
                
                # Update build status to building
                settings = LLMSettings.get_settings()
                settings.graph_build_status = "building"
                settings.save()
                
                # Get all unique user IDs from Memory model
                logger.info("Checking total memories in database...")
                total_memories = Memory.objects.count()
                active_memories = Memory.objects.filter(is_active=True).count()
                logger.info("Total memories: %d, Active memories: %d", total_memories, active_memories)
                
                unique_user_ids = Memory.objects.filter(is_active=True).values_list('user_id', flat=True).distinct().order_by('user_id')
                unique_user_list = list(unique_user_ids)
                logger.info("Found %d unique user IDs to process", len(unique_user_list))
                logger.info("User IDs: %s", [str(uid) for uid in unique_user_list])
                
                total_nodes = 0
                total_relationships = 0
                failed_users = []
                
                for uid in unique_user_list:
                    try:
                        logger.info("Building graph for user %s", uid)
                        result = graph_service.build_memory_graph(uid, incremental=incremental)
                        if result["success"]:
                            total_nodes += result.get("nodes_created", 0)
                            total_relationships += result.get("relationships_created", 0)
                        else:
                            failed_users.append(str(uid))
                            error_msg = result.get("error", "Unknown error")
                            logger.error("Failed to build graph for user %s: %s", uid, error_msg)
                            
                            # If Neo4j connection fails, fail fast for all users
                            if "Neo4j driver not initialized" in error_msg:
                                logger.error("Neo4j connection failed - aborting build for all users")
                                settings.graph_build_status = "failed"
                                settings.save()
                                return Response(
                                    {
                                        "success": False,
                                        "error": "Neo4j database connection failed. Please check Neo4j is running and credentials are correct.",
                                        "neo4j_error": True
                                    },
                                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                )
                    except Exception as e:
                        failed_users.append(str(uid))
                        logger.error("Error building graph for user %s: %s", uid, e)
                
                # Update build status
                logger.info("Build complete - processed %d users, %d failed", len(unique_user_list), len(failed_users))
                logger.info("Total nodes: %d, Total relationships: %d", total_nodes, total_relationships)
                
                if failed_users:
                    logger.info("Failed users: %s", failed_users)
                    settings.graph_build_status = "partial"
                else:
                    logger.info("All users processed successfully - setting status to 'built'")
                    settings.graph_build_status = "built"
                    
                from django.utils import timezone
                settings.graph_last_build = timezone.now()
                settings.save()
                
                return Response({
                    "success": len(failed_users) == 0,
                    "message": f"Memory graph built for {len(unique_user_list) - len(failed_users)} users",
                    "nodes_created": total_nodes,
                    "relationships_created": total_relationships,
                    "incremental": incremental,
                    "total_users": len(unique_user_list),
                    "failed_users": failed_users,
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error("Unexpected error during bulk graph building: %s", e)
                settings = LLMSettings.get_settings()
                settings.graph_build_status = "failed"
                settings.save()
                return Response(
                    {
                        "success": False,
                        "error": "An unexpected error occurred during graph building",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        
        # Build for specific user (original behavior)
        if not user_id:
            return Response(
                {"success": False, "error": "user_id is required when build_for_all is False"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Validate user_id format
        try:
            uuid.UUID(user_id)
        except ValueError:
            return Response(
                {"success": False, "error": "Invalid user_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            logger.info("Building memory graph for user %s (incremental: %s)", user_id, incremental)
            
            # Update build status to building
            settings = LLMSettings.get_settings()
            settings.graph_build_status = "building"
            settings.save()
            
            # Build the memory graph
            result = graph_service.build_memory_graph(user_id, incremental=incremental)
            
            if result["success"]:
                # Update build status to built
                settings.graph_build_status = "built"
                from django.utils import timezone
                settings.graph_last_build = timezone.now()
                settings.save()
                
                return Response(
                    {
                        "success": True,
                        "message": "Memory graph built successfully",
                        "nodes_created": result["nodes_created"],
                        "relationships_created": result["relationships_created"],
                        "incremental": result["incremental"],
                        "user_id": user_id,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                # Update build status to failed
                settings.graph_build_status = "failed"
                settings.save()
                
                logger.error("Graph building failed: %s", result.get("error"))
                return Response(
                    {
                        "success": False,
                        "error": f"Graph building failed: {result.get('error')}",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        
        except Exception as e:
            logger.error("Unexpected error during graph building: %s", e)
            # Update build status to failed
            settings = LLMSettings.get_settings()
            settings.graph_build_status = "failed"
            settings.save()
            
            return Response(
                {
                    "success": False,
                    "error": "An unexpected error occurred during graph building",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TraverseMemoryGraphView(APIView):
    """
    API endpoint to traverse memory graph and find related memories
    """
    
    def post(self, request):
        memory_id = request.data.get("memory_id")
        user_id = request.data.get("user_id")
        depth = request.data.get("depth", 2)
        
        if not memory_id:
            return Response(
                {"success": False, "error": "memory_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
            
        if not user_id:
            return Response(
                {"success": False, "error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Validate parameters
        try:
            uuid.UUID(user_id)
            uuid.UUID(memory_id)
            depth = int(depth)
            if depth < 1 or depth > 5:
                depth = 2
        except ValueError:
            return Response(
                {"success": False, "error": "Invalid parameter format"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            logger.info("Traversing memory graph from %s for user %s (depth: %d)", 
                       memory_id, user_id, depth)
            
            # Traverse the graph
            related_memories = graph_service.traverse_related_memories(
                memory_id, user_id, depth
            )
            
            return Response(
                {
                    "success": True,
                    "related_memories": related_memories,
                    "count": len(related_memories),
                    "starting_memory_id": memory_id,
                    "traversal_depth": depth,
                },
                status=status.HTTP_200_OK,
            )
        
        except Exception as e:
            logger.error("Unexpected error during graph traversal: %s", e)
            return Response(
                {
                    "success": False,
                    "error": "An unexpected error occurred during graph traversal",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MemoryClustersView(APIView):
    """
    API endpoint to get memory clusters for a user
    """
    
    def get(self, request):
        user_id = request.query_params.get("user_id")
        
        if not user_id:
            return Response(
                {"success": False, "error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            uuid.UUID(user_id)
        except ValueError:
            return Response(
                {"success": False, "error": "Invalid user_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            logger.info("Getting memory clusters for user %s", user_id)
            
            # Get memory clusters
            clusters = graph_service.get_memory_clusters(user_id)
            
            # Get centrality scores
            centrality_scores = graph_service.get_memory_centrality_scores(user_id)
            
            return Response(
                {
                    "success": True,
                    "clusters": clusters,
                    "centrality_scores": centrality_scores,
                    "cluster_count": len(clusters),
                    "user_id": user_id,
                },
                status=status.HTTP_200_OK,
            )
        
        except Exception as e:
            logger.error("Unexpected error getting memory clusters: %s", e)
            return Response(
                {
                    "success": False,
                    "error": "An unexpected error occurred getting memory clusters",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GraphStatusView(APIView):
    """
    API endpoint to check graph build status and requirements
    """
    
    def get(self, request):
        user_id = request.query_params.get("user_id")
        
        if not user_id:
            return Response(
                {"success": False, "error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            uuid.UUID(user_id)
        except ValueError:
            return Response(
                {"success": False, "error": "Invalid user_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            logger.info("Checking graph status for user %s", user_id)
            
            # Get current settings
            settings = LLMSettings.get_settings()
            
            # Count active memories for the user
            memory_count = Memory.objects.filter(user_id=user_id, is_active=True).count()
            
            # Check graph node count
            graph_stats = graph_service.get_user_graph_stats(user_id)
            graph_node_count = graph_stats.get('node_count', 0) if 'error' not in graph_stats else 0
            
            # Determine if graph needs building
            needs_build = memory_count > graph_node_count
            has_graph = graph_node_count > 0
            
            # Check if graph is outdated (more than 10 memories difference)
            is_outdated = memory_count - graph_node_count > 10
            
            return Response(
                {
                    "success": True,
                    "has_graph": has_graph,
                    "needs_build": needs_build,
                    "is_outdated": is_outdated,
                    "memory_count": memory_count,
                    "graph_node_count": graph_node_count,
                    "last_build": settings.graph_last_build,
                    "build_status": settings.graph_build_status,
                    "enabled": settings.enable_graph_enhanced_retrieval,
                    "user_id": user_id,
                },
                status=status.HTTP_200_OK,
            )
        
        except Exception as e:
            logger.error("Error checking graph status: %s", e)
            return Response(
                {
                    "success": False,
                    "error": "An unexpected error occurred checking graph status",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ConversationChunkViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CRUD operations on conversation chunks in the hybrid architecture
    """
    queryset = ConversationChunk.objects.all()
    
    def get_serializer_class(self):
        # Return a basic serializer class since we'll define inline
        from rest_framework import serializers
        
        class ConversationChunkSerializer(serializers.ModelSerializer):
            class Meta:
                model = ConversationChunk
                fields = '__all__'
                
        return ConversationChunkSerializer

    def get_queryset(self):
        """Filter conversation chunks by user_id if provided"""
        user_id = self.request.GET.get("user_id")
        if user_id:
            try:
                uuid.UUID(user_id)  # Validate UUID format
                return ConversationChunk.objects.filter(user_id=user_id).order_by("-timestamp")
            except ValueError:
                logger.warning(f"Invalid user_id format: {user_id}")
                return ConversationChunk.objects.none()
        return ConversationChunk.objects.all().order_by("-timestamp")

    def retrieve(self, request, *args, pk=None, **kwargs):
        """Get a specific conversation chunk by ID"""
        try:
            uuid.UUID(pk)  # Validate UUID format
            chunk = self.get_object()
            serializer = self.get_serializer(chunk)
            return Response({
                "success": True,
                "chunk": serializer.data
            })
        except ValueError:
            return Response(
                {"success": False, "error": "Invalid chunk ID format"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ConversationChunk.DoesNotExist:
            return Response(
                {"success": False, "error": "Conversation chunk not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def list(self, request, *args, **kwargs):
        """List conversation chunks with pagination"""
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "chunks": serializer.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "chunks": serializer.data,
            "count": len(serializer.data)
        })


class ConversationChunkMemoriesView(APIView):
    """
    API endpoint to get memories extracted from a specific conversation chunk
    """
    
    def get(self, request, chunk_id):
        """Get memories that were extracted from this conversation chunk"""
        try:
            uuid.UUID(chunk_id)  # Validate UUID format
        except ValueError:
            return Response(
                {"success": False, "error": "Invalid chunk ID format"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            chunk = ConversationChunk.objects.get(id=chunk_id)
            memory_ids = chunk.extracted_memory_ids or []
            
            if not memory_ids:
                return Response({
                    "success": True,
                    "memories": [],
                    "count": 0,
                    "chunk_info": {
                        "id": str(chunk.id),
                        "content_preview": chunk.get_conversation_preview(),
                        "timestamp": chunk.timestamp.isoformat(),
                    }
                })
            
            # Get the memories
            memories = Memory.objects.filter(id__in=memory_ids, is_active=True).order_by('-created_at')
            
            formatted_memories = []
            for memory in memories:
                formatted_memories.append({
                    "id": str(memory.id),
                    "content": memory.content,
                    "metadata": memory.metadata,
                    "entity_type": memory.metadata.get("entity_type", "general"),
                    "fact_type": memory.fact_type,
                    "inference_level": memory.metadata.get("inference_level", "stated"),
                    "created_at": memory.created_at.isoformat(),
                })
            
            return Response({
                "success": True,
                "memories": formatted_memories,
                "count": len(formatted_memories),
                "chunk_info": {
                    "id": str(chunk.id),
                    "content_preview": chunk.get_conversation_preview(),
                    "timestamp": chunk.timestamp.isoformat(),
                    "total_content_length": len(chunk.content),
                }
            })
            
        except ConversationChunk.DoesNotExist:
            return Response(
                {"success": False, "error": "Conversation chunk not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error("Error retrieving memories for chunk %s: %s", chunk_id, e)
            return Response(
                {"success": False, "error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ConversationSearchView(APIView):
    """
    API endpoint to search conversation chunks using vector similarity
    """
    
    def post(self, request):
        """Search conversation chunks by content similarity"""
        query = request.data.get("query", "")
        user_id = request.data.get("user_id")
        limit = request.data.get("limit", 20)
        threshold = request.data.get("threshold", 0.5)
        
        if not query:
            return Response(
                {"success": False, "error": "query is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if not user_id:
            return Response(
                {"success": False, "error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            uuid.UUID(user_id)  # Validate UUID format
        except ValueError:
            return Response(
                {"success": False, "error": "Invalid user_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            # Get embedding for the query
            from .llm_service import llm_service
            embedding_result = llm_service.get_embeddings([query])
            
            if not embedding_result["success"]:
                return Response(
                    {"success": False, "error": "Failed to generate query embedding"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            
            # Search conversation chunks
            search_results = vector_service.search_conversation_context(
                query_embedding=embedding_result["embeddings"][0],
                user_id=user_id,
                limit=limit,
                score_threshold=threshold
            )
            
            # Format results
            formatted_results = []
            for result in search_results:
                chunk_id = result["chunk_id"]
                try:
                    chunk = ConversationChunk.objects.get(id=chunk_id)
                    formatted_results.append({
                        "chunk_id": chunk_id,
                        "content": result.get("content", ""),
                        "score": result["score"],
                        "timestamp": result.get("timestamp"),
                        "extracted_memories_count": len(chunk.extracted_memory_ids or []),
                        "content_preview": chunk.get_conversation_preview(150),
                    })
                except ConversationChunk.DoesNotExist:
                    # Skip chunks that no longer exist
                    continue
            
            return Response({
                "success": True,
                "results": formatted_results,
                "count": len(formatted_results),
                "query": query,
                "search_params": {
                    "limit": limit,
                    "threshold": threshold,
                }
            })
            
        except Exception as e:
            logger.error("Error searching conversation chunks: %s", e)
            return Response(
                {"success": False, "error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
