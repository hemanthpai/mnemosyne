# Create memories/batch_service.py

import logging
from typing import Any, Dict, List

from django.utils import timezone

from .llm_service import llm_service
from .models import Memory
from .vector_service import vector_service

logger = logging.getLogger(__name__)


class BatchMemoryService:
    """Service for efficient batch operations on memories"""

    def batch_store_memories_with_embeddings(
        self, memories_data: List[Dict[str, Any]], user_id: str, batch_size: int = 20
    ) -> Dict[str, Any]:
        """
        Efficiently store multiple memories with their embeddings in batches

        Args:
            memories_data: List of dicts with 'content' and 'metadata' keys
            user_id: UUID of the user
            batch_size: Size of batches for processing

        Returns:
            Dictionary with success status and created memory info
        """
        try:
            if not memories_data:
                return {
                    "success": True,
                    "created_count": 0,
                    "failed_count": 0,
                    "created_memories": [],
                    "failed_memories": [],
                }

            created_memories = []
            failed_memories = []

            # Process in batches to manage memory usage
            for i in range(0, len(memories_data), batch_size):
                batch = memories_data[i : i + batch_size]
                batch_result = self._process_memory_batch(batch, user_id)

                created_memories.extend(batch_result["created"])
                failed_memories.extend(batch_result["failed"])

                logger.info(
                    f"Processed batch {i // batch_size + 1}/{(len(memories_data) + batch_size - 1) // batch_size}: "
                    f"{len(batch_result['created'])} created, {len(batch_result['failed'])} failed"
                )

            return {
                "success": True,
                "created_count": len(created_memories),
                "failed_count": len(failed_memories),
                "created_memories": created_memories,
                "failed_memories": failed_memories,
            }

        except Exception as e:
            logger.error(f"Batch memory storage failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "created_count": 0,
                "failed_count": len(memories_data),
                "created_memories": [],
                "failed_memories": memories_data,
            }

    def _process_memory_batch(
        self, batch: List[Dict[str, Any]], user_id: str
    ) -> Dict[str, List]:
        """Process a single batch of memories"""

        created_memories = []
        try:
            # Step 1: Extract content for embedding generation
            contents_for_embedding = []
            for item in batch:
                content = item.get("content", "")
                if content:
                    contents_for_embedding.append(content)
                else:
                    logger.warning("Skipping memory with empty content")

            if not contents_for_embedding:
                return {
                    "created": [],
                    "failed": [
                        {"content": item.get("content", ""), "error": "Empty content"}
                        for item in batch
                    ],
                }

            # Step 2: Generate embeddings in batch
            logger.debug(
                f"Generating embeddings for {len(contents_for_embedding)} items"
            )
            embedding_result = llm_service.get_embeddings(contents_for_embedding)

            if not embedding_result["success"]:
                error_msg = embedding_result.get("error", "Unknown embedding error")
                logger.error(f"Batch embedding generation failed: {error_msg}")
                return {
                    "created": [],
                    "failed": [
                        {"content": item.get("content", ""), "error": error_msg}
                        for item in batch
                    ],
                }

            embeddings = embedding_result["embeddings"]
            if len(embeddings) != len(contents_for_embedding):
                logger.error(
                    f"Embedding count mismatch: {len(embeddings)} vs {len(contents_for_embedding)}"
                )
                return {
                    "created": [],
                    "failed": [
                        {
                            "content": item.get("content", ""),
                            "error": "Embedding count mismatch",
                        }
                        for item in batch
                    ],
                }

            # Step 3: Create Memory objects in database
            memories_to_create = []
            valid_items = []

            for i, item in enumerate(batch):
                content = item.get("content", "")
                if content and i < len(embeddings):
                    metadata = item.get("metadata", {})

                    memory = Memory(
                        user_id=user_id,
                        content=content,
                        metadata=metadata,
                        created_at=timezone.now(),
                        updated_at=timezone.now(),
                    )
                    memories_to_create.append(memory)
                    valid_items.append((item, embeddings[i]))

            if not memories_to_create:
                return {
                    "created": [],
                    "failed": [
                        {
                            "content": item.get("content", ""),
                            "error": "No valid memories to create",
                        }
                        for item in batch
                    ],
                }

            # Bulk create memories in database
            created_memories = Memory.objects.bulk_create(memories_to_create)
            logger.debug(f"Created {len(created_memories)} memory records in database")

            # Step 4: Prepare vector data for batch storage
            vector_data = []
            for memory, (original_item, embedding) in zip(
                created_memories, valid_items
            ):
                vector_data.append(
                    {
                        "memory_id": str(memory.id),
                        "embedding": embedding,
                        "user_id": str(user_id),
                        "metadata": {
                            **memory.metadata,
                            "created_at": memory.created_at.isoformat(),
                        },
                    }
                )

            # Step 5: Batch store embeddings in vector database
            logger.debug(f"Storing {len(vector_data)} embeddings in vector database")
            vector_ids = vector_service.batch_store_embeddings(vector_data)

            if len(vector_ids) != len(created_memories):
                logger.error(
                    f"Vector ID count mismatch: {len(vector_ids)} vs {len(created_memories)}"
                )
                # Clean up: delete created memories since vector storage failed
                Memory.objects.filter(id__in=[m.id for m in created_memories]).delete()
                return {
                    "created": [],
                    "failed": [
                        {
                            "content": item.get("content", ""),
                            "error": "Vector storage failed",
                        }
                        for item in batch
                    ],
                }

            # Step 6: Update memories with vector IDs
            memory_updates = []
            for memory, vector_id in zip(created_memories, vector_ids):
                memory.vector_id = vector_id
                memory_updates.append(memory)

            # Bulk update vector IDs
            Memory.objects.bulk_update(memory_updates, ["vector_id"])

            logger.info(
                f"Successfully stored batch of {len(created_memories)} memories with embeddings"
            )

            return {
                "created": [
                    {
                        "id": str(m.id),
                        "content": m.content,
                        "metadata": m.metadata,
                        "created_at": m.created_at.isoformat(),
                        "vector_id": m.vector_id,
                    }
                    for m in created_memories
                ],
                "failed": [],
            }

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")

            # Clean up any created memories if vector storage fails
            if "created_memories" in locals():
                try:
                    Memory.objects.filter(
                        id__in=[m.id for m in created_memories]
                    ).delete()
                    logger.info(
                        "Cleaned up partially created memories due to batch failure"
                    )
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup memories: {cleanup_error}")

            return {
                "created": [],
                "failed": [
                    {"content": item.get("content", ""), "error": str(e)}
                    for item in batch
                ],
            }


# Global instance
batch_memory_service = BatchMemoryService()
