"""
OpenWebUI History Importer

This module handles importing historical conversations from Open WebUI's SQLite database
and storing them as conversation turns.

Features:
- Parses conversations into individual turns (user + assistant pairs)
- Stores using conversation_service.store_turn()
- Automatic atomic note extraction and relationship building via background tasks
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

from .conversation_service import conversation_service
from .models import ConversationTurn

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
        self.stored_turns = 0  # Track conversation turns
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
            "stored_turns": self.stored_turns,  # Report turns
            "extracted_memories": self.stored_turns,  # Backward compatibility
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

    def parse_chat_messages(self, chat_json: str) -> List[Dict[str, Any]]:
        """
        Parse chat JSON into messages

        Args:
            chat_json: JSON string containing chat messages

        Returns:
            List of message dictionaries with 'role' and 'content'
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

            # Extract and normalize messages
            parsed_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = msg.get("content", "")

                    if role in ["user", "assistant"] and content and isinstance(content, str):
                        parsed_messages.append({
                            "role": role,
                            "content": content.strip()
                        })

            return parsed_messages

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse chat JSON: {e}")
            return []

    def create_conversation_turns(self, messages: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
        """
        Create conversation turns from messages (user + assistant pairs)

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            List of (user_message, assistant_message) tuples
        """
        turns = []
        i = 0

        while i < len(messages):
            # Look for user message
            if messages[i]["role"] == "user":
                user_msg = messages[i]["content"]

                # Look for next assistant message
                assistant_msg = ""
                if i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                    assistant_msg = messages[i + 1]["content"]
                    i += 2  # Skip both user and assistant
                else:
                    # User message without assistant response (skip it)
                    i += 1
                    continue

                # Only add complete turns (both user and assistant)
                if user_msg and assistant_msg:
                    turns.append((user_msg, assistant_msg))
            else:
                # Skip orphaned assistant messages
                i += 1

        return turns

    def store_conversation_turns(
        self, turns: List[Tuple[str, str]], mnemosyne_user_id: str,
        session_id: str, dry_run: bool = False
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Store conversation turns

        Stores turns as ConversationTurn objects, which automatically:
        - Generate embeddings
        - Cache in working memory
        - Schedule background extraction of atomic notes
        - Schedule relationship building

        Args:
            turns: List of (user_message, assistant_message) tuples
            mnemosyne_user_id: Mnemosyne user ID (UUID)
            session_id: Session identifier for this conversation
            dry_run: If True, don't actually store turns

        Returns:
            Tuple of (turns_stored_count, stored_turn_details_list)
        """
        if not turns:
            return 0, []

        try:
            stored_turns = []

            for user_msg, assistant_msg in turns:
                # Truncate if needed
                MAX_MESSAGE_LENGTH = 10000
                if len(user_msg) > MAX_MESSAGE_LENGTH:
                    logger.warning(f"User message too long ({len(user_msg)} chars), truncating")
                    user_msg = user_msg[:MAX_MESSAGE_LENGTH]

                if len(assistant_msg) > MAX_MESSAGE_LENGTH:
                    logger.warning(f"Assistant message too long ({len(assistant_msg)} chars), truncating")
                    assistant_msg = assistant_msg[:MAX_MESSAGE_LENGTH]

                if dry_run:
                    # Don't actually store, just return what would be stored
                    stored_turns.append({
                        "user_message": user_msg,
                        "assistant_message": assistant_msg,
                        "session_id": session_id,
                        "dry_run": True
                    })
                else:
                    # Store using conversation_service
                    # This will automatically:
                    # 1. Generate embeddings
                    # 2. Cache in working memory
                    # 3. Schedule extraction task (immediate via Django-Q)
                    # 4. Extraction will schedule relationship building
                    turn = conversation_service.store_turn(
                        user_id=mnemosyne_user_id,
                        session_id=session_id,
                        user_message=user_msg,
                        assistant_message=assistant_msg
                    )

                    stored_turns.append({
                        "id": str(turn.id),
                        "turn_number": turn.turn_number,
                        "user_message": user_msg[:100] + "..." if len(user_msg) > 100 else user_msg,
                        "assistant_message": assistant_msg[:100] + "..." if len(assistant_msg) > 100 else assistant_msg,
                        "session_id": session_id,
                        "extracted": turn.extracted
                    })

                    logger.debug(f"Stored turn {turn.turn_number} for session {session_id}")

            logger.info(f"Stored {len(stored_turns)} turns for user {mnemosyne_user_id}")
            return len(stored_turns), stored_turns

        except Exception as e:
            logger.error(f"Unexpected error storing conversation turns: {e}", exc_info=True)
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
                        # Parse chat into messages
                        messages = self.parse_chat_messages(conv["chat"])

                        if not messages:
                            logger.debug(
                                f"No messages in conversation {conv['id']}"
                            )
                            with _progress_lock:
                                _import_progress.processed_conversations += 1
                            continue

                        # Create conversation turns (user + assistant pairs)
                        turns = self.create_conversation_turns(messages)

                        if not turns:
                            logger.debug(
                                f"No complete turns in conversation {conv['id']}"
                            )
                            with _progress_lock:
                                _import_progress.processed_conversations += 1
                            continue

                        # Determine target user ID
                        if target_user_id:
                            mnemosyne_user_id = target_user_id
                        else:
                            mnemosyne_user_id = self.map_openwebui_user_to_mnemosyne(
                                conv["user_id"]
                            )

                        # Generate session ID for this conversation
                        # Use OpenWebUI conversation ID as session ID
                        session_id = f"openwebui-import-{conv['id']}"

                        # Store conversation turns
                        # This will automatically trigger extraction and relationship building
                        turns_count, stored_turns = self.store_conversation_turns(
                            turns, mnemosyne_user_id, session_id, dry_run
                        )

                        total_memories_extracted += turns_count

                        # Update progress with lock (grouped related updates)
                        with _progress_lock:
                            _import_progress.stored_turns = total_memories_extracted
                            _import_progress.processed_conversations += 1

                        conversation_details.append(
                            {
                                "conversation_id": conv["id"],
                                "title": conv.get("title", "Untitled"),
                                "turns_count": len(turns),
                                "turns_stored": turns_count,
                                "mnemosyne_user_id": mnemosyne_user_id,
                                "session_id": session_id
                            }
                        )

                        logger.info(
                            f"Processed conversation {conv['id']}: {turns_count} turns stored"
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
                "total_turns_stored": total_memories_extracted,  # Turns stored
                "total_memories_extracted": total_memories_extracted,  # Backward compatibility
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
