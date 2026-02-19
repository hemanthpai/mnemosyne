from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import httpx
from mcp.server.fastmcp import FastMCP, Context

from .config import BACKEND_URL, MCP_PORT


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    async with httpx.AsyncClient(base_url=BACKEND_URL) as client:
        yield {"client": client}


mcp = FastMCP("mnemosyne", lifespan=lifespan, host="0.0.0.0", port=MCP_PORT)


def _get_client(ctx: Context) -> httpx.AsyncClient:
    return ctx.request_context.lifespan_context["client"]


@mcp.tool()
async def store_memory(
    content: str, tags: list[str] | None = None, ctx: Context = None
) -> str:
    """Store a memory for long-term recall.

    Args:
        content: The text content of the memory to store.
        tags: Optional list of tags to categorize the memory.
    """
    client = _get_client(ctx)
    payload: dict = {"content": content}
    if tags is not None:
        payload["tags"] = tags
    response = await client.post("/api/memories", json=payload)
    if response.status_code == 201:
        data = response.json()
        return f"Memory stored (id: {data['id']})"
    else:
        return f"Error storing memory: {response.text}"


@mcp.tool()
async def fetch_memories(
    query: str | None = None,
    tags: list[str] | None = None,
    ctx: Context = None,
) -> str:
    """Fetch memories from long-term storage.

    Args:
        query: Optional text to search for in memory content.
        tags: Optional list of tags to filter memories by.
    """
    client = _get_client(ctx)
    params: dict = {}
    if query is not None:
        params["query"] = query
    if tags is not None:
        params["tags"] = ",".join(tags)
    response = await client.get("/api/memories", params=params)
    if response.status_code == 200:
        data = response.json()
        memories = data["memories"]
        if not memories:
            return "No memories found."
        lines = []
        for m in memories:
            tag_str = f" [{', '.join(m['tags'])}]" if m["tags"] else ""
            lines.append(f"- {m['content']}{tag_str} (id: {m['id']})")
        return f"Found {data['total']} memories:\n" + "\n".join(lines)
    else:
        return f"Error fetching memories: {response.text}"


@mcp.tool()
async def store_conversation(
    source_id: str,
    messages: list[dict] | None = None,
    title: str | None = None,
    tags: list[str] | None = None,
    source: str | None = None,
    ctx: Context = None,
) -> str:
    """Store or update a conversation by source ID (upsert).

    Creates a new conversation if the source_id doesn't exist, or appends
    messages and updates metadata if it does.

    Args:
        source_id: The caller's unique ID for this conversation.
        messages: Optional list of message dicts with 'role' and 'content' keys.
        title: Optional conversation title.
        tags: Optional list of tags to categorize the conversation.
        source: Optional source identifier (e.g. 'open-webui', 'n8n').
    """
    client = _get_client(ctx)
    payload: dict = {"sourceId": source_id}
    if messages is not None:
        payload["messages"] = messages
    if title is not None:
        payload["title"] = title
    if tags is not None:
        payload["tags"] = tags
    if source is not None:
        payload["source"] = source
    response = await client.post("/api/conversations", json=payload)
    if response.status_code == 200:
        data = response.json()
        msg_count = len(data.get("messages", []))
        return f"Conversation stored (id: {data['id']}, messages: {msg_count})"
    else:
        return f"Error storing conversation: {response.text}"


@mcp.tool()
async def search_conversations(
    query: str | None = None,
    tags: list[str] | None = None,
    limit: int | None = None,
    ctx: Context = None,
) -> str:
    """Search conversations by text query and/or tags.

    Args:
        query: Optional text to search for in conversation messages and titles.
        tags: Optional list of tags to filter conversations by.
        limit: Optional maximum number of results to return.
    """
    client = _get_client(ctx)
    params: dict = {}
    if query is not None:
        params["query"] = query
    if tags is not None:
        params["tags"] = ",".join(tags)
    if limit is not None:
        params["limit"] = str(limit)
    response = await client.get("/api/conversations", params=params)
    if response.status_code == 200:
        data = response.json()
        conversations = data["conversations"]
        if not conversations:
            return "No conversations found."
        lines = []
        for c in conversations:
            tag_str = f" [{', '.join(c['tags'])}]" if c.get("tags") else ""
            score_str = f" (score: {c['score']:.3f})" if c.get("score") is not None else ""
            lines.append(f"- {c.get('title', 'Untitled')}{tag_str}{score_str} (id: {c['id']})")
        return f"Found {data['total']} conversations:\n" + "\n".join(lines)
    else:
        return f"Error searching conversations: {response.text}"


@mcp.tool()
async def get_conversation(
    id: str,
    ctx: Context = None,
) -> str:
    """Get a conversation by its internal ID, including all messages.

    Args:
        id: The internal UUID of the conversation.
    """
    client = _get_client(ctx)
    response = await client.get(f"/api/conversations/{id}")
    if response.status_code == 200:
        data = response.json()
        tag_str = f" [{', '.join(data['tags'])}]" if data.get("tags") else ""
        header = f"# {data.get('title', 'Untitled')}{tag_str}\n"
        messages = data.get("messages", [])
        if not messages:
            return header + "No messages."
        lines = [header]
        for msg in messages:
            lines.append(f"**{msg['role']}**: {msg['content']}")
        return "\n".join(lines)
    elif response.status_code == 404:
        return "Conversation not found."
    else:
        return f"Error fetching conversation: {response.text}"


def main():
    import os
    import sys

    transport = os.environ.get("MCP_TRANSPORT", "").lower()
    if transport == "stdio" or "--stdio" in sys.argv:
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
