import json
import logging
import uuid
from datetime import datetime

from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from settings_app.models import LLMSettings

from .llm_service import MEMORY_EXTRACTION_FORMAT, MEMORY_SEARCH_FORMAT, llm_service
from .memory_search_service import memory_search_service
from .models import Memory
from .rate_limiter import rate_limit_extract, rate_limit_retrieve
from .serializers import MemorySerializer
from .vector_service import vector_service

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
    
    Supports field selection to optimize response size:
    - fields: Array of field names to include in response (default: ["id", "content"])
    
    Available fields: id, content, metadata, created_at, updated_at
    """

    @rate_limit_extract
    def post(self, request):
        conversation_text = request.data.get("conversation_text", "")
        user_id = request.data.get("user_id")

        if not conversation_text:
            return Response(
                {"success": False, "error": "conversation_text is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Add reasonable content length limit for DIY systems
        if len(conversation_text) > 50000:  # ~50KB limit
            return Response(
                {
                    "success": False, 
                    "error": "Conversation text is too long. Please break it into smaller chunks.",
                    "max_length": 50000,
                    "current_length": len(conversation_text)
                },
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
            # Refresh LLM settings to ensure we have the latest configuration
            llm_service.refresh_settings()
            
            # Get LLM settings for the extraction prompt
            settings = LLMSettings.get_settings()
            system_prompt = settings.memory_extraction_prompt

            logger.info("Extracting memories for user %s", user_id)

            # Add the current datetime to system prompt for time awareness
            # Add current timestamp to system prompt for context
            try:
                now = datetime.now()
                system_prompt_with_date = f"{system_prompt}\n\nCurrent date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}"
            except Exception as e:
                logger.warning("Could not add date to system prompt: %s", e)
                system_prompt_with_date = system_prompt

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

                # Simple fallback - return helpful error message
                logger.error("Failed to parse LLM response as JSON: %s", e)
                logger.debug("Invalid LLM response: %s", llm_result.get("response", "")[:500])
                
                return Response(
                    {
                        "success": False,
                        "error": "The AI model returned an invalid response format. This usually means the model is overloaded or the prompt was too complex. Please try again with a shorter message.",
                        "memories_extracted": 0,
                        "suggestion": "If this continues to happen, check your LLM service configuration or try a different model."
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Store extracted memories
            stored_memories = []
            for memory_data in memories_data:
                if not isinstance(memory_data, dict):
                    continue

                content = memory_data.get("content", "")
                if not content:
                    continue

                # Prepare metadata
                metadata = {
                    "tags": memory_data.get("tags", []),
                    "extraction_source": "conversation",
                    "model_used": llm_result.get("model", "unknown"),
                }

                memory = memory_search_service.store_memory_with_embedding(
                    content=content, user_id=user_id, metadata=metadata
                )

                # Format memory based on requested fields (default to minimal for efficiency)
                fields = request.data.get("fields", ["id", "content"])
                memory_data = {}
                
                if "id" in fields:
                    memory_data["id"] = str(memory.id)
                if "content" in fields:
                    memory_data["content"] = memory.content
                if "metadata" in fields:
                    memory_data["metadata"] = memory.metadata
                if "created_at" in fields:
                    memory_data["created_at"] = memory.created_at.isoformat()
                if "updated_at" in fields:
                    memory_data["updated_at"] = memory.updated_at.isoformat()
                
                stored_memories.append(memory_data)

            logger.info(
                "Successfully extracted and stored %d memories", len(stored_memories)
            )

            return Response(
                {
                    "success": True,
                    "memories_extracted": len(stored_memories),
                    "memories": stored_memories,
                    "model_used": llm_result.get("model", "unknown"),
                }
            )

        except Exception as e:
            logger.error("Unexpected error during memory extraction: %s", e)
            return Response(
                {
                    "success": False,
                    "error": "Failed to extract memories. This could be due to an LLM service issue, database problem, or vector storage failure.",
                    "memories_extracted": 0,
                    "suggestion": "Check if your LLM service (Ollama) and vector database (Qdrant) are running properly."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RetrieveMemoriesView(APIView):
    """
    API endpoint to retrieve relevant memories for a prompt using vector search
    
    Supports response optimization options:
    - fields: Array of field names to include (default: ["id", "content"])  
    - include_search_metadata: Whether to include search scoring info (default: false)
    - include_summary: Whether to generate memory summary (default: false, saves LLM calls)
    
    Available fields: id, content, metadata, created_at, updated_at
    """

    def _format_memory(self, memory, fields, include_search_metadata=False):
        """Format a single memory with specified fields"""
        memory_data = {}
        
        # Include only requested fields
        if "id" in fields:
            memory_data["id"] = str(memory.id)
        if "content" in fields:
            memory_data["content"] = memory.content
        if "metadata" in fields:
            memory_data["metadata"] = memory.metadata
        if "created_at" in fields:
            memory_data["created_at"] = memory.created_at.isoformat()
        if "updated_at" in fields:
            memory_data["updated_at"] = memory.updated_at.isoformat()
        
        # Add search metadata if requested and available
        if include_search_metadata and hasattr(memory, '_search_score'):
            memory_data["search_metadata"] = {
                "search_score": round(memory._search_score, 3),
                "search_type": memory._search_type,
                "original_score": round(memory._original_score, 3),
                "query_confidence": round(memory._query_confidence, 3),
            }
        
        return memory_data

    @rate_limit_retrieve
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
        
        # Add reasonable prompt length limit
        if len(prompt) > 5000:  # ~5KB limit for search prompts
            return Response(
                {
                    "success": False, 
                    "error": "Search prompt is too long. Please use a shorter, more focused query.",
                    "max_length": 5000,
                    "current_length": len(prompt)
                },
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
            # Refresh LLM settings to ensure we have the latest configuration
            llm_service.refresh_settings()
            
            # Step 1: Get LLM settings and generate search queries
            settings = LLMSettings.get_settings()
            search_prompt = settings.memory_search_prompt

            logger.info(
                "Generating search queries for user %s with prompt: %s...",
                user_id,
                prompt,
            )

            # Query LLM to generate search queries
            logger.info("About to generate search queries with user prompt: %s", prompt)
            logger.info("Using search system prompt length: %d characters", len(search_prompt))
            
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
                search_queries = [{"search_query": prompt, "search_type": "direct"}]

            logger.info("Generated %d search queries", len(search_queries))

            # Step 3: Use memory search service to find relevant memories
            relevant_memories = memory_search_service.search_memories_with_queries(
                search_queries=search_queries,
                user_id=user_id,
                limit=limit,
                threshold=threshold,
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

            # Step 5: Generate memory summary for AI assistance (optional)
            memory_summary = None
            include_summary = request.data.get("include_summary", False)
            if relevant_memories and include_summary:
                logger.info("Generating memory summary...")
                memory_summary = memory_search_service.summarize_relevant_memories(
                    memories=relevant_memories, user_query=prompt
                )
                logger.info("Memory summary generated successfully")

            # Step 6: Format memories for response with field selection
            # Default to minimal fields for efficiency - can reduce response size by 60-80%
            fields = request.data.get("fields", ["id", "content"])  
            include_search_metadata = request.data.get("include_search_metadata", False)
            
            formatted_memories = []
            for memory in relevant_memories:
                memory_data = self._format_memory(memory, fields, include_search_metadata)
                formatted_memories.append(memory_data)

            logger.info("Found %d relevant memories", len(formatted_memories))

            return Response(
                {
                    "success": True,
                    "memories": formatted_memories,
                    "memory_summary": memory_summary,  # Add the summary
                    "count": len(formatted_memories),
                    "search_queries_generated": len(search_queries),
                    "model_used": llm_result.get("model", "unknown"),
                    "query_params": {
                        "limit": limit,
                        "threshold": threshold,
                    },
                    "debug_info": {
                        "quality_filtering_applied": True,
                        "improved_summarization": True,
                        "raw_memory_count_before_filtering": len(relevant_memories) if 'relevant_memories' in locals() else 0
                    }
                }
            )

        except Exception as e:
            logger.error("Unexpected error during memory retrieval: %s", e)
            return Response(
                {
                    "success": False,
                    "error": "Failed to retrieve memories. This could be due to an LLM service issue, vector database problem, or database connectivity issue.",
                    "memories": [],
                    "suggestion": "Check if your LLM service (Ollama) and vector database (Qdrant) are running and accessible."
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

            # Count tags by category
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
                    "domain_distribution": domain_tags,
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
