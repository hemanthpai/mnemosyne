"""
Open Web UI Memory Integration Filter (v2 - Fixed)

This module provides an optimized Open Web UI Filter to integrate with the Mnemosyne memory service
for retrieving and extracting memories during chat interactions.

*** KEY IMPROVEMENTS IN V2 ***
- Only processes latest user messages (no duplicates)
- Never extracts from assistant responses
- Proper session isolation for concurrent chats
- Message tracking with content hashing
- Hybrid persistence (memory + file)

The filter handles:
1. Retrieving relevant memories when user enters a prompt (inlet) and adding them as context for the LLM
2. Extracting memories ONLY from user messages after LLM responses (outlet)

API Endpoints Used:
- POST /api/memories/retrieve/ - Retrieve relevant memories for a prompt
- POST /api/memories/extract/ - Extract memories from conversation text

Open Web UI Filter Methods:
- async inlet(body, __event_emitter__, __user__) -> dict: Pre-process user input, add memory context
- async outlet(body, __event_emitter__, __user__) -> dict: Post-process conversation, extract memories
- stream(event) -> dict: Process streaming events (pass-through)
"""

import json
import logging
import aiohttp
import asyncio
import hashlib
import os
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from pydantic import BaseModel, Field
from pathlib import Path
import threading


class Filter:
    # Valves: Configuration options for the filter
    class Valves(BaseModel):
        mnemosyne_endpoint: str = Field(
            default="http://localhost:8000",
            description="Mnemosyne memory service endpoint URL",
            title="Mnemosyne Endpoint"
        )
        api_key: str = Field(
            default="",
            description="Optional API key for Mnemosyne authentication",
            title="API Key"
        )
        optimization_level: str = Field(
            default="fast",
            description="Response optimization: 'fast' (60-80% smaller), 'detailed' (with metadata), 'full' (everything + LLM summary)",
            title="Optimization Level"
        )
        enable_memory_retrieval: bool = Field(
            default=True,
            description="Enable retrieving relevant memories before LLM response",
            title="Enable Memory Retrieval"
        )
        enable_memory_extraction: bool = Field(
            default=True,
            description="Enable extracting memories from conversations",
            title="Enable Memory Extraction"
        )
        memory_limit: int = Field(
            default=10,
            description="Maximum number of memories to retrieve (1-20)",
            title="Memory Limit",
            ge=1,
            le=20
        )
        memory_threshold: float = Field(
            default=0.7,
            description="Similarity threshold for memory retrieval (0.0-1.0)",
            title="Memory Threshold",
            ge=0.0,
            le=1.0
        )
        show_status_updates: bool = Field(
            default=True,
            description="Show real-time status updates during memory operations",
            title="Show Status Updates"
        )
        enable_rate_limit_backoff: bool = Field(
            default=True,
            description="Enable automatic backoff when rate limits are hit",
            title="Rate Limit Backoff"
        )
        persistence_enabled: bool = Field(
            default=True,
            description="Enable persistent tracking of processed messages",
            title="Enable Persistence"
        )
        persistence_file: str = Field(
            default="/tmp/mnemosyne_tracking.pkl",
            description="Path to persistence file for tracking processed messages",
            title="Persistence File Path"
        )

    def __init__(self):
        # Initialize valves (optional configuration for the Filter)
        self.valves = self.Valves()

        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # HTTP timeout settings
        self.timeout = aiohttp.ClientTimeout(total=45)

        # Message tracking: {user_id: {session_id: {message_hash: timestamp}}}
        self._processed_messages = {}
        self._lock = threading.Lock()

        # Session tracking for isolation
        self._active_sessions = {}

        # Load persisted tracking data
        self._load_tracking_data()

        # Cleanup old entries periodically
        self._last_cleanup = datetime.now()

    def _load_tracking_data(self):
        """Load persisted tracking data from file"""
        if not self.valves.persistence_enabled:
            return

        try:
            if os.path.exists(self.valves.persistence_file):
                with open(self.valves.persistence_file, 'rb') as f:
                    data = pickle.load(f)
                    if isinstance(data, dict):
                        self._processed_messages = data
                        self.logger.info(f"Loaded tracking data for {len(data)} users")
        except Exception as e:
            self.logger.error(f"Failed to load tracking data: {e}")
            self._processed_messages = {}

    def _save_tracking_data(self):
        """Save tracking data to file for persistence"""
        if not self.valves.persistence_enabled:
            return

        try:
            # Create directory if it doesn't exist
            Path(self.valves.persistence_file).parent.mkdir(parents=True, exist_ok=True)

            with self._lock:
                with open(self.valves.persistence_file, 'wb') as f:
                    pickle.dump(self._processed_messages, f)
        except Exception as e:
            self.logger.error(f"Failed to save tracking data: {e}")

    def _cleanup_old_entries(self):
        """Remove tracking entries older than 24 hours"""
        try:
            now = datetime.now()

            # Only cleanup once per hour
            if (now - self._last_cleanup).total_seconds() < 3600:
                return

            self._last_cleanup = now
            cutoff_time = now - timedelta(hours=24)

            with self._lock:
                # Clean up processed messages
                for user_id in list(self._processed_messages.keys()):
                    for session_id in list(self._processed_messages.get(user_id, {}).keys()):
                        session_data = self._processed_messages[user_id][session_id]
                        # Remove old message hashes
                        for msg_hash in list(session_data.keys()):
                            if session_data[msg_hash] < cutoff_time:
                                del session_data[msg_hash]

                        # Remove empty sessions
                        if not session_data:
                            del self._processed_messages[user_id][session_id]

                    # Remove empty users
                    if not self._processed_messages.get(user_id):
                        del self._processed_messages[user_id]

                # Save after cleanup
                self._save_tracking_data()

            self.logger.info(f"Cleaned up old tracking entries older than {cutoff_time}")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def _get_message_hash(self, content: str, role: str = "user") -> str:
        """Generate a hash for a message to track if it's been processed"""
        # Include role in hash to differentiate user/assistant messages
        hash_input = f"{role}:{content}".encode('utf-8')
        return hashlib.sha256(hash_input).hexdigest()

    def _has_been_processed(self, user_id: str, session_id: str, message_hash: str) -> bool:
        """Check if a message has already been processed"""
        with self._lock:
            user_data = self._processed_messages.get(user_id, {})
            session_data = user_data.get(session_id, {})
            return message_hash in session_data

    def _mark_as_processed(self, user_id: str, session_id: str, message_hash: str):
        """Mark a message as processed"""
        with self._lock:
            if user_id not in self._processed_messages:
                self._processed_messages[user_id] = {}
            if session_id not in self._processed_messages[user_id]:
                self._processed_messages[user_id][session_id] = {}

            self._processed_messages[user_id][session_id][message_hash] = datetime.now()

        # Save to disk periodically
        self._save_tracking_data()

    def _get_session_id(self, body: dict) -> str:
        """Extract or generate a session ID for the current chat thread"""
        # Try to get session/chat ID from body
        # OpenWebUI might include this in metadata
        session_id = body.get("chat_id") or body.get("session_id") or body.get("conversation_id")

        if not session_id:
            # Generate session ID based on message history pattern
            # This helps identify unique conversations
            messages = body.get("messages", [])
            if messages:
                # Use hash of first few messages as session identifier
                session_content = ""
                for msg in messages[:3]:  # First 3 messages usually unique enough
                    session_content += f"{msg.get('role', '')}:{msg.get('content', '')[:100]}"
                session_id = hashlib.md5(session_content.encode()).hexdigest()[:16]
            else:
                session_id = "default"

        return str(session_id)

    def _is_first_user_message(self, body: dict) -> bool:
        """Check if this is the first user message in a conversation"""
        messages = body.get("messages", [])
        user_message_count = sum(1 for msg in messages if msg.get("role") == "user")
        # First user message if there's only one user message total
        return user_message_count == 1

    def _get_latest_user_message(self, body: dict) -> Optional[str]:
        """Extract only the latest user message from the conversation"""
        messages = body.get("messages", [])

        # Iterate backwards to find the most recent user message
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")

        return None

    def _get_all_user_messages(self, body: dict) -> List[Tuple[str, int]]:
        """Get all user messages with their indices"""
        messages = body.get("messages", [])
        user_messages = []

        for idx, msg in enumerate(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if content:
                    user_messages.append((content, idx))

        return user_messages

    def _get_unprocessed_user_messages(self, body: dict, user_id: str, session_id: str) -> List[str]:
        """Get only user messages that haven't been processed yet"""
        unprocessed = []

        for content, idx in self._get_all_user_messages(body):
            msg_hash = self._get_message_hash(content, "user")
            if not self._has_been_processed(user_id, session_id, msg_hash):
                unprocessed.append(content)
                # Mark it as processed immediately to avoid race conditions
                self._mark_as_processed(user_id, session_id, msg_hash)

        return unprocessed

    async def _emit_status(self, __event_emitter__, description: str, done: bool = False):
        """Helper method to conditionally emit status updates"""
        if self.valves.show_status_updates:
            await __event_emitter__({
                "type": "status",
                "data": {"description": description, "done": done}
            })

    def _get_headers(self) -> dict:
        """Get HTTP headers including authentication if provided"""
        headers = {"Content-Type": "application/json"}
        if self.valves.api_key:
            headers["X-API-Key"] = self.valves.api_key
            headers["Authorization"] = f"Bearer {self.valves.api_key}"
        return headers

    def _get_user_id(self, __user__: Optional[dict] = None) -> str:
        """Extract user ID from user object"""
        user_id = None

        if __user__ and isinstance(__user__, dict):
            user_id = __user__.get("id") or __user__.get("user_id")

        if not user_id:
            user_id = "openwebui-user"
            self.logger.warning("No user ID found, using default: openwebui-user")

        return str(user_id)

    def _get_optimization_config(self) -> dict:
        """Get configuration based on optimization level"""
        level = self.valves.optimization_level.lower()

        configs = {
            "fast": {
                "fields": ["id", "content"],
                "include_search_metadata": False,
                "include_summary": False,
                "description": "Fast mode (minimal fields)"
            },
            "detailed": {
                "fields": ["id", "content", "created_at"],
                "include_search_metadata": True,
                "include_summary": False,
                "description": "Detailed mode (with metadata)"
            },
            "full": {
                "fields": ["id", "content", "metadata", "created_at", "updated_at"],
                "include_search_metadata": True,
                "include_summary": True,
                "description": "Full mode (everything)"
            }
        }

        return configs.get(level, configs["fast"])

    async def _handle_rate_limit(self, response_status: int, __event_emitter__) -> bool:
        """Handle rate limiting responses"""
        if response_status == 429:
            if self.valves.enable_rate_limit_backoff:
                await self._emit_status(__event_emitter__, "⏱️ Rate limit reached, waiting...", False)
                await asyncio.sleep(60)
                return True
            else:
                await self._emit_status(__event_emitter__, "🚫 Rate limit reached", True)
                return False
        return False

    async def _retrieve_memories(self, prompt: str, user_id: str, __event_emitter__) -> Optional[Dict[str, Any]]:
        """Retrieve relevant memories from Mnemosyne"""
        try:
            url = f"{self.valves.mnemosyne_endpoint.rstrip('/')}/api/memories/retrieve/"
            config = self._get_optimization_config()

            payload = {
                "prompt": prompt,
                "user_id": user_id,
                "limit": self.valves.memory_limit,
                "threshold": self.valves.memory_threshold,
                "fields": config["fields"],
                "include_search_metadata": config["include_search_metadata"],
                "include_summary": config["include_summary"]
            }

            self.logger.info(f"Retrieving memories for user {user_id}")
            await self._emit_status(__event_emitter__, f"🧠 Searching memories...", False)

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload, headers=self._get_headers()) as response:
                    if response.status == 429:
                        if await self._handle_rate_limit(response.status, __event_emitter__):
                            async with session.post(url, json=payload, headers=self._get_headers()) as retry_response:
                                retry_response.raise_for_status()
                                result = await retry_response.json()
                        else:
                            return None
                    else:
                        response.raise_for_status()
                        result = await response.json()

            if result.get("success"):
                memory_count = result.get('count', 0)
                self.logger.info(f"Retrieved {memory_count} memories")
                return result
            else:
                self.logger.error(f"Memory retrieval failed: {result.get('error')}")
                return None

        except Exception as e:
            self.logger.error(f"Error retrieving memories: {str(e)}")
            await self._emit_status(__event_emitter__, "⚠️ Could not retrieve memories", True)
            return None

    async def _extract_memories(self, conversation_text: str, user_id: str, __event_emitter__) -> Optional[Dict[str, Any]]:
        """Extract memories from conversation"""
        try:
            url = f"{self.valves.mnemosyne_endpoint.rstrip('/')}/api/memories/extract/"
            config = self._get_optimization_config()

            payload = {
                "conversation_text": conversation_text,
                "user_id": user_id,
                "fields": config["fields"]
            }

            self.logger.info(f"Extracting memories for user {user_id}")

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload, headers=self._get_headers()) as response:
                    if response.status == 429:
                        if await self._handle_rate_limit(response.status, __event_emitter__):
                            async with session.post(url, json=payload, headers=self._get_headers()) as retry_response:
                                retry_response.raise_for_status()
                                result = await retry_response.json()
                        else:
                            return None
                    else:
                        response.raise_for_status()
                        result = await response.json()

            if result.get("success"):
                extracted_count = result.get("memories_extracted", 0)
                self.logger.info(f"Extracted {extracted_count} memories")
                return result
            else:
                self.logger.error(f"Memory extraction failed: {result.get('error')}")
                return None

        except Exception as e:
            self.logger.error(f"Error extracting memories: {str(e)}")
            await self._emit_status(__event_emitter__, "⚠️ Could not extract memories", True)
            return None

    def _format_memories_for_context(self, memories: List[Dict[str, Any]]) -> str:
        """Format memories for inclusion in LLM context"""
        if not memories:
            return ""

        context_parts = ["## Relevant Memories from Previous Conversations"]

        for i, memory in enumerate(memories, 1):
            content = memory.get("content", "")
            memory_entry = f"\n**Memory {i}:**\n{content}"

            # Include metadata if available
            if "created_at" in memory:
                created_at = memory.get("created_at", "")
                if created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        formatted_date = dt.strftime("%Y-%m-%d")
                        memory_entry += f"\n*Date: {formatted_date}*"
                    except:
                        pass

            context_parts.append(memory_entry)

        context_parts.append("\n---\n")
        return "\n".join(context_parts)

    async def inlet(self, body: dict, __event_emitter__, __user__: Optional[dict] = None) -> dict:
        """
        Process incoming requests - retrieve relevant memories and add to context
        Only uses the latest user message for retrieval (not the entire history)
        """
        try:
            # Cleanup old entries periodically
            self._cleanup_old_entries()

            if not self.valves.enable_memory_retrieval:
                await self._emit_status(__event_emitter__, "🔇 Memory retrieval disabled", True)
                return body

            user_id = self._get_user_id(__user__)
            session_id = self._get_session_id(body)

            # Get the latest user message for retrieval
            user_message = self._get_latest_user_message(body)

            if not user_message:
                await self._emit_status(__event_emitter__, "⚠️ No user message found", True)
                self.logger.warning("No user message found for memory retrieval")
                return body

            # Log what we're doing
            is_first = self._is_first_user_message(body)
            self.logger.info(f"Processing {'first' if is_first else 'subsequent'} message for session {session_id}")

            # Retrieve memories based on latest user message
            await self._emit_status(__event_emitter__, "🔍 Searching for relevant memories...", False)
            memory_result = await self._retrieve_memories(user_message, user_id, __event_emitter__)

            if memory_result and memory_result.get("memories"):
                memories = memory_result["memories"]

                # Format and add memories to context
                await self._emit_status(__event_emitter__, f"✨ Found {len(memories)} relevant memories!", False)

                memory_context = self._format_memories_for_context(memories)

                if memory_context:
                    messages = body.get("messages", [])
                    if messages:
                        # Find last user message index
                        last_user_idx = -1
                        for i in reversed(range(len(messages))):
                            if messages[i].get("role") == "user":
                                last_user_idx = i
                                break

                        if last_user_idx >= 0:
                            # Insert memory context as system message before last user message
                            memory_msg = {
                                "role": "system",
                                "content": memory_context
                            }
                            messages.insert(last_user_idx, memory_msg)

                            await self._emit_status(__event_emitter__, f"🎯 Added {len(memories)} memories to context", True)
                            self.logger.info(f"Added {len(memories)} memories to context")
            else:
                await self._emit_status(__event_emitter__, "🤔 No relevant memories found", True)

            return body

        except Exception as e:
            await self._emit_status(__event_emitter__, f"❌ Error: {str(e)}", True)
            self.logger.error(f"Error in inlet: {str(e)}")
            return body

    def stream(self, event: dict) -> dict:
        """Process streaming events - pass through"""
        return event

    async def outlet(self, body: dict, __event_emitter__, __user__: Optional[dict] = None) -> dict:
        """
        Process outgoing responses - extract memories ONLY from unprocessed user messages
        Never extracts from assistant responses
        """
        try:
            if not self.valves.enable_memory_extraction:
                await self._emit_status(__event_emitter__, "🔇 Memory extraction disabled", True)
                return body

            user_id = self._get_user_id(__user__)
            session_id = self._get_session_id(body)

            # Get only unprocessed user messages
            unprocessed_messages = self._get_unprocessed_user_messages(body, user_id, session_id)

            if not unprocessed_messages:
                self.logger.info("No new user messages to process for memory extraction")
                return body

            # Build conversation text from ONLY the unprocessed user messages
            conversation_text = "\n".join([f"user: {msg}" for msg in unprocessed_messages])

            # Check length limit
            if len(conversation_text) > 45000:
                await self._emit_status(__event_emitter__, "⚠️ Truncating long messages", False)
                conversation_text = conversation_text[:45000] + "...[truncated]"

            # Extract memories
            await self._emit_status(__event_emitter__, f"💭 Analyzing {len(unprocessed_messages)} new message(s)...", False)

            extraction_result = await self._extract_memories(conversation_text, user_id, __event_emitter__)

            if extraction_result and extraction_result.get("success"):
                memories_count = extraction_result.get("memories_extracted", 0)
                if memories_count > 0:
                    await self._emit_status(__event_emitter__, f"🎉 Extracted {memories_count} new memories!", True)
                else:
                    await self._emit_status(__event_emitter__, "💡 No new memories found", True)
            else:
                await self._emit_status(__event_emitter__, "📝 Memory extraction completed", True)

            return body

        except Exception as e:
            await self._emit_status(__event_emitter__, f"❌ Error: {str(e)}", True)
            self.logger.error(f"Error in outlet: {str(e)}")
            return body