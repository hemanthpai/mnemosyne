import logging
import uuid
from typing import Any, Dict, List

from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

logger = logging.getLogger(__name__)


class VectorService:
    """Service for managing embeddings in Qdrant vector database"""

    def __init__(self):
        self.collection_name = getattr(settings, "QDRANT_COLLECTION_NAME", "memories")
        self._connect()

    def _connect(self):
        """Initialize Qdrant client connection"""
        try:
            host = getattr(settings, "QDRANT_HOST", "localhost")
            port = getattr(settings, "QDRANT_PORT", 6333)
            api_key = getattr(settings, "QDRANT_API_KEY", None)

            if api_key:
                self.client = QdrantClient(host=host, port=port, api_key=api_key)
            else:
                self.client = QdrantClient(host=host, port=port)

            logger.info("Connected to Qdrant at %s:%s", host, port)
            self._ensure_collection()

        except Exception as e:
            logger.error("Failed to connect to Qdrant: %s", e)
            raise

    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]

            if self.collection_name not in collection_names:
                logger.info("Creating Qdrant collection: %s", self.collection_name)
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=1024,  # Default for OpenAI embeddings - adjust based on your model
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("Collection %s created successfully", self.collection_name)
            else:
                logger.info("Collection %s already exists", self.collection_name)

        except Exception as e:
            logger.error("Failed to ensure collection exists: %s", e)
            raise

    def store_embedding(
        self,
        memory_id: str,
        embedding: List[float],
        user_id: str,
        metadata: Dict[str, Any],
    ) -> str:
        """
        Store embedding in Qdrant and return vector ID
        
        DEPRECATED: Use store_conversation_chunk_embedding() for new conversation-based architecture

        Args:
            memory_id: UUID of the memory record
            embedding: Vector embedding
            user_id: UUID of the user
            metadata: Additional metadata to store

        Returns:
            Vector ID (UUID string)
        """
        try:
            vector_id = str(uuid.uuid4())

            point = PointStruct(
                id=vector_id,
                vector=embedding,
                payload={
                    "memory_id": memory_id,
                    "user_id": user_id,
                    "created_at": metadata.get("created_at"),
                    "content_type": "memory",  # Mark as legacy memory content
                    **metadata,
                },
            )

            self.client.upsert(collection_name=self.collection_name, points=[point])

            logger.debug(
                "Stored embedding for memory %s with vector ID %s", memory_id, vector_id
            )
            return vector_id

        except Exception as e:
            logger.error("Failed to store embedding for memory %s: %s", memory_id, e)
            raise

    def store_conversation_chunk_embedding(
        self,
        chunk_id: str,
        embedding: List[float],
        user_id: str,
        timestamp: str,
        metadata: Dict[str, Any],
    ) -> str:
        """
        Store conversation chunk embedding in Qdrant and return vector ID

        Args:
            chunk_id: UUID of the ConversationChunk record
            embedding: Vector embedding of conversation text
            user_id: UUID of the user
            timestamp: ISO timestamp of when conversation occurred
            metadata: Additional metadata to store

        Returns:
            Vector ID (UUID string)
        """
        try:
            vector_id = str(uuid.uuid4())

            point = PointStruct(
                id=vector_id,
                vector=embedding,
                payload={
                    "chunk_id": chunk_id,
                    "user_id": user_id,
                    "timestamp": timestamp,
                    "content_type": "conversation",
                    **metadata,
                },
            )

            self.client.upsert(collection_name=self.collection_name, points=[point])

            logger.debug(
                "Stored conversation chunk embedding for chunk %s with vector ID %s", chunk_id, vector_id
            )
            return vector_id

        except Exception as e:
            logger.error("Failed to store conversation chunk embedding for chunk %s: %s", chunk_id, e)
            raise

    def search_similar(
        self,
        query_embedding: List[float],
        user_id: str,
        limit: int = 10,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar embeddings

        Args:
            query_embedding: Query vector
            user_id: Filter by user ID (optional)
            limit: Maximum number of results
            score_threshold: Minimum similarity score

        Returns:
            List of search results with memory_id, score, and payload
        """
        logger.info(
            "Searching for similar embeddings for user %s with limit %d",
            user_id,
            limit,
        )
        try:
            # Build filter for user_id if provided
            search_filter = None
            if user_id:
                search_filter = Filter(
                    must=[
                        FieldCondition(key="user_id", match=MatchValue(value=user_id))
                    ]
                )

            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                query_filter=search_filter,
                score_threshold=score_threshold,
            )

            search_results = []
            for hit in results:
                # Handle both legacy memory_id and new chunk_id formats
                memory_id = (
                    hit.payload.get("memory_id")
                    if hit.payload and "memory_id" in hit.payload
                    else None
                )
                chunk_id = (
                    hit.payload.get("chunk_id")
                    if hit.payload and "chunk_id" in hit.payload
                    else None
                )
                search_results.append(
                    {
                        "memory_id": memory_id,  # Legacy field for backward compatibility
                        "chunk_id": chunk_id,    # New field for conversation chunks
                        "score": hit.score,
                        "payload": hit.payload,
                        "vector_id": hit.id,
                    }
                )

            logger.debug(
                "Found %d similar embeddings for user %s", len(search_results), user_id
            )
            return search_results

        except Exception as e:
            logger.error("Failed to search similar embeddings: %s", e)
            return []

    def search_conversation_context(
        self,
        query_embedding: List[float],
        user_id: str,
        limit: int = 10,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant conversation chunks using semantic similarity

        Args:
            query_embedding: Query vector
            user_id: Filter by user ID
            limit: Maximum number of results
            score_threshold: Minimum similarity score

        Returns:
            List of search results with chunk_id, score, content, and timestamp
        """
        logger.info(
            "Searching conversation context for user %s with limit %d",
            user_id,
            limit,
        )
        try:
            # Filter for conversation chunks only
            search_filter = Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    FieldCondition(key="content_type", match=MatchValue(value="conversation"))
                ]
            )

            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                query_filter=search_filter,
                score_threshold=score_threshold,
            )

            search_results = []
            for hit in results:
                if hit.payload and "chunk_id" in hit.payload:
                    search_results.append(
                        {
                            "chunk_id": hit.payload["chunk_id"],
                            "score": hit.score,
                            "content": hit.payload.get("content", ""),
                            "timestamp": hit.payload.get("timestamp"),
                            "user_id": hit.payload.get("user_id"),
                            "vector_id": hit.id,
                            "metadata": {k: v for k, v in hit.payload.items() 
                                       if k not in ["chunk_id", "user_id", "content_type", "timestamp"]}
                        }
                    )

            logger.debug(
                "Found %d conversation chunks for user %s", len(search_results), user_id
            )
            return search_results

        except Exception as e:
            logger.error("Failed to search conversation context: %s", e)
            return []

    def chunk_conversation(self, text: str, max_chunk_size: int = 1000, overlap_size: int = 100) -> List[str]:
        """
        Split conversation text into semantic chunks for vector storage
        
        Args:
            text: Original conversation text
            max_chunk_size: Maximum characters per chunk (default 1000)
            overlap_size: Characters to overlap between chunks (default 100)
            
        Returns:
            List of conversation text chunks
        """
        if not text or not text.strip():
            return []
            
        # Clean the text
        text = text.strip()
        
        # If text is smaller than max chunk size, return as single chunk
        if len(text) <= max_chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Calculate end position
            end = start + max_chunk_size
            
            # If this would be the last chunk, include all remaining text
            if end >= len(text):
                chunks.append(text[start:])
                break
            
            # Try to find a good break point (sentence or paragraph boundary)
            # Look backwards from the end position for natural break points
            chunk_text = text[start:end]
            
            # Look for sentence boundaries (. ! ?) followed by space or newline
            sentence_breaks = []
            for i, char in enumerate(chunk_text):
                if char in '.!?' and i < len(chunk_text) - 1:
                    next_char = chunk_text[i + 1]
                    if next_char in ' \n\t':
                        sentence_breaks.append(start + i + 1)
            
            # Look for paragraph breaks (double newlines)
            para_breaks = []
            for i in range(len(chunk_text) - 1):
                if chunk_text[i:i+2] == '\n\n':
                    para_breaks.append(start + i + 2)
            
            # Choose the best break point
            best_break = end
            if para_breaks:
                # Prefer paragraph breaks closest to target end
                best_break = max(para_breaks)
            elif sentence_breaks:
                # Fall back to sentence breaks closest to target end
                best_break = max(sentence_breaks)
            
            # Ensure we don't create tiny chunks
            if best_break - start < max_chunk_size // 2:
                best_break = end
                
            chunks.append(text[start:best_break])
            
            # Move start position with overlap
            start = max(best_break - overlap_size, best_break)
            
        return chunks

    def store_conversation_chunks(
        self, 
        chunks: List[str], 
        user_id: str, 
        timestamp: str,
        base_metadata: Dict[str, Any] = None
    ) -> List[str]:
        """
        Store multiple conversation chunks in vector database
        
        Args:
            chunks: List of conversation text chunks
            user_id: User ID
            timestamp: ISO timestamp when conversation occurred
            base_metadata: Base metadata to include with each chunk
            
        Returns:
            List of vector IDs for stored chunks
        """
        from .llm_service import llm_service
        
        if base_metadata is None:
            base_metadata = {}
            
        vector_ids = []
        
        try:
            # Get embeddings for all chunks at once (more efficient)
            embedding_result = llm_service.get_embeddings(chunks)
            if not embedding_result["success"]:
                logger.error("Failed to generate embeddings for conversation chunks: %s", 
                           embedding_result.get("error"))
                raise ValueError(f"Failed to generate embeddings: {embedding_result.get('error')}")
            
            embeddings = embedding_result["embeddings"]
            
            # Store each chunk with its embedding
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = str(uuid.uuid4())
                
                chunk_metadata = {
                    **base_metadata,
                    "content": chunk,  # Store original text in metadata for search results
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "extraction_timestamp": timestamp
                }
                
                vector_id = self.store_conversation_chunk_embedding(
                    chunk_id=chunk_id,
                    embedding=embedding,
                    user_id=user_id,
                    timestamp=timestamp,
                    metadata=chunk_metadata
                )
                
                vector_ids.append(vector_id)
                logger.debug("Stored conversation chunk %d/%d with vector ID %s", 
                           i + 1, len(chunks), vector_id)
            
            logger.info("Successfully stored %d conversation chunks for user %s", 
                       len(vector_ids), user_id)
            return vector_ids
            
        except Exception as e:
            logger.error("Failed to store conversation chunks: %s", e)
            raise

    def link_memories_to_chunks(self, memory_ids: List[str], chunk_ids: List[str]) -> bool:
        """
        Create bidirectional links between memories and conversation chunks
        
        Args:
            memory_ids: List of Memory IDs that were extracted
            chunk_ids: List of ConversationChunk IDs that led to the extraction
            
        Returns:
            True if linking successful, False otherwise
        """
        try:
            from .models import Memory, ConversationChunk
            
            # Update Memory records with conversation chunk IDs
            for memory_id in memory_ids:
                try:
                    memory = Memory.objects.get(id=memory_id)
                    if not memory.conversation_chunk_ids:
                        memory.conversation_chunk_ids = []
                    
                    # Add new chunk IDs, avoiding duplicates
                    for chunk_id in chunk_ids:
                        if chunk_id not in memory.conversation_chunk_ids:
                            memory.conversation_chunk_ids.append(chunk_id)
                    
                    memory.save()
                    logger.debug("Updated memory %s with chunk IDs %s", memory_id, chunk_ids)
                    
                except Memory.DoesNotExist:
                    logger.warning("Memory %s not found for linking", memory_id)
                    continue
            
            # Update ConversationChunk records with memory IDs
            for chunk_id in chunk_ids:
                try:
                    chunk = ConversationChunk.objects.get(id=chunk_id)
                    if not chunk.extracted_memory_ids:
                        chunk.extracted_memory_ids = []
                    
                    # Add new memory IDs, avoiding duplicates
                    for memory_id in memory_ids:
                        if memory_id not in chunk.extracted_memory_ids:
                            chunk.extracted_memory_ids.append(memory_id)
                    
                    chunk.save()
                    logger.debug("Updated chunk %s with memory IDs %s", chunk_id, memory_ids)
                    
                except ConversationChunk.DoesNotExist:
                    logger.warning("ConversationChunk %s not found for linking", chunk_id)
                    continue
            
            logger.info("Successfully linked %d memories to %d conversation chunks", 
                       len(memory_ids), len(chunk_ids))
            return True
            
        except Exception as e:
            logger.error("Failed to link memories to chunks: %s", e)
            return False

    def find_conversations_for_memory(self, memory_id: str) -> List[Dict[str, Any]]:
        """
        Find conversation chunks that led to a specific memory
        
        Args:
            memory_id: Memory ID to find conversations for
            
        Returns:
            List of conversation chunk data with content and metadata
        """
        try:
            from .models import Memory, ConversationChunk
            
            # Get the memory and its linked chunk IDs
            memory = Memory.objects.get(id=memory_id)
            chunk_ids = memory.conversation_chunk_ids or []
            
            if not chunk_ids:
                return []
            
            # Get the conversation chunks
            chunks = ConversationChunk.objects.filter(id__in=chunk_ids).order_by('timestamp')
            
            chunk_data = []
            for chunk in chunks:
                chunk_data.append({
                    "chunk_id": str(chunk.id),
                    "content": chunk.content,
                    "timestamp": chunk.timestamp.isoformat(),
                    "vector_id": chunk.vector_id,
                    "metadata": chunk.metadata,
                    "extracted_memory_ids": chunk.extracted_memory_ids
                })
            
            logger.debug("Found %d conversation chunks for memory %s", 
                        len(chunk_data), memory_id)
            return chunk_data
            
        except Exception as e:
            logger.error("Failed to find conversations for memory %s: %s", memory_id, e)
            return []

    def find_memories_from_conversation(self, chunk_id: str) -> List[Dict[str, Any]]:
        """
        Find memories that were extracted from a specific conversation chunk
        
        Args:
            chunk_id: ConversationChunk ID to find memories for
            
        Returns:
            List of memory data
        """
        try:
            from .models import Memory, ConversationChunk
            
            # Get the conversation chunk and its linked memory IDs
            chunk = ConversationChunk.objects.get(id=chunk_id)
            memory_ids = chunk.extracted_memory_ids or []
            
            if not memory_ids:
                return []
            
            # Get the memories
            memories = Memory.objects.filter(id__in=memory_ids, is_active=True).order_by('-created_at')
            
            memory_data = []
            for memory in memories:
                memory_data.append({
                    "memory_id": str(memory.id),
                    "content": memory.content,
                    "metadata": memory.get_standardized_metadata(),
                    "fact_type": memory.fact_type,
                    "temporal_confidence": memory.temporal_confidence,
                    "created_at": memory.created_at.isoformat()
                })
            
            logger.debug("Found %d memories from conversation chunk %s", 
                        len(memory_data), chunk_id)
            return memory_data
            
        except Exception as e:
            logger.error("Failed to find memories from conversation %s: %s", chunk_id, e)
            return []

    def delete_embedding(self, vector_id: str) -> bool:
        """Delete embedding by vector ID"""
        try:
            self.client.delete(
                collection_name=self.collection_name, points_selector=[vector_id]
            )
            logger.debug("Deleted embedding with vector ID %s", vector_id)
            return True

        except Exception as e:
            logger.error("Failed to delete embedding %s: %s", vector_id, e)
            return False

    def delete_user_embeddings(self, user_id: str) -> bool:
        """Delete all embeddings for a user"""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(key="user_id", match=MatchValue(value=user_id))
                    ]
                ),
            )
            logger.info("Deleted all embeddings for user %s", user_id)
            return True

        except Exception as e:
            logger.error("Failed to delete embeddings for user %s: %s", user_id, e)
            return False

    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the collection"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                "status": collection_info.status,
                "vector_count": collection_info.config.params.vectors.size,  # type: ignore
                "distance": collection_info.config.params.vectors.distance,  # type: ignore
                "optimizer_status": collection_info.optimizer_status,
                "points_count": collection_info.points_count,
            }
        except Exception as e:
            logger.error("Failed to get collection info: %s", e)
            return {}

    def health_check(self) -> bool:
        """Check if Qdrant is healthy"""
        try:
            collections = self.client.get_collections()
            logger.info("Qdrant health check passed, collections: %s", collections)
            return True
        except Exception as e:
            logger.error("Qdrant health check failed: %s", e)
            return False

    def delete_memories(self, memory_ids: List[str], user_id: str) -> Dict[str, Any]:
        """Delete specific memories from vector database"""
        try:
            # Delete points by memory IDs
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(key="memory_id", match=MatchAny(any=memory_ids)),
                        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    ]
                ),
            )

            logger.info(f"Deleted {len(memory_ids)} vectors for user {user_id}")
            return {"success": True, "deleted_count": len(memory_ids)}

        except Exception as e:
            logger.error(f"Error deleting vectors: {e}")
            return {"success": False, "error": str(e)}

    def clear_all_memories(self) -> Dict[str, Any]:
        """Clear ALL memories from vector database (admin operation)"""
        try:
            # Get collection info to check if it exists
            try:
                collection_info = self.client.get_collection(self.collection_name)
                point_count = collection_info.points_count
            except Exception:
                return {
                    "success": True,
                    "message": "Collection doesn't exist or is already empty",
                }

            if point_count == 0:
                return {"success": True, "message": "Vector database is already empty"}

            # Delete the entire collection and recreate it
            self.client.delete_collection(self.collection_name)
            self._ensure_collection()

            logger.warning(
                f"ADMIN ACTION: Cleared ALL {point_count} vectors from database"
            )
            return {"success": True, "cleared_count": point_count}

        except Exception as e:
            logger.error(f"Error clearing vector database: {e}")
            return {"success": False, "error": str(e)}

    def delete_user_memories(self, user_id: str) -> Dict[str, Any]:
        """Delete all memories for a specific user from vector database"""
        try:
            # Delete all points for this user
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(key="user_id", match=MatchValue(value=user_id))
                    ]
                ),
            )

            logger.info(f"Deleted all vectors for user {user_id}")
            return {"success": True}

        except Exception as e:
            logger.error(f"Error deleting user vectors: {e}")
            return {"success": False, "error": str(e)}


# Global instance
vector_service = VectorService()
