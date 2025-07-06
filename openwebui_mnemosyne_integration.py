import json
import logging
import requests
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

    def __init__(self):
        # Initialize valves (optional configuration for the Filter)
        self.valves = self.Valves()
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Initialize session for HTTP requests
        self.session = requests.Session()
        self.session.timeout = 30

    def _setup_auth(self):
        """Set up authentication headers if API key is provided"""
        if self.valves.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.valves.api_key}",
                "Content-Type": "application/json"
            })
        else:
            self.session.headers.update({"Content-Type": "application/json"})

    def _get_user_id(self, body: dict) -> str:
        """Extract user ID from request body"""
        # Try to get user ID from various possible locations
        user_id = None
        
        # Check if user info is in the body
        if isinstance(body, dict):
            user_id = body.get("user", {}).get("id") if body.get("user") else None
            if not user_id:
                user_id = body.get("user_id")
            if not user_id:
                user_id = body.get("__user", {}).get("id") if body.get("__user") else None
        
        # Fallback to a default user ID if none found
        if not user_id:
            user_id = "openwebui-user"
            self.logger.warning("No user ID found in request, using default: openwebui-user")
        
        return str(user_id)

    def _retrieve_memories(self, prompt: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve relevant memories from Mnemosyne"""
        try:
            self._setup_auth()
            
            url = f"{self.valves.mnemosyne_endpoint.rstrip('/')}/api/memories/retrieve/"
            payload = {
                "prompt": prompt,
                "user_id": user_id,
                "limit": self.valves.memory_limit,
                "threshold": self.valves.memory_threshold
            }
            
            self.logger.info(f"Retrieving memories for user {user_id}")
            
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                self.logger.info(f"Retrieved {result.get('count', 0)} memories")
                return result
            else:
                self.logger.error(f"Memory retrieval failed: {result.get('error')}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error retrieving memories: {str(e)}")
            return None

    def _extract_memories(self, conversation_text: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Extract memories from conversation"""
        try:
            self._setup_auth()
            
            url = f"{self.valves.mnemosyne_endpoint.rstrip('/')}/api/memories/extract/"
            payload = {
                "conversation_text": conversation_text,
                "user_id": user_id
            }
            
            self.logger.info(f"Extracting memories for user {user_id}")
            
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                self.logger.info(f"Extracted {result.get('memories_extracted', 0)} memories")
                return result
            else:
                self.logger.error(f"Memory extraction failed: {result.get('error')}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error extracting memories: {str(e)}")
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

    def inlet(self, body: dict) -> dict:
        """
        Process incoming requests - retrieve relevant memories and add to context
        """
        try:
            if not self.valves.enable_memory_retrieval:
                return body
            
            # Get user ID and current message
            user_id = self._get_user_id(body)
            user_message = self._extract_user_message(body)
            
            if not user_message:
                self.logger.warning("No user message found, skipping memory retrieval")
                return body
            
            # Retrieve relevant memories
            memory_result = self._retrieve_memories(user_message, user_id)
            
            if memory_result and memory_result.get("memories"):
                memories = memory_result["memories"]
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
                            
                            self.logger.info(f"Added {len(memories)} memories to context")
            
            return body
            
        except Exception as e:
            self.logger.error(f"Error in inlet: {str(e)}")
            return body

    def stream(self, event: dict) -> dict:
        """
        Process streaming events - no memory processing needed here
        """
        return event

    def outlet(self, body: dict) -> None:
        """
        Process outgoing responses - extract memories from the conversation
        """
        try:
            if not self.valves.enable_memory_extraction:
                return
            
            # Get user ID and build conversation text
            user_id = self._get_user_id(body)
            conversation_text = self._build_conversation_text(body)
            
            if not conversation_text:
                self.logger.warning("No conversation text found, skipping memory extraction")
                return
            
            # Extract memories from the conversation
            self._extract_memories(conversation_text, user_id)
            
        except Exception as e:
            self.logger.error(f"Error in outlet: {str(e)}")
