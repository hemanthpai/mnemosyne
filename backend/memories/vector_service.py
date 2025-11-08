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
        embedding: List[float],
        user_id: str,
        metadata: Dict[str, Any],
    ) -> str:
        """
        Store embedding in Qdrant and return vector ID

        Phase 1: Stores conversation turn embeddings

        Args:
            embedding: Vector embedding
            user_id: UUID of the user
            metadata: Additional metadata to store (should include turn_id, session_id, etc.)

        Returns:
            Vector ID (UUID string)
        """
        try:
            vector_id = str(uuid.uuid4())

            point = PointStruct(
                id=vector_id,
                vector=embedding,
                payload={
                    "user_id": user_id,
                    **metadata,
                },
            )

            self.client.upsert(collection_name=self.collection_name, points=[point])

            logger.debug(
                "Stored embedding for user %s with vector ID %s", user_id, vector_id
            )
            return vector_id

        except Exception as e:
            logger.error("Failed to store embedding for user %s: %s", user_id, e)
            raise

    def search_similar(
        self,
        embedding: List[float],
        user_id: str,
        limit: int = 10,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar embeddings

        Phase 1: Returns conversation turn metadata

        Args:
            embedding: Query vector (renamed from query_embedding for consistency)
            user_id: Filter by user ID
            limit: Maximum number of results
            score_threshold: Minimum similarity score

        Returns:
            List of search results with metadata, score, and vector_id
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
                query_vector=embedding,
                limit=limit,
                query_filter=search_filter,
                score_threshold=score_threshold,
            )

            search_results = []
            for hit in results:
                search_results.append(
                    {
                        "metadata": hit.payload if hit.payload else {},
                        "score": hit.score,
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
