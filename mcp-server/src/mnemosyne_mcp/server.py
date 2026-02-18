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
