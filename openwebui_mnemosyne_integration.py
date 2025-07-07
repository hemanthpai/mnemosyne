"""
Open Web UI Memory Integration Filter

This module provides an Open Web UI Filter to integrate with the Mnemosyne memory service
for retrieving and extracting memories during chat interactions.

The filter handles:
1. Retrieving relevant memories when user enters a prompt (inlet) and adding them as context for the LLM
2. Extracting memories from conversations after LLM responses (outlet)

API Endpoints Used:
- POST /api/memories/retrieve/ - Retrieve relevant memories for a prompt
- POST /api/memories/extract/ - Extract memories from conversation text

Open Web UI Filter Methods:
- async inlet(body, __event_emitter__, __user__) -> dict: Pre-process user input, add memory context
- async outlet(body, __event_emitter__, __user__) -> dict: Post-process conversation, extract memories
- stream(event) -> dict: Process streaming events (pass-through)

Configuration via Valves:
- mnemosyne_endpoint: URL of the Mnemosyne memory service
- api_key: Optional API key for authentication
- enable_memory_retrieval: Toggle memory retrieval in inlet
- enable_memory_extraction: Toggle memory extraction in outlet
- memory_limit: Maximum number of memories to retrieve
- memory_threshold: Similarity threshold for memory retrieval
- show_status_updates: Toggle real-time status updates with fun icons
"""

import json
import logging
import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


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

    def __init__(self):
        # Initialize valves (optional configuration for the Filter)
        self.valves = self.Valves()
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # HTTP timeout settings
        self.timeout = aiohttp.ClientTimeout(total=30)

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
            headers["Authorization"] = f"Bearer {self.valves.api_key}"
        return headers

    def _get_user_id(self, __user__: Optional[dict] = None) -> str:
        """Extract user ID from user object"""
        user_id = None
        
        # Get user ID from the __user__ parameter
        if __user__ and isinstance(__user__, dict):
            user_id = __user__.get("id")
            if not user_id:
                user_id = __user__.get("user_id")
        
        # Fallback to a default user ID if none found
        if not user_id:
            user_id = "openwebui-user"
            self.logger.warning("No user ID found in __user__ parameter, using default: openwebui-user")
        
        return str(user_id)

    async def _retrieve_memories(self, prompt: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve relevant memories from Mnemosyne"""
        try:
            url = f"{self.valves.mnemosyne_endpoint.rstrip('/')}/api/memories/retrieve/"
            payload = {
                "prompt": prompt,
                "user_id": user_id,
                "limit": self.valves.memory_limit,
                "threshold": self.valves.memory_threshold
            }
            
            self.logger.info(f"Retrieving memories for user {user_id} from {url}")
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload, headers=self._get_headers()) as response:
                    self.logger.info(f"Memory retrieval response status: {response.status}")
                    response.raise_for_status()
                    result = await response.json()
            
            if result.get("success"):
                self.logger.info(f"Retrieved {result.get('count', 0)} memories")
                return result
            else:
                self.logger.error(f"Memory retrieval failed: {result.get('error')}")
                return None
                
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout retrieving memories for user {user_id} from {url}")
            return None
        except aiohttp.ClientConnectorError as e:
            self.logger.error(f"Connection error retrieving memories from {url}: {str(e)}")
            return None
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"HTTP error retrieving memories from {url}: {e.status} {e.message}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving memories from {url}: {str(e)}")
            return None

    async def _extract_memories(self, conversation_text: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Extract memories from conversation"""
        try:
            url = f"{self.valves.mnemosyne_endpoint.rstrip('/')}/api/memories/extract/"
            payload = {
                "conversation_text": conversation_text,
                "user_id": user_id
            }
            
            self.logger.info(f"Extracting memories for user {user_id} from {url}")
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload, headers=self._get_headers()) as response:
                    self.logger.info(f"Memory extraction response status: {response.status}")
                    response.raise_for_status()
                    result = await response.json()
            
            if result.get("success"):
                self.logger.info(f"Extracted {result.get('memories_extracted', 0)} memories")
                return result
            else:
                self.logger.error(f"Memory extraction failed: {result.get('error')}")
                return None
                
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout extracting memories for user {user_id} from {url}")
            return None
        except aiohttp.ClientConnectorError as e:
            self.logger.error(f"Connection error extracting memories from {url}: {str(e)}")
            return None
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"HTTP error extracting memories from {url}: {e.status} {e.message}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error extracting memories from {url}: {str(e)}")
            return None

    def _format_memories_for_context(self, memories: List[Dict[str, Any]]) -> str:
        """Format memories for inclusion in LLM context"""
        if not memories:
            return ""
        
        context_parts = ["## Relevant Memories from Previous Conversations"]
        
        for i, memory in enumerate(memories, 1):
            content = memory.get("content", "")
            metadata = memory.get("metadata", {})
            tags = metadata.get("tags", [])
            created_at = memory.get("created_at", "")
            
            memory_entry = f"\n**Memory {i}:**"
            memory_entry += f"\n{content}"
            
            if tags:
                memory_entry += f"\n*Tags: {', '.join(tags)}*"
            
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

    def _extract_user_message(self, body: dict) -> str:
        """Extract the user's message from the request body"""
        try:
            messages = body.get("messages", [])
            if messages:
                # Get the last user message
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        return msg.get("content", "")
            return ""
        except Exception as e:
            self.logger.error(f"Error extracting user message: {str(e)}")
            return ""

    def _build_conversation_text(self, body: dict) -> str:
        """Build conversation text from messages for memory extraction"""
        try:
            messages = body.get("messages", [])
            conversation_parts = []
            
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role and content:
                    conversation_parts.append(f"{role}: {content}")
            
            return "\n".join(conversation_parts)
        except Exception as e:
            self.logger.error(f"Error building conversation text: {str(e)}")
            return ""

    async def inlet(self, body: dict, __event_emitter__, __user__: Optional[dict] = None) -> dict:
        """
        Process incoming requests - retrieve relevant memories and add to context
        """
        try:
            if not self.valves.enable_memory_retrieval:
                await self._emit_status(__event_emitter__, "🔇 Memory retrieval is disabled", True)
                return body
            
            # Step 1: Identify user
            await self._emit_status(__event_emitter__, "🔍 Identifying user for personalized memories...", False)
            
            user_id = self._get_user_id(__user__)
            user_message = self._extract_user_message(body)
            
            if not user_message:
                await self._emit_status(__event_emitter__, "⚠️ No user message found, skipping memory retrieval", True)
                self.logger.warning("No user message found, skipping memory retrieval")
                return body
            
            # Step 2: Search for relevant memories
            await self._emit_status(__event_emitter__, "🧠 Searching for relevant memories...", False)
            
            memory_result = await self._retrieve_memories(user_message, user_id)
            
            if memory_result is None:
                await self._emit_status(__event_emitter__, "⚠️ Could not connect to memory service", True)
                return body
            
            if memory_result and memory_result.get("memories"):
                memories = memory_result["memories"]
                
                # Step 3: Found memories - preparing context
                await self._emit_status(__event_emitter__, f"✨ Found {len(memories)} relevant memories! Preparing context...", False)
                
                memory_context = self._format_memories_for_context(memories)
                
                if memory_context:
                    # Add memory context to the conversation
                    messages = body.get("messages", [])
                    if messages:
                        # Insert memory context before the last user message
                        last_user_msg_idx = -1
                        for i, msg in enumerate(reversed(messages)):
                            if msg.get("role") == "user":
                                last_user_msg_idx = len(messages) - 1 - i
                                break
                        
                        if last_user_msg_idx >= 0:
                            # Create a system message with memory context
                            memory_msg = {
                                "role": "system",
                                "content": memory_context
                            }
                            messages.insert(last_user_msg_idx, memory_msg)
                            
                            # Step 4: Success - memories added
                            await self._emit_status(__event_emitter__, f"🎯 Memory context added! Using {len(memories)} memories to enhance response.", True)
                            
                            self.logger.info(f"Added {len(memories)} memories to context")
            else:
                # No relevant memories found
                await self._emit_status(__event_emitter__, "🤔 No relevant memories found for this conversation", True)
            
            return body
            
        except Exception as e:
            await self._emit_status(__event_emitter__, f"❌ Error retrieving memories: {str(e)}", True)
            self.logger.error(f"Error in inlet: {str(e)}")
            return body

    def stream(self, event: dict) -> dict:
        """
        Process streaming events - no memory processing needed here
        """
        return event

    async def outlet(self, body: dict, __event_emitter__, __user__: Optional[dict] = None) -> dict:
        """
        Process outgoing responses - extract memories from the conversation
        """
        try:
            if not self.valves.enable_memory_extraction:
                await self._emit_status(__event_emitter__, "🔇 Memory extraction is disabled", True)
                return body
            
            # Step 1: Preparing for memory extraction
            await self._emit_status(__event_emitter__, "💭 Analyzing conversation for new memories...", False)
            
            user_id = self._get_user_id(__user__)
            conversation_text = self._build_conversation_text(body)
            
            if not conversation_text:
                await self._emit_status(__event_emitter__, "⚠️ No conversation content found for memory extraction", True)
                self.logger.warning("No conversation text found, skipping memory extraction")
                return body
            
            # Step 2: Processing conversation
            await self._emit_status(__event_emitter__, "🔍 Processing conversation content...", False)
            
            # Step 3: Extracting memories
            await self._emit_status(__event_emitter__, "🧬 Extracting valuable memories from conversation...", False)
            
            # Extract memories from the conversation
            extraction_result = await self._extract_memories(conversation_text, user_id)
            
            # Step 4: Report results
            if extraction_result and extraction_result.get("success"):
                memories_count = extraction_result.get("memories_extracted", 0)
                if memories_count > 0:
                    await self._emit_status(__event_emitter__, f"🎉 Successfully extracted {memories_count} new memories for future reference!", True)
                else:
                    await self._emit_status(__event_emitter__, "💡 No new memorable information found in this conversation", True)
            else:
                await self._emit_status(__event_emitter__, "📝 Memory extraction completed (processing in background)", True)
            
            return body
            
        except Exception as e:
            await self._emit_status(__event_emitter__, f"❌ Error during memory extraction: {str(e)}", True)
            self.logger.error(f"Error in outlet: {str(e)}")
            return body
