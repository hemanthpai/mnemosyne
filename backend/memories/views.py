import json
import logging
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import QuerySet
from rest_framework import parsers, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from settings_app.models import LLMSettings

from .llm_service import MEMORY_EXTRACTION_FORMAT, MEMORY_SEARCH_FORMAT, llm_service
from .memory_search_service import memory_search_service
from .models import Memory
from .openwebui_importer import (
    ImportProgress,
    OpenWebUIImporter,
    _import_progresses,
    _progress_lock,
)
from .rate_limiter import rate_limit_extract, rate_limit_retrieve
from .serializers import MemorySerializer
from .vector_service import vector_service

logger = logging.getLogger(__name__)

# API-P2-05 fix: Extract magic numbers as named constants
MAX_CONVERSATION_TEXT_LENGTH = 50000  # Maximum characters for extraction text (~50KB)
MAX_PROMPT_LENGTH = 5000  # Maximum characters for search prompts (~5KB)
EXTRACTION_MAX_TOKENS = 16384  # Token limit for LLM memory extraction
ERROR_MESSAGE_TRUNCATE_LENGTH = 500  # Truncate error messages for logging
DEFAULT_RETRIEVAL_LIMIT = 99  # Default number of memories to retrieve
MAX_RETRIEVAL_LIMIT = 100  # Maximum allowed retrieval limit
DEFAULT_CLAMPED_LIMIT = 10  # Default when invalid limit provided
DEFAULT_IMPORT_BATCH_SIZE = 10  # Default batch size for imports


class MemoryPagination(PageNumberPagination):
    """
    API-P1-01 fix: Pagination for memory list endpoint.

    Prevents performance issues with large datasets by limiting
    results per page and providing navigation links.
    """
    page_size = 50  # Default page size
    page_size_query_param = 'page_size'  # Allow client to override
    max_page_size = 1000  # Maximum allowed page size


# API-P1-06 fix: Whitelist of allowed fields for field selection
ALLOWED_MEMORY_FIELDS = {"id", "content", "metadata", "created_at", "updated_at"}


def validate_fields(requested_fields: Any) -> List[str]:
    """
    Validate requested fields against whitelist.

    API-P1-06 fix: Prevents users from requesting invalid fields
    that could cause errors or expose internal data.
    API-P2-06 fix: Added type hints for better IDE support and type safety.

    Args:
        requested_fields: List of field names to validate (or any type, will be validated)

    Returns:
        list: Validated fields (only allowed ones)
    """
    if not isinstance(requested_fields, list):
        return ["id", "content"]  # Default safe fields

    # Filter to only allowed fields
    validated = [field for field in requested_fields if field in ALLOWED_MEMORY_FIELDS]

    # If no valid fields requested, return defaults
    return validated if validated else ["id", "content"]


class MemoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CRUD operations on memories with pagination support.

    API-P1-01: Implements pagination to prevent performance issues.
    """

    serializer_class = MemorySerializer
    queryset = Memory.objects.all()
    pagination_class = MemoryPagination

    def get_queryset(self) -> QuerySet[Memory]:
        """
        Filter memories by user_id if provided in query params

        API-P2-06 fix: Added type hints for better IDE support and type safety.

        Returns:
            QuerySet of Memory objects, filtered by user_id if provided
        """
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
        """
        Get a specific memory by ID.

        API-P1-03/04: Improved exception handling with logging.
        """
        try:
            # Validate UUID format
            uuid.UUID(pk)
            memory = self.get_object()
            serializer = self.get_serializer(memory)
            return Response(serializer.data)
        except ValueError as e:
            # API-P1-03: Log specific error but return generic message
            logger.debug(f"Invalid UUID format for memory retrieval: {pk} - {e}")
            return Response(
                {"success": False, "error": "Invalid memory ID format"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Memory.DoesNotExist as e:
            # API-P1-03: Log specific error
            logger.debug(f"Memory not found: {pk} - {e}")
            return Response(
                {"success": False, "error": "Memory not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            # API-P1-03: Log unexpected errors but don't expose details to user
            # API-P1-04: Prevent information disclosure
            logger.error(f"Unexpected error retrieving memory {pk}: {e}", exc_info=True)
            return Response(
                {"success": False, "error": "An error occurred while retrieving the memory"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def list(self, request, *args, **kwargs):
        """
        List memories with optional user_id filtering and pagination.

        API-P1-01: Returns paginated results with navigation links.
        """
        queryset = self.get_queryset()

        # Paginate the queryset
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            # get_paginated_response adds 'count', 'next', 'previous' links
            return self.get_paginated_response(serializer.data)

        # Fallback if pagination is disabled
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
        if len(conversation_text) > MAX_CONVERSATION_TEXT_LENGTH:
            return Response(
                {
                    "success": False,
                    "error": "Conversation text is too long. Please break it into smaller chunks.",
                    "max_length": MAX_CONVERSATION_TEXT_LENGTH,
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

            # API-P2-02 fix: Use cached settings from llm_service instead of fetching again
            system_prompt = llm_service.settings.memory_extraction_prompt

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
                max_tokens=EXTRACTION_MAX_TOKENS,
            )

            if not llm_result["success"]:
                # API-P1-03: Log detailed error
                # API-P1-04: Don't expose internal LLM error details to user
                logger.error("LLM extraction failed: %s", llm_result.get("error", "Unknown error"))
                return Response(
                    {
                        "success": False,
                        "error": "Memory extraction failed. Please check if the LLM service is available and try again.",
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
                # API-P2-10 fix: Removed duplicate logging
                logger.error("Failed to parse LLM response as JSON: %s", e)
                logger.debug(
                    "LLM response length: %d chars, preview: %s...",
                    len(llm_result.get("response", "")),
                    llm_result.get("response", "")[:ERROR_MESSAGE_TRUNCATE_LENGTH]
                )

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
                # API-P1-06: Validate fields against whitelist
                requested_fields = request.data.get("fields", ["id", "content"])
                fields = validate_fields(requested_fields)
                # API-P2-03 fix: Rename to avoid shadowing loop variable
                response_memory = {}

                if "id" in fields:
                    response_memory["id"] = str(memory.id)
                if "content" in fields:
                    response_memory["content"] = memory.content
                if "metadata" in fields:
                    response_memory["metadata"] = memory.metadata
                if "created_at" in fields:
                    response_memory["created_at"] = memory.created_at.isoformat()
                if "updated_at" in fields:
                    response_memory["updated_at"] = memory.updated_at.isoformat()

                stored_memories.append(response_memory)

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
            # API-P1-03: Log full exception with stack trace
            # API-P1-04: Return generic error message to prevent information disclosure
            logger.error("Unexpected error during memory extraction: %s", e, exc_info=True)
            return Response(
                {
                    "success": False,
                    "error": "An unexpected error occurred during memory extraction. Please try again later.",
                    "memories_extracted": 0,
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

    def _format_memory(
        self,
        memory: Memory,
        fields: List[str],
        include_search_metadata: bool = False
    ) -> Dict[str, Any]:
        """
        Format a single memory with specified fields

        API-P2-06 fix: Added type hints for better IDE support and type safety.

        Args:
            memory: Memory instance to format
            fields: List of field names to include in response
            include_search_metadata: Whether to include search scoring information

        Returns:
            dict: Formatted memory data with requested fields
        """
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
        limit = request.data.get("limit", DEFAULT_RETRIEVAL_LIMIT)
        threshold = request.data.get("threshold", 0.7)
        boosted_threshold = request.data.get("boosted_threshold", 0.5)

        if not prompt:
            return Response(
                {"success": False, "error": "prompt is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Add reasonable prompt length limit
        if len(prompt) > MAX_PROMPT_LENGTH:
            return Response(
                {
                    "success": False,
                    "error": "Search prompt is too long. Please use a shorter, more focused query.",
                    "max_length": MAX_PROMPT_LENGTH,
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

        # API-P2-14 fix: Validate limit and threshold with logging
        try:
            limit = int(limit)
            if limit <= 0 or limit > MAX_RETRIEVAL_LIMIT:
                logger.warning(f"Invalid limit value {limit}, clamping to default {DEFAULT_CLAMPED_LIMIT}")
                limit = DEFAULT_CLAMPED_LIMIT
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid limit format: {e}, using default {DEFAULT_CLAMPED_LIMIT}")
            limit = DEFAULT_CLAMPED_LIMIT

        try:
            threshold = float(threshold)
            if threshold < 0.0 or threshold > 1.0:
                logger.warning(f"Invalid threshold value {threshold}, clamping to default 0.7")
                threshold = 0.7
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid threshold format: {e}, using default 0.7")
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

            # API-P2-02 fix: Use cached settings from llm_service instead of fetching again
            search_prompt = llm_service.settings.memory_search_prompt

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
                # API-P1-03: Log detailed error
                # API-P1-04: Don't expose internal LLM error details to user
                logger.error(
                    "Failed to generate search queries: %s", llm_result.get("error", "Unknown error")
                )
                return Response(
                    {
                        "success": False,
                        "error": "Search query generation failed. Please check if the LLM service is available and try again.",
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
            # API-P1-06: Validate fields against whitelist
            requested_fields = request.data.get("fields", ["id", "content"])
            fields = validate_fields(requested_fields)
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
                        # API-P2-11 fix: relevant_memories is always defined here
                        "raw_memory_count_before_filtering": len(relevant_memories)
                    }
                }
            )

        except Exception as e:
            # API-P1-03: Log full exception with stack trace
            # API-P1-04: Return generic error message to prevent information disclosure
            logger.error("Unexpected error during memory retrieval: %s", e, exc_info=True)
            return Response(
                {
                    "success": False,
                    "error": "An unexpected error occurred during memory retrieval. Please try again later.",
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

            # API-P2-07 fix: Moved import to module level
            # Test vector service
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
            # API-P1-02: Optimize query to fetch only needed field
            # Use .only() to fetch only metadata field, reducing memory usage
            memories = Memory.objects.filter(user_id=user_id).only('metadata')

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

            # API-P2-07 fix: Moved import to module level
            # Get vector service stats
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
            # API-P1-03: Log detailed error
            # API-P1-04: Return generic error
            logger.error("Error getting memory stats: %s", e, exc_info=True)
            return Response(
                {"success": False, "error": "An error occurred while retrieving memory statistics"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DeleteAllMemoriesView(APIView):
    """Delete all memories for a user or all users"""

    def delete(self, request):
        # API-P2-09 fix: Use query parameters instead of request body
        # DELETE requests don't reliably support request bodies in all HTTP clients
        user_id = request.query_params.get("user_id") or request.data.get("user_id")
        confirm_param = request.query_params.get("confirm") or request.data.get("confirm", False)

        # Parse confirm parameter (could be string or boolean)
        if isinstance(confirm_param, str):
            confirm = confirm_param.lower() in ('true', '1', 'yes')
        else:
            confirm = bool(confirm_param)

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

                # API-P2-01 fix: Use values_list to fetch only IDs, not full objects
                # This is much more efficient for large datasets
                memory_ids = list(
                    memories_to_delete.values_list('id', flat=True)
                )
                memory_ids_str = [str(mid) for mid in memory_ids]

                vector_delete_result = vector_service.delete_memories(
                    memory_ids_str, user_id
                )

                if not vector_delete_result["success"]:
                    # API-P1-03/04: Log detailed error but return generic message
                    logger.error(
                        f"Failed to delete vectors for user {user_id}: {vector_delete_result.get('error', 'Unknown error')}"
                    )
                    return Response(
                        {
                            "success": False,
                            "error": "Failed to delete memories from vector database.",
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                # API-P1-05: Use transaction for database delete
                # If this fails, at least the failure is atomic
                try:
                    with transaction.atomic():
                        # Delete from main database within transaction
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
                except Exception as e:
                    # API-P1-03: Log detailed error
                    # API-P1-04: Return generic error
                    logger.error(f"Failed to delete memories from database for user {user_id}: {e}", exc_info=True)
                    return Response(
                        {
                            "success": False,
                            "error": "Failed to delete memories from database. Vector database may have orphaned entries.",
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
                    # API-P1-03/04: Log detailed error but return generic message
                    logger.error(
                        f"Failed to clear vector database: {vector_clear_result.get('error', 'Unknown error')}"
                    )
                    return Response(
                        {
                            "success": False,
                            "error": "Failed to clear vector database.",
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                # API-P1-05: Use transaction for database delete
                try:
                    with transaction.atomic():
                        # Delete all memories from main database within transaction
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
                    # API-P1-03: Log detailed error
                    # API-P1-04: Return generic error
                    logger.error(f"Failed to delete all memories from database: {e}", exc_info=True)
                    return Response(
                        {
                            "success": False,
                            "error": "Failed to delete memories from database. Vector database may have orphaned entries.",
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

        except Exception as e:
            # API-P1-03: Log detailed error with stack trace
            # API-P1-04: Return generic error to prevent information disclosure
            logger.error(f"Error deleting memories: {e}", exc_info=True)
            return Response(
                {"success": False, "error": "An unexpected error occurred while deleting memories"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ImportOpenWebUIHistoryView(APIView):
    """Import historical conversations from Open WebUI database"""

    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request):
        """
        Start import process from uploaded database file

        Request body:
        - db_file: Uploaded SQLite database file (multipart/form-data)
        - target_user_id: (optional) Mnemosyne user ID to assign all memories
        - openwebui_user_id: (optional) Filter by Open WebUI user
        - after_date: (optional) Only import after this date (ISO format)
        - batch_size: (optional) Batch processing size (default: 10)
        - limit: (optional) Maximum conversations to import
        - dry_run: (optional) Preview mode (default: false)
        """
        # API-P2-07 fix: Moved imports to module level

        try:
            # Get uploaded file
            if 'db_file' not in request.FILES:
                return Response(
                    {"success": False, "error": "No database file uploaded"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            db_file = request.FILES['db_file']

            # Validate file extension
            if not db_file.name.endswith('.db'):
                return Response(
                    {"success": False, "error": "File must be a .db SQLite database"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate file size
            settings = LLMSettings.get_settings()
            max_size_bytes = settings.max_import_file_size_mb * 1024 * 1024

            if db_file.size > max_size_bytes:
                return Response(
                    {
                        "success": False,
                        "error": f"Database file too large. Maximum size is {settings.max_import_file_size_mb}MB",
                        "file_size_mb": round(db_file.size / (1024 * 1024), 2),
                        "max_size_mb": settings.max_import_file_size_mb
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get and validate optional parameters BEFORE creating temp file
            # API-P2-12 fix: Validate all parameters before creating temp file
            # to prevent file leak on early returns
            target_user_id = request.data.get('target_user_id')
            openwebui_user_id = request.data.get('openwebui_user_id')
            after_date_str = request.data.get('after_date')

            # API-P2-04 fix: Proper boolean parsing instead of string comparison
            dry_run_value = request.data.get('dry_run', False)
            if isinstance(dry_run_value, bool):
                dry_run = dry_run_value
            elif isinstance(dry_run_value, str):
                dry_run = dry_run_value.lower() in ('true', '1', 'yes')
            else:
                dry_run = bool(dry_run_value)

            # Validate and clamp batch_size
            try:
                batch_size = int(request.data.get('batch_size', DEFAULT_IMPORT_BATCH_SIZE))
                batch_size = max(1, min(MAX_RETRIEVAL_LIMIT, batch_size))  # Clamp to 1-100
            except (ValueError, TypeError):
                return Response(
                    {"success": False, "error": f"Invalid batch_size. Must be an integer between 1-{MAX_RETRIEVAL_LIMIT}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate limit
            limit = request.data.get('limit')
            if limit:
                try:
                    limit = int(limit)
                    if limit < 1:
                        return Response(
                            {"success": False, "error": "Limit must be a positive integer."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                except (ValueError, TypeError):
                    return Response(
                        {"success": False, "error": "Invalid limit. Must be a positive integer."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Parse after_date if provided
            after_date = None
            if after_date_str:
                try:
                    # API-P2-07 fix: Moved import to module level
                    # Parse date string and treat as start of day in UTC
                    # This ensures consistent filtering regardless of user's timezone
                    date_obj = datetime.fromisoformat(after_date_str.replace('Z', '')).date()
                    after_date = datetime.combine(date_obj, datetime.min.time()).replace(tzinfo=timezone.utc)
                except ValueError:
                    return Response(
                        {"success": False, "error": "Invalid date format. Use ISO format (YYYY-MM-DD)"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Validate target_user_id if provided
            if target_user_id:
                try:
                    uuid.UUID(target_user_id)
                except ValueError:
                    return Response(
                        {"success": False, "error": "Invalid target_user_id format. Must be UUID."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # API-P2-13 fix: Generate unique import_id BEFORE starting thread
            # to prevent race condition in progress initialization
            import_id = str(uuid.uuid4())

            # API-P2-12 fix: Only create temp file AFTER all validations pass
            # This prevents file leaks from early returns during validation
            with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
                for chunk in db_file.chunks():
                    tmp_file.write(chunk)
                tmp_path = tmp_file.name

            # Run import in background thread
            def run_import():
                import_thread_id = threading.current_thread().ident
                logger.info(f"[Thread {import_thread_id}] Starting import in background...")

                # Track if temp file was created successfully
                temp_file_created = Path(tmp_path).exists()

                try:
                    try:
                        with OpenWebUIImporter(tmp_path) as importer:
                            result = importer.import_conversations(
                                import_id=import_id,  # API-P2-13 fix: Pass import_id
                                target_user_id=target_user_id,
                                openwebui_user_id=openwebui_user_id,
                                after_date=after_date,
                                batch_size=batch_size,
                                limit=limit,
                                dry_run=dry_run,
                            )
                            logger.info(f"[Thread {import_thread_id}] Import completed successfully: {result}")
                    except Exception as e:
                        logger.error(f"[Thread {import_thread_id}] Import failed in background: {e}", exc_info=True)
                finally:
                    # Always cleanup temp file if it exists
                    if temp_file_created or Path(tmp_path).exists():
                        try:
                            Path(tmp_path).unlink(missing_ok=True)
                            logger.info(f"[Thread {import_thread_id}] Cleaned up temp file: {tmp_path}")
                        except Exception as e:
                            logger.error(f"[Thread {import_thread_id}] Failed to delete temp file: {e}")
                    logger.info(f"[Thread {import_thread_id}] Background import thread exiting")

            # API-P2-13 fix: Initialize progress state BEFORE starting thread
            # to prevent race condition. Use _import_progresses dict with import_id.
            # API-P2-07 fix: Moved import to module level
            with _progress_lock:
                if import_id not in _import_progresses:
                    _import_progresses[import_id] = ImportProgress()
                progress = _import_progresses[import_id]
                progress.status = "initializing"
                progress.start_time = datetime.now()
                progress.end_time = None
                progress.dry_run = dry_run
                progress.error_message = None
                progress.current_conversation_id = None
                progress.total_conversations = 0
                progress.processed_conversations = 0
                progress.extracted_memories = 0
                progress.failed_conversations = 0

            # Start import thread
            import_thread = threading.Thread(target=run_import, daemon=True)
            import_thread.start()

            return Response(
                {
                    "success": True,
                    "message": "Import started successfully",
                    "import_id": import_id,  # API-P2-13 fix: Return import_id for progress tracking
                    "dry_run": dry_run,
                }
            )

        except Exception as e:
            logger.error(f"Error starting import: {e}")
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ImportProgressView(APIView):
    """Get current import progress"""

    def get(self, request):
        try:
            # API-P2-07 fix: Moved import to module level
            progress = OpenWebUIImporter.get_progress()

            return Response(
                {
                    "success": True,
                    "progress": progress,
                }
            )
        except Exception as e:
            logger.error(f"Error getting import progress: {e}")
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CancelImportView(APIView):
    """Cancel ongoing import"""

    def post(self, request):
        try:
            # API-P2-07 fix: Moved import to module level
            OpenWebUIImporter.cancel_import()

            return Response(
                {
                    "success": True,
                    "message": "Import cancellation requested",
                }
            )
        except Exception as e:
            logger.error(f"Error cancelling import: {e}")
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
