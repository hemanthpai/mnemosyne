import logging
import uuid
from typing import Any, Dict, List, Optional

from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
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
        user_id: Optional[str] = None,
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


# Global instance
vector_service = VectorService()
