#!/usr/bin/env python3
"""
Mnemosyne MCP Server (AI-Intuitive Design)

FastMCP-based server following MCP 2025 best practices for AI usability:
- Natural, action-oriented tool names (recall, remember, what_do_i_know)
- Clear WHEN guidance in descriptions (not just WHAT)
- Minimal parameters (auto-infer user_id, session_id)
- Higher-level abstractions (not 1:1 API mapping)

Supports dual transport:
- stdio: Claude Desktop, Cursor, Cline, Continue
- HTTP: Open WebUI, Home Assistant, web clients

Based on:
- https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- https://www.marktechpost.com/2025/07/23/7-mcp-server-best-practices-for-scalable-ai-integrations-in-2025/
"""

import os
import sys
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

# Add Django project to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'memory_service.settings')
import django
django.setup()

from fastmcp import FastMCP, Context
from memories.cache_service import cache_service
from memories.conversation_service import conversation_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(
    name="mnemosyne"
)

# ==============================================================================
# Context Management - Auto-infer user_id from MCP context
# ==============================================================================

def get_user_id_from_context(ctx: Optional[Context] = None) -> str:
    """
    Extract user_id from MCP context.

    In production, this would come from the MCP client's authentication.
    For now, we'll use a default or allow override via meta.
    """
    if ctx and hasattr(ctx, 'meta') and 'user_id' in ctx.meta:
        return ctx.meta['user_id']

    # Fallback: Use a default user for demo/testing
    # In production, this should be required from client
    return "00000000-0000-0000-0000-000000000001"

def get_session_id_from_context(ctx: Optional[Context] = None) -> str:
    """
    Extract or generate session_id from MCP context.

    In production MCP clients, this would come from conversation context.
    """
    if ctx and hasattr(ctx, 'meta') and 'session_id' in ctx.meta:
        return ctx.meta['session_id']

    # Fallback: Generate a session ID based on timestamp
    # In production, client should provide this
    return f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

# ==============================================================================
# Tools - Redesigned for AI Intuitiveness
# ==============================================================================

@mcp.tool(
    description="""
    Recall relevant information from past conversations.

    **WHEN TO USE**: Before answering ANY question that might benefit from context
    - User asks about their preferences: "What's my favorite...?"
    - User references past conversations: "Remember when we talked about...?"
    - User asks for recommendations: "What should I...?" (check their preferences)
    - Any time you need context about the user to give a personalized response

    **EXAMPLES**:
    - User: "What's my favorite coffee order?" → Call this first!
    - User: "Recommend a movie" → Check if they've mentioned preferences
    - User: "What did we discuss last week?" → This is the tool!

    **RETURNS**: Relevant past conversations and extracted knowledge
    """
)
def recall(
    query: str,
    max_results: int = 5,
    include_knowledge: bool = True
) -> Dict[str, Any]:
    """
    Search through past conversations and knowledge to find relevant context.

    Args:
        query: What to search for (use the user's question or topic)
        max_results: How many results to return (default: 5)
        include_knowledge: Also search extracted knowledge, not just conversations (default: True)

    Returns:
        Relevant memories with context
    """
    try:
        user_id = get_user_id_from_context()

        # Search conversations (fast mode for responsiveness)
        results = conversation_service.search_fast(
            query=query,
            user_id=user_id,
            limit=max_results,
            threshold=0.4  # Lower threshold for better recall
        )

        response = {
            "found": len(results) > 0,
            "count": len(results),
            "conversations": results
        }

        # Optionally search knowledge graph too
        if include_knowledge:
            try:
                from memories.graph_service import graph_service
                knowledge = graph_service.search_notes(
                    query=query,
                    user_id=user_id,
                    limit=max_results,
                    threshold=0.4
                )
                response["knowledge"] = knowledge
                response["knowledge_count"] = len(knowledge)
            except Exception as e:
                logger.warning(f"Knowledge search failed: {e}")
                response["knowledge"] = []

        return response

    except Exception as e:
        logger.error(f"recall failed: {e}")
        return {
            "found": False,
            "error": str(e),
            "conversations": [],
            "knowledge": []
        }


@mcp.tool(
    description="""
    Remember important information from the current conversation.

    **WHEN TO USE**: After the user shares something important that should be remembered
    - User states a preference: "I prefer...", "I like...", "I don't like..."
    - User shares personal information: "I live in...", "My job is..."
    - User mentions a goal or aspiration: "I want to...", "I'm learning..."
    - User gives feedback: "That worked well", "Don't do that again"

    **EXAMPLES**:
    - User: "I'm allergic to peanuts" → Remember this!
    - User: "I prefer dark mode in all apps" → Remember this!
    - User: "My birthday is June 15th" → Remember this!

    **AUTOMATIC**: Extraction and knowledge graph building happen in background
    You just need to call this to mark it as important to remember.
    """
)
def remember(
    what_user_said: str,
    assistant_response: str = ""
) -> Dict[str, Any]:
    """
    Store important information from the conversation for future recall.

    Args:
        what_user_said: The important thing the user said
        assistant_response: Your response (optional, helps with context)

    Returns:
        Confirmation that it was remembered
    """
    try:
        user_id = get_user_id_from_context()
        session_id = get_session_id_from_context()

        # If no assistant response provided, use a generic one
        if not assistant_response:
            assistant_response = "Noted and remembered."

        turn = conversation_service.store_turn(
            user_id=user_id,
            session_id=session_id,
            user_message=what_user_said,
            assistant_message=assistant_response
        )

        return {
            "remembered": True,
            "message": "I'll remember that. Knowledge extraction will happen automatically in the background.",
            "turn_id": str(turn.id)
        }

    except Exception as e:
        logger.error(f"remember failed: {e}")
        return {
            "remembered": False,
            "error": str(e)
        }


@mcp.tool(
    description="""
    Get a quick overview of what you know about the user.

    **WHEN TO USE**: When you need to understand the user's context quickly
    - At the start of a new conversation
    - When unsure if you have relevant context
    - To personalize your responses based on known preferences

    **EXAMPLES**:
    - New conversation starts → Check what you know
    - User asks something vague → Check their preferences/context
    - Before making recommendations → See what they like/dislike

    **RETURNS**: Recent context + key knowledge about the user
    """
)
def what_do_i_know() -> Dict[str, Any]:
    """
    Get a summary of recent context and key knowledge about the user.

    Returns:
        Summary of recent conversations and important facts
    """
    try:
        user_id = get_user_id_from_context()

        # Get recent conversations from cache (fast)
        recent = cache_service.get_working_memory(user_id, limit=10)

        # Get top knowledge from notes
        from memories.models import AtomicNote
        from collections import defaultdict

        notes = AtomicNote.objects.filter(user_id=user_id).order_by('-importance_score')[:20]

        # Group notes by type for easy scanning
        knowledge_by_type = defaultdict(list)
        for note in notes:
            knowledge_by_type[note.note_type].append({
                'content': note.content,
                'confidence': note.confidence
            })

        return {
            "has_context": len(recent) > 0 or len(notes) > 0,
            "recent_conversations": len(recent),
            "knowledge_facts": len(notes),
            "knowledge_summary": dict(knowledge_by_type),
            "message": "Use 'recall' with specific queries to get detailed information"
        }

    except Exception as e:
        logger.error(f"what_do_i_know failed: {e}")
        return {
            "has_context": False,
            "error": str(e)
        }


# ==============================================================================
# Resources - Data streams (unchanged, these are good)
# ==============================================================================

@mcp.resource("memory://recent")
def get_recent_context() -> str:
    """
    Stream of recent conversations (working memory).

    Use this resource to quickly scan recent context.
    """
    try:
        user_id = get_user_id_from_context()
        conversations = cache_service.get_working_memory(user_id, limit=20)

        if not conversations:
            return "No recent conversations."

        output = ["Recent conversation history:\n"]
        for i, conv in enumerate(conversations, 1):
            output.append(f"\n{i}. {conv.get('user_message', '')[:80]}...")

        return "\n".join(output)

    except Exception as e:
        return f"Error: {str(e)}"


@mcp.resource("memory://knowledge")
def get_knowledge_summary() -> str:
    """
    Stream of extracted knowledge (facts known about the user).

    Use this resource to see what facts have been learned.
    """
    try:
        user_id = get_user_id_from_context()
        from memories.models import AtomicNote
        from collections import defaultdict

        notes = AtomicNote.objects.filter(user_id=user_id).order_by('-importance_score')[:30]

        if not notes:
            return "No knowledge extracted yet."

        # Group by type
        notes_by_type = defaultdict(list)
        for note in notes:
            notes_by_type[note.note_type].append(note.content)

        output = ["Extracted Knowledge:\n"]
        for note_type, contents in sorted(notes_by_type.items()):
            output.append(f"\n{note_type.upper()}:")
            for content in contents[:5]:  # Limit per type
                output.append(f"  - {content}")

        return "\n".join(output)

    except Exception as e:
        return f"Error: {str(e)}"


# ==============================================================================
# Prompts - Redesigned to guide proper tool usage
# ==============================================================================

@mcp.prompt(
    description="Template for starting a conversation with memory context"
)
def start_conversation_with_memory() -> str:
    """
    Guides the AI to check for context at conversation start.
    """
    return """You are an AI assistant with long-term memory via Mnemosyne.

At the START of EVERY conversation:
1. Call the 'what_do_i_know' tool to check if you have context about this user
2. If you have context, personalize your greeting based on what you know
3. If you don't have context, introduce yourself and ask questions to learn about them

IMPORTANT: Don't mention "I'm checking my memory" - just naturally use what you find.

Example:
- If you know they're a developer in Seattle who likes coffee, greet them accordingly
- If you know nothing, simply say hi and be ready to learn
"""


@mcp.prompt(
    description="Template for answering questions with memory"
)
def answer_with_memory(user_question: str) -> str:
    """
    Guides the AI to search memory before answering.

    Args:
        user_question: The question the user asked
    """
    return f"""The user asked: "{user_question}"

BEFORE answering, follow these steps:
1. Call 'recall' tool with the user's question to check for relevant context
2. Review what you find - look for:
   - Direct answers to their question
   - Related preferences or past discussions
   - Context that affects how you should answer
3. Answer the question using the context you found
4. If you found no relevant context, answer based on general knowledge

REMEMBER: Always check memory first! The user expects you to remember past conversations.
"""


@mcp.prompt(
    description="Template for when the user shares something important"
)
def user_shared_something_important(what_they_said: str) -> str:
    """
    Guides the AI to remember important information.

    Args:
        what_they_said: What the user just shared
    """
    return f"""The user just said: "{what_they_said}"

Evaluate if this is important to remember for future conversations:

REMEMBER IF:
- It's a preference (they like/dislike something)
- It's personal info (location, job, hobbies, goals)
- It's feedback (this worked/didn't work)
- They explicitly said "remember this" or similar

If it IS important:
1. Call 'remember' tool with what they said
2. Acknowledge naturally (don't say "I'll add this to my memory")
3. Continue the conversation

If it's NOT important (just casual chat):
- Don't call remember
- Just continue naturally

Examples of IMPORTANT:
- "I'm vegan"
- "I live in Tokyo"
- "I prefer you to be concise"
- "My birthday is in March"

Examples of NOT important:
- "How are you today?"
- "Thanks"
- "Okay"
"""


# ==============================================================================
# Main - Handle both transports
# ==============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mnemosyne MCP Server v2 (AI-Intuitive)")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport protocol"
    )
    parser.add_argument("--host", default="0.0.0.0", help="HTTP host")
    parser.add_argument("--port", type=int, default=3000, help="HTTP port")

    args = parser.parse_args()

    if args.transport == "stdio":
        logger.info("Starting Mnemosyne MCP Server v2 (stdio)")
        logger.info("AI-Intuitive design: recall, remember, what_do_i_know")
        mcp.run(transport="stdio")
    else:
        logger.info(f"Starting Mnemosyne MCP Server v2 (HTTP) on {args.host}:{args.port}")
        logger.info("AI-Intuitive design: recall, remember, what_do_i_know")
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
