#!/usr/bin/env python3
"""
Mnemosyne MCP Server

Phase 2: Model Context Protocol server for cross-platform memory access
Enables Claude Desktop, ChatGPT, and other AI assistants to access Mnemosyne

Tools:
- get_working_memory: Retrieve recent conversations (<10ms)
- search_memories: Search conversations (100-300ms)
- store_conversation_turn: Store new conversation

Resources:
- memory://user/{user_id}/working: Working memory stream
- memory://user/{user_id}/raw: Recent conversations

Prompts:
- format_context: Format memories for AI context
"""

import os
import sys
import json
import logging
from typing import Any, Dict, List

# Add Django project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'memory_service.settings')
import django
django.setup()

from memories.cache_service import cache_service
from memories.conversation_service import conversation_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MemoryMCPServer:
    """MCP Server for Mnemosyne Memory Service"""

    def __init__(self):
        self.name = "mnemosyne"
        self.version = "2.0.0"
        logger.info(f"Initializing {self.name} MCP Server v{self.version}")

    # ========================================================================
    # MCP Tools
    # ========================================================================

    def get_working_memory(self, user_id: str, limit: int = 20) -> Dict[str, Any]:
        """
        Get working memory (recent conversations) for a user

        Latency: <10ms (cache hit)

        Args:
            user_id: UUID of the user
            limit: Maximum number of conversations to return

        Returns:
            Recent conversations from cache
        """
        try:
            conversations = cache_service.get_working_memory(user_id, limit)

            return {
                "success": True,
                "count": len(conversations),
                "conversations": conversations,
                "source": "cache" if conversations else "empty",
                "latency_ms": "<10"  # Cache hit latency
            }

        except Exception as e:
            logger.error(f"get_working_memory failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "count": 0,
                "conversations": []
            }

    def search_memories(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Search memories with semantic similarity

        Latency: <10ms (cache hit), 100-300ms (cache miss)

        Args:
            query: Search query text
            user_id: UUID of the user
            limit: Maximum number of results
            threshold: Minimum similarity score

        Returns:
            Search results with relevance scores
        """
        try:
            results = conversation_service.search_fast(
                query=query,
                user_id=user_id,
                limit=limit,
                threshold=threshold
            )

            return {
                "success": True,
                "count": len(results),
                "results": results,
                "query": query,
                "threshold": threshold
            }

        except Exception as e:
            logger.error(f"search_memories failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "count": 0,
                "results": []
            }

    def store_conversation_turn(
        self,
        user_message: str,
        assistant_message: str,
        user_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Store a new conversation turn

        Latency: <100ms

        Args:
            user_message: User's message
            assistant_message: Assistant's response
            user_id: UUID of the user
            session_id: Session identifier

        Returns:
            Stored turn information
        """
        try:
            turn = conversation_service.store_turn(
                user_id=user_id,
                session_id=session_id,
                user_message=user_message,
                assistant_message=assistant_message
            )

            return {
                "success": True,
                "turn_id": str(turn.id),
                "turn_number": turn.turn_number,
                "session_id": turn.session_id,
                "cached": True  # Automatically cached in working memory
            }

        except Exception as e:
            logger.error(f"store_conversation_turn failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    # ========================================================================
    # MCP Resources
    # ========================================================================

    def get_resource(self, uri: str) -> Dict[str, Any]:
        """
        Get MCP resource by URI

        Supported URIs:
        - memory://user/{user_id}/working
        - memory://user/{user_id}/raw
        """
        try:
            if uri.startswith("memory://user/"):
                parts = uri.replace("memory://user/", "").split("/")
                user_id = parts[0]
                resource_type = parts[1] if len(parts) > 1 else "working"

                if resource_type == "working":
                    return self.get_working_memory(user_id)
                elif resource_type == "raw":
                    turns = conversation_service.list_recent(user_id, limit=50)
                    return {
                        "success": True,
                        "count": len(turns),
                        "conversations": [{
                            "id": str(t.id),
                            "user_message": t.user_message,
                            "assistant_message": t.assistant_message,
                            "timestamp": t.timestamp.isoformat(),
                            "session_id": t.session_id,
                            "turn_number": t.turn_number
                        } for t in turns]
                    }

            return {"success": False, "error": f"Unknown resource: {uri}"}

        except Exception as e:
            logger.error(f"get_resource failed: {e}")
            return {"success": False, "error": str(e)}

    # ========================================================================
    # MCP Prompts
    # ========================================================================

    def format_context(self, memories: List[Dict[str, Any]]) -> str:
        """
        Format memories for AI context

        Args:
            memories: List of conversation turns or search results

        Returns:
            Formatted context string
        """
        if not memories:
            return "No relevant memories found."

        context_parts = ["# Relevant Memories\n"]

        for i, memory in enumerate(memories, 1):
            user_msg = memory.get('user_message', '')
            assistant_msg = memory.get('assistant_message', '')
            score = memory.get('score')

            context_parts.append(f"## Memory {i}")
            if score:
                context_parts.append(f"**Relevance:** {score:.2f}")

            context_parts.append(f"\n**User:** {user_msg}")
            context_parts.append(f"**Assistant:** {assistant_msg}\n")

        return "\n".join(context_parts)

    # ========================================================================
    # MCP Protocol Handler
    # ========================================================================

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle MCP request

        Request format:
        {
            "method": "tool_call" | "get_resource" | "format_prompt",
            "params": {...}
        }
        """
        method = request.get("method")
        params = request.get("params", {})

        try:
            if method == "tool_call":
                tool_name = params.get("tool")

                if tool_name == "get_working_memory":
                    return self.get_working_memory(**params.get("arguments", {}))
                elif tool_name == "search_memories":
                    return self.search_memories(**params.get("arguments", {}))
                elif tool_name == "store_conversation_turn":
                    return self.store_conversation_turn(**params.get("arguments", {}))
                else:
                    return {"success": False, "error": f"Unknown tool: {tool_name}"}

            elif method == "get_resource":
                uri = params.get("uri")
                return self.get_resource(uri)

            elif method == "format_prompt":
                memories = params.get("memories", [])
                return {
                    "success": True,
                    "formatted": self.format_context(memories)
                }

            else:
                return {"success": False, "error": f"Unknown method: {method}"}

        except Exception as e:
            logger.error(f"Request handling failed: {e}")
            return {"success": False, "error": str(e)}

    def run_stdio(self):
        """Run MCP server with stdio transport (for Claude Desktop)"""
        logger.info("Starting MCP server with stdio transport...")
        logger.info("Send JSON requests via stdin, receive responses via stdout")

        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                request = json.loads(line.strip())
                response = self.handle_request(request)
                print(json.dumps(response), flush=True)

            except json.JSONDecodeError as e:
                error_response = {"success": False, "error": f"Invalid JSON: {e}"}
                print(json.dumps(error_response), flush=True)
            except KeyboardInterrupt:
                logger.info("MCP server shutting down...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                error_response = {"success": False, "error": str(e)}
                print(json.dumps(error_response), flush=True)


def main():
    """Main entry point"""
    server = MemoryMCPServer()

    # Default to stdio transport (for Claude Desktop)
    server.run_stdio()


if __name__ == "__main__":
    main()
