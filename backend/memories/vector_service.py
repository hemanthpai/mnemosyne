import logging
import uuid
from typing import Any, Dict, List, Optional

from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchAny,
    MatchValue,
    OptimizersConfigDiff,
    PayloadSchemaType,
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
        """Create collection if it doesn't exist with optimized RAM configuration"""
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]

            if self.collection_name not in collection_names:
                logger.info(
                    "Creating Qdrant collection: %s with RAM optimization",
                    self.collection_name,
                )

                # Get vector size from settings or embedding service
                vector_size = getattr(settings, "EMBEDDING_DIMENSION", 1024)

                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE,
                        # Optimize HNSW for speed
                        hnsw_config=HnswConfigDiff(
                            m=16,  # Number of bi-directional links created for each new element during construction
                            ef_construct=200,  # Size of the dynamic candidate list
                            full_scan_threshold=10000,  # Threshold for switching to full scan
                            max_indexing_threads=0,  # Use all available threads
                            on_disk=False,  # Keep vectors in RAM for fastest access
                        ),
                    ),
                    # Optimize for RAM storage
                    optimizers_config=OptimizersConfigDiff(
                        deleted_threshold=0.2,  # Trigger optimization when 20% of points are deleted
                        vacuum_min_vector_number=1000,  # Minimum vectors before vacuum
                        default_segment_number=0,  # Let Qdrant decide optimal segments
                        max_segment_size=None,  # No limit on segment size
                        memmap_threshold=None,  # Keep everything in RAM
                        indexing_threshold=20000,  # Start indexing after 20k points
                        flush_interval_sec=5,  # Flush to disk every 5 seconds
                        max_optimization_threads=None,  # Use all available threads
                    ),
                    # Set replication factor for performance vs reliability trade-off
                    replication_factor=1,  # Single replica for home server
                    write_consistency_factor=1,  # Faster writes
                )

                # Create indexes for commonly queried fields for faster filtering
                self._create_payload_indexes()

                logger.info(
                    "Collection %s created successfully with RAM optimization",
                    self.collection_name,
                )
            else:
                logger.info("Collection %s already exists", self.collection_name)
                # Optionally update existing collection settings
                self._optimize_existing_collection()

        except Exception as e:
            logger.error("Failed to ensure collection exists: %s", e)
            raise

    def _create_payload_indexes(self):
        """Create indexes on payload fields for faster filtering"""
        try:
            # Index user_id for fast user-specific queries
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="user_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )

            # Index memory_id for fast memory lookups
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="memory_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )

            # Index created_at for temporal queries
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="created_at",
                field_schema=PayloadSchemaType.DATETIME,
            )

            logger.info("Created payload indexes for faster filtering")

        except Exception as e:
            logger.warning("Failed to create some payload indexes: %s", e)

    def _optimize_existing_collection(self):
        """Update existing collection for better performance"""
        try:
            # Update collection configuration if possible
            self.client.update_collection(
                collection_name=self.collection_name,
                optimizers_config=OptimizersConfigDiff(
                    memmap_threshold=None,  # Keep in RAM
                    indexing_threshold=20000,
                    max_optimization_threads=None,
                ),
                hnsw_config=HnswConfigDiff(
                    on_disk=False,  # Move to RAM
                    ef_construct=200,
                    m=16,
                ),
            )
            logger.info("Updated existing collection for RAM optimization")
        except Exception as e:
            logger.warning("Could not update existing collection: %s", e)

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

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get collection performance statistics"""
        try:
            collection_info = self.client.get_collection(self.collection_name)

            # Safely access HNSW config with fallbacks
            hnsw_config = {}
            try:
                if (
                    hasattr(collection_info.config.params.vectors, "hnsw_config")
                    and collection_info.config.params.vectors.hnsw_config  # type: ignore
                ):
                    hnsw_config = {
                        "m": getattr(
                            collection_info.config.params.vectors.hnsw_config,  # type: ignore
                            "m",
                            16,
                        ),
                        "ef_construct": getattr(
                            collection_info.config.params.vectors.hnsw_config,  # type: ignore
                            "ef_construct",
                            100,
                        ),
                        "on_disk": getattr(
                            collection_info.config.params.vectors.hnsw_config,  # type: ignore
                            "on_disk",
                            True,
                        ),
                    }
                else:
                    # Fallback values when hnsw_config is None
                    hnsw_config = {
                        "m": "unknown",
                        "ef_construct": "unknown",
                        "on_disk": "unknown",
                    }
            except (AttributeError, TypeError) as e:
                logger.warning("Could not access HNSW config: %s", e)
                hnsw_config = {
                    "m": "error",
                    "ef_construct": "error",
                    "on_disk": "error",
                }

            return {
                "points_count": collection_info.points_count,
                "segments_count": collection_info.segments_count,
                "status": collection_info.status.value,
                "optimizer_status": collection_info.optimizer_status,
                "vector_size": collection_info.config.params.vectors.size,  # type: ignore
                "distance_function": collection_info.config.params.vectors.distance.value,  # type: ignore
                "hnsw_config": hnsw_config,
                "ram_usage_optimized": hnsw_config.get("on_disk") is False
                if isinstance(hnsw_config.get("on_disk"), bool)
                else False,
            }
        except Exception as e:
            logger.error("Failed to get performance stats: %s", e)
            return {}

    def optimize_collection(self) -> Dict[str, Any]:
        """Trigger manual collection optimization"""
        try:
            # This will optimize the collection structure
            operation_info = self.client.update_collection(
                collection_name=self.collection_name,
                optimizer_config=OptimizersConfigDiff(
                    deleted_threshold=0.2,
                    vacuum_min_vector_number=1000,
                    memmap_threshold=None,  # Keep in RAM
                ),
            )

            logger.info("Triggered collection optimization")
            return {"success": True, "operation_info": operation_info}

        except Exception as e:
            logger.error("Failed to optimize collection: %s", e)
            return {"success": False, "error": str(e)}

    # Add optimized search methods to VectorService

    def search_similar_optimized(
        self,
        query_embedding: List[float],
        user_id: str,
        limit: int = 10,
        score_threshold: float = 0.0,
        ef: Optional[int] = None,  # Search-time parameter for HNSW
    ) -> List[Dict[str, Any]]:
        """
        Optimized search for similar embeddings with custom ef parameter

        Args:
            query_embedding: Query vector
            user_id: Filter by user ID
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            ef: Search-time HNSW parameter (higher = more accurate but slower)

        Returns:
            List of search results with memory_id, score, and payload
        """
        logger.info(
            "Optimized search for user %s with limit %d, ef=%s", user_id, limit, ef
        )

        try:
            # Build filter for user_id
            search_filter = None
            if user_id:
                search_filter = Filter(
                    must=[
                        FieldCondition(key="user_id", match=MatchValue(value=user_id))
                    ]
                )

            # Use search with custom parameters
            search_params = None
            if ef is not None:
                from qdrant_client.models import SearchParams

                search_params = SearchParams(hnsw_ef=ef)  # Use correct parameter name

            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                query_filter=search_filter,
                score_threshold=score_threshold,
                search_params=search_params,
                with_payload=True,
                with_vectors=False,  # Don't return vectors to save bandwidth
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
                "Found %d similar embeddings for user %s in optimized search",
                len(search_results),
                user_id,
            )
            return search_results

        except Exception as e:
            logger.error("Failed to search similar embeddings (optimized): %s", e)
            return []

    def batch_store_embeddings(
        self, embeddings_data: List[Dict[str, Any]], batch_size: int = 100
    ) -> List[str]:
        """
        Store multiple embeddings in batches for better performance

        Args:
            embeddings_data: List of dicts with memory_id, embedding, user_id, metadata
            batch_size: Number of embeddings to store per batch

        Returns:
            List of vector IDs
        """
        vector_ids = []

        try:
            for i in range(0, len(embeddings_data), batch_size):
                batch = embeddings_data[i : i + batch_size]
                points = []

                for data in batch:
                    vector_id = str(uuid.uuid4())
                    vector_ids.append(vector_id)

                    point = PointStruct(
                        id=vector_id,
                        vector=data["embedding"],
                        payload={
                            "memory_id": data["memory_id"],
                            "user_id": data["user_id"],
                            "created_at": data["metadata"].get("created_at"),
                            **data["metadata"],
                        },
                    )
                    points.append(point)

                # Batch upsert for better performance
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                    wait=False,  # Don't wait for indexing to complete
                )

                logger.debug("Stored batch of %d embeddings", len(points))

            logger.info(
                "Stored %d embeddings in %d batches",
                len(embeddings_data),
                (len(embeddings_data) + batch_size - 1) // batch_size,
            )

            return vector_ids

        except Exception as e:
            logger.error("Failed to batch store embeddings: %s", e)
            raise


# Global instance
vector_service = VectorService()
