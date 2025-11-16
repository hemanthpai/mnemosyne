import logging
import time
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
        self.client = None
        self._connected = False
        self._connection_attempts = 0
        self._last_connection_attempt = 0

    def _connect(self):
        """
        Initialize Qdrant client connection.
        Returns True if successful, False otherwise.
        Does not raise exceptions - allows graceful degradation.
        """
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
            self._connected = True
            return True

        except Exception as e:
            logger.warning("Failed to connect to Qdrant: %s", e)
            self._connected = False
            return False

    def _ensure_connection(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Ensure connection to Qdrant is established with retry logic.

        Args:
            max_retries: Maximum number of connection attempts
            retry_delay: Delay between retries in seconds

        Returns:
            True if connected, False otherwise

        Raises:
            Exception if connection cannot be established after retries
        """
        # Already connected
        if self._connected and self.client is not None:
            return True

        # Avoid hammering the server with connection attempts
        current_time = time.time()
        if current_time - self._last_connection_attempt < 5:
            # Less than 5 seconds since last attempt
            if not self._connected:
                raise Exception("Qdrant connection unavailable (recent connection attempt failed)")
            return False

        self._last_connection_attempt = current_time

        # Try to connect with retries
        for attempt in range(max_retries):
            if attempt > 0:
                sleep_time = retry_delay * (2 ** (attempt - 1))
                logger.info("Retrying Qdrant connection in %.2f seconds...", sleep_time)
                time.sleep(sleep_time)

            logger.info("Attempting to connect to Qdrant (attempt %d/%d)", attempt + 1, max_retries)
            if self._connect():
                self._connection_attempts = 0
                return True

            self._connection_attempts += 1

        # All retries failed
        error_msg = f"Failed to connect to Qdrant after {max_retries} attempts"
        logger.error(error_msg)
        raise Exception(error_msg)

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

        Args:
            memory_id: UUID of the memory record
            embedding: Vector embedding
            user_id: UUID of the user
            metadata: Additional metadata to store

        Returns:
            Vector ID (UUID string)
        """
        self._ensure_connection()

        try:
            vector_id = str(uuid.uuid4())

            point = PointStruct(
                id=vector_id,
                vector=embedding,
                payload={
                    "memory_id": memory_id,
                    "user_id": user_id,
                    "created_at": metadata.get("created_at"),
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
        self._ensure_connection()

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
                memory_id = (
                    hit.payload["memory_id"]
                    if hit.payload and "memory_id" in hit.payload
                    else None
                )
                search_results.append(
                    {
                        "memory_id": memory_id,
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

    def delete_embedding(self, vector_id: str) -> bool:
        """Delete embedding by vector ID"""
        self._ensure_connection()

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
        self._ensure_connection()

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
        self._ensure_connection()

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
        self._ensure_connection()

        try:
            collections = self.client.get_collections()
            logger.info("Qdrant health check passed, collections: %s", collections)
            return True
        except Exception as e:
            logger.error("Qdrant health check failed: %s", e)
            return False

    def delete_memories(self, memory_ids: List[str], user_id: str) -> Dict[str, Any]:
        """Delete specific memories from vector database"""
        self._ensure_connection()

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
        self._ensure_connection()

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
        self._ensure_connection()

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
