"""
OpenWebUI History Importer

This module handles importing historical conversations from Open WebUI's SQLite database
and extracting memories from them using mnemosyne's existing extraction pipeline.
"""

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction

# PHASE 1 NOTE: This file is based on Phase 0 architecture
# These imports are commented out until the importer is updated for Phase 1
# from .llm_service import llm_service
# from .memory_search_service import memory_search_service  # Deleted in Phase 1
# from .models import Memory  # Replaced with ConversationTurn in Phase 1

logger = logging.getLogger(__name__)

# Thread lock for progress access
_progress_lock = threading.Lock()


def _log_with_thread(message: str, level: str = 'info'):
    """Helper to log with thread ID for consistency"""
    thread_id = threading.current_thread().ident
    getattr(logger, level)(f"[Thread {thread_id}] {message}")


class ImportProgress:
    """Track import progress in memory for real-time updates"""

    def __init__(self):
        self.total_conversations = 0
        self.processed_conversations = 0
        self.extracted_memories = 0
        self.failed_conversations = 0
        self.current_conversation_id = None
        self.status = "idle"  # idle, running, completed, failed, cancelled
        self.error_message = None
        self.start_time = None
        self.end_time = None
        self.dry_run = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert progress to dictionary for API responses"""
        elapsed = None
        if self.start_time:
            end = self.end_time or datetime.now()
            elapsed = (end - self.start_time).total_seconds()

        return {
            "total_conversations": self.total_conversations,
            "processed_conversations": self.processed_conversations,
            "extracted_memories": self.extracted_memories,
            "failed_conversations": self.failed_conversations,
            "current_conversation_id": self.current_conversation_id,
            "status": self.status,
            "error_message": self.error_message,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "elapsed_seconds": elapsed,
            "dry_run": self.dry_run,
            "progress_percentage": (
                int(
                    (self.processed_conversations / self.total_conversations) * 100
                )
                if self.total_conversations > 0
                else 0
            ),
        }


# Global progress tracker (in production, use Redis or database)
_import_progress = ImportProgress()


class OpenWebUIImporter:
    """Import and process conversations from Open WebUI database"""

    def __init__(self, db_path: str):
        """
        Initialize importer with path to Open WebUI database

        Args:
            db_path: Path to webui.db SQLite database
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database file not found: {db_path}")

        self.conn = None
        self.processed_chat_ids = set()

    def __enter__(self):
        """Context manager entry"""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.conn:
            self.conn.close()

    def get_conversations(
        self,
        user_id: Optional[str] = None,
        after_date: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve conversations from Open WebUI database

        Args:
            user_id: Filter by specific Open WebUI user ID
            after_date: Only get conversations created after this date
            limit: Maximum number of conversations to retrieve

        Returns:
            List of conversation dictionaries
        """
        query = "SELECT id, user_id, title, chat, created_at, updated_at FROM chat WHERE 1=1"
        params = []

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        if after_date:
            # Convert datetime to timestamp (Open WebUI uses BigInteger timestamps)
            timestamp = int(after_date.timestamp())
            query += " AND created_at >= ?"
            params.append(timestamp)

        query += " ORDER BY created_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        conversations = []
        for row in rows:
            conversations.append(
                {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "title": row["title"],
                    "chat": row["chat"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )

        return conversations

    def extract_user_messages(self, chat_json: str) -> List[str]:
        """
        Extract user messages from chat JSON

        Args:
            chat_json: JSON string containing chat messages

        Returns:
            List of user message contents
        """
        try:
            chat_data = json.loads(chat_json)

            # Handle different possible structures
            messages = []
            if isinstance(chat_data, dict):
                # Check for 'messages' key
                if "messages" in chat_data:
                    messages = chat_data["messages"]
                # Check for 'history' key
                elif "history" in chat_data:
                    messages = chat_data["history"]
            elif isinstance(chat_data, list):
                messages = chat_data

            # Extract user messages
            user_messages = []
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    content = msg.get("content", "")
                    if content and isinstance(content, str):
                        user_messages.append(content.strip())

            return user_messages

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse chat JSON: {e}")
            return []

    def format_conversation_text(self, user_messages: List[str]) -> str:
        """
        Format user messages into conversation text for extraction

        Args:
            user_messages: List of user message strings

        Returns:
            Formatted conversation text
        """
        if not user_messages:
            return ""

        # Join messages with clear separation
        conversation_parts = [f"User: {msg}" for msg in user_messages]
        return "\n\n".join(conversation_parts)

    def extract_memories_from_conversation(
        self, conversation_text: str, mnemosyne_user_id: str, dry_run: bool = False
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Extract memories from conversation using existing extraction pipeline

        Args:
            conversation_text: Formatted conversation text
            mnemosyne_user_id: Mnemosyne user ID (UUID)
            dry_run: If True, don't actually store memories

        Returns:
            Tuple of (memories_extracted_count, extracted_memories_list)
        """
        # Maximum conversation length (consistent with ExtractMemoriesView limit)
        MAX_CONVERSATION_LENGTH = 50000

        if not conversation_text or len(conversation_text.strip()) < 10:
            return 0, []

        # Enforce maximum length with truncation
        if len(conversation_text) > MAX_CONVERSATION_LENGTH:
            logger.warning(
                f"Conversation text too long ({len(conversation_text)} chars), truncating to {MAX_CONVERSATION_LENGTH}"
            )
            conversation_text = conversation_text[:MAX_CONVERSATION_LENGTH]

        try:
            # PHASE 1 NOTE: This importer is based on Phase 0 architecture
            # It needs to be rewritten for Phase 1 (raw conversation storage)
            # For now, returning empty to prevent crashes
            logger.warning("OpenWebUI importer not yet updated for Phase 1 - returning empty")
            return 0, []

            # Legacy Phase 0 code (commented out):
            # from settings_app.models import LLMSettings
            # settings = LLMSettings.get_settings()
            # system_prompt = settings.memory_extraction_prompt

            # Add timestamp for context
            now = datetime.now()
            system_prompt_with_date = f"{system_prompt}\n\nCurrent date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}"

            # Query LLM for memory extraction
            from .llm_service import MEMORY_EXTRACTION_FORMAT

            llm_result = llm_service.query_llm(
                system_prompt=system_prompt_with_date,
                prompt=conversation_text,
                response_format=MEMORY_EXTRACTION_FORMAT,
                max_tokens=16384,
            )

            if not llm_result["success"]:
                logger.error(
                    f"LLM extraction failed: {llm_result.get('error', 'Unknown error')}"
                )
                return 0, []

            # Parse extraction results
            try:
                memories_data = json.loads(llm_result["response"].strip())
                if not isinstance(memories_data, list):
                    logger.error("LLM response is not a list")
                    return 0, []
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response: {e}")
                return 0, []

            # Store memories
            stored_memories = []
            for memory_data in memories_data:
                if not isinstance(memory_data, dict):
                    continue

                content = memory_data.get("content", "")
                if not content:
                    continue

                # Prepare metadata with historical import tag
                metadata = {
                    "tags": memory_data.get("tags", []),
                    "extraction_source": "openwebui_historical_import",
                    "model_used": llm_result.get("model", "unknown"),
                    "import_date": datetime.now().isoformat(),
                }

                if dry_run:
                    # Don't actually store, just return what would be stored
                    stored_memories.append(
                        {"content": content, "metadata": metadata}
                    )
                else:
                    # Store using existing service
                    memory = memory_search_service.store_memory_with_embedding(
                        content=content, user_id=mnemosyne_user_id, metadata=metadata
                    )
                    stored_memories.append(
                        {
                            "id": str(memory.id),
                            "content": memory.content,
                            "metadata": memory.metadata,
                        }
                    )

            return len(stored_memories), stored_memories

        except Exception as e:
            logger.error(f"Unexpected error during memory extraction: {e}")
            return 0, []

    def map_openwebui_user_to_mnemosyne(
        self, openwebui_user_id: str
    ) -> str:
        """
        Map Open WebUI user ID to Mnemosyne user ID

        For now, we use the Open WebUI user ID if it's a valid UUID,
        otherwise generate a deterministic UUID from the ID

        Args:
            openwebui_user_id: User ID from Open WebUI

        Returns:
            Mnemosyne user ID (UUID string)
        """
        try:
            # Try to parse as UUID
            uuid.UUID(openwebui_user_id)
            return openwebui_user_id
        except ValueError:
            # Generate deterministic UUID from user ID
            namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace
            return str(uuid.uuid5(namespace, openwebui_user_id))

    def import_conversations(
        self,
        target_user_id: Optional[str] = None,
        openwebui_user_id: Optional[str] = None,
        after_date: Optional[datetime] = None,
        batch_size: int = 10,
        limit: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Import conversations and extract memories

        Args:
            target_user_id: Mnemosyne user ID to assign all imported memories to
            openwebui_user_id: Filter by specific Open WebUI user
            after_date: Only import conversations after this date
            batch_size: Number of conversations to process before committing
            limit: Maximum number of conversations to import
            dry_run: If True, don't actually store memories

        Returns:
            Import statistics dictionary
        """
        global _import_progress

        try:
            # Get conversations first (before touching global state)
            conversations = self.get_conversations(
                user_id=openwebui_user_id, after_date=after_date, limit=limit
            )

            # Update only the fields that weren't set by the view
            # DO NOT reset start_time, dry_run, or counters - they were already initialized
            with _progress_lock:
                _import_progress.status = "running"
                # Keep the start_time from view initialization - don't reset it
                # _import_progress.start_time is already set by the view
                _import_progress.total_conversations = len(conversations)
                # Keep counters at 0 (already set by view) - don't reset
                # processed_conversations, extracted_memories, failed_conversations already 0
                _log_with_thread(
                    f"Found {len(conversations)} conversations to process (dry_run={dry_run}), Progress ID: {id(_import_progress)}", 'info'
                )

            total_memories_extracted = 0
            failed_conversations = 0
            conversation_details = []

            # Process in batches
            for i in range(0, len(conversations), batch_size):
                # Check for cancellation at batch level (with lock)
                with _progress_lock:
                    current_status = _import_progress.status

                logger.debug(f"Batch {i}: Checking cancellation, status={current_status}, ID={id(_import_progress)}")
                if current_status == "cancelled":
                    _log_with_thread("Import cancelled by user (batch level)", 'info')
                    with _progress_lock:
                        _import_progress.end_time = datetime.now()
                    return {
                        "success": False,
                        "error": "Import cancelled by user",
                        "total_conversations": len(conversations),
                        "processed_conversations": _import_progress.processed_conversations,
                        "total_memories_extracted": total_memories_extracted,
                        "failed_conversations": failed_conversations,
                    }

                batch = conversations[i : i + batch_size]

                for conv in batch:
                    # Check if import was cancelled (with lock)
                    with _progress_lock:
                        current_status = _import_progress.status

                    logger.debug(f"Conv {conv['id']}: Checking cancellation, status={current_status}")
                    if current_status == "cancelled":
                        _log_with_thread("Import cancelled by user (conversation level)", 'info')
                        with _progress_lock:
                            _import_progress.end_time = datetime.now()
                        return {
                            "success": False,
                            "error": "Import cancelled by user",
                            "total_conversations": len(conversations),
                            "processed_conversations": _import_progress.processed_conversations,
                            "total_memories_extracted": total_memories_extracted,
                            "failed_conversations": failed_conversations,
                        }

                    with _progress_lock:
                        _import_progress.current_conversation_id = conv["id"]

                    try:
                        # Extract user messages
                        user_messages = self.extract_user_messages(conv["chat"])

                        if not user_messages:
                            logger.debug(
                                f"No user messages in conversation {conv['id']}"
                            )
                            with _progress_lock:
                                _import_progress.processed_conversations += 1
                            continue

                        # Format conversation
                        conversation_text = self.format_conversation_text(
                            user_messages
                        )

                        # Determine target user ID
                        if target_user_id:
                            mnemosyne_user_id = target_user_id
                        else:
                            mnemosyne_user_id = self.map_openwebui_user_to_mnemosyne(
                                conv["user_id"]
                            )

                        # Extract memories
                        memories_count, memories = (
                            self.extract_memories_from_conversation(
                                conversation_text, mnemosyne_user_id, dry_run
                            )
                        )

                        total_memories_extracted += memories_count

                        # Update progress with lock (grouped related updates)
                        with _progress_lock:
                            _import_progress.extracted_memories = total_memories_extracted
                            _import_progress.processed_conversations += 1

                        conversation_details.append(
                            {
                                "conversation_id": conv["id"],
                                "title": conv.get("title", "Untitled"),
                                "user_messages_count": len(user_messages),
                                "memories_extracted": memories_count,
                                "mnemosyne_user_id": mnemosyne_user_id,
                            }
                        )

                        logger.info(
                            f"Processed conversation {conv['id']}: {memories_count} memories extracted"
                        )

                    except Exception as e:
                        logger.error(
                            f"Failed to process conversation {conv['id']}: {e}"
                        )
                        failed_conversations += 1

                        # Update failure counts with lock
                        with _progress_lock:
                            _import_progress.failed_conversations = failed_conversations
                            _import_progress.processed_conversations += 1

            # Mark as completed with lock
            with _progress_lock:
                _import_progress.status = "completed"
                _import_progress.end_time = datetime.now()

            return {
                "success": True,
                "total_conversations": len(conversations),
                "processed_conversations": _import_progress.processed_conversations,
                "total_memories_extracted": total_memories_extracted,
                "failed_conversations": failed_conversations,
                "dry_run": dry_run,
                "conversation_details": conversation_details,
                "elapsed_seconds": (
                    _import_progress.end_time - _import_progress.start_time
                ).total_seconds(),
            }

        except Exception as e:
            # Mark as failed with lock
            with _progress_lock:
                _import_progress.status = "failed"
                _import_progress.error_message = str(e)
                _import_progress.end_time = datetime.now()
            logger.error(f"Import failed: {e}")
            raise

    @staticmethod
    def get_progress() -> Dict[str, Any]:
        """Get current import progress"""
        with _progress_lock:
            return _import_progress.to_dict()

    @staticmethod
    def cancel_import():
        """Cancel ongoing import (sets status flag)"""
        global _import_progress
        with _progress_lock:
            logger.info(f"Cancel requested. Current status: {_import_progress.status}, ID: {id(_import_progress)}, Total convs: {_import_progress.total_conversations}, Processed: {_import_progress.processed_conversations}")
            if _import_progress.status == "running":
                _import_progress.status = "cancelled"
                # Don't set end_time here - let the import loop set it when it exits
                logger.info(f"Import status set to cancelled. ID: {id(_import_progress)}")
            else:
                logger.warning(f"Cannot cancel - status is '{_import_progress.status}'. Import may have already completed or not started.")
