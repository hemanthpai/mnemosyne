import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock

from mnemosyne_mcp.server import (
    store_memory,
    fetch_memories,
    store_conversation,
    search_conversations,
    get_conversation,
)


def make_response(status_code: int, json_data: dict) -> httpx.Response:
    """Create a real httpx.Response for testing."""
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "http://test"),
    )


def make_ctx(client: AsyncMock) -> MagicMock:
    """Create a mock Context with lifespan_context containing the client."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"client": client}
    return ctx


@pytest.fixture
def client():
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def ctx(client):
    return make_ctx(client)


@pytest.mark.asyncio
async def test_store_memory_success(client, ctx):
    client.post.return_value = make_response(
        201,
        {
            "id": "abc-123",
            "content": "Test memory",
            "tags": ["test"],
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
        },
    )

    result = await store_memory(content="Test memory", tags=["test"], ctx=ctx)
    assert "abc-123" in result
    assert "stored" in result.lower()
    client.post.assert_called_once_with(
        "/api/memories", json={"content": "Test memory", "tags": ["test"]}
    )


@pytest.mark.asyncio
async def test_store_memory_without_tags(client, ctx):
    client.post.return_value = make_response(
        201,
        {
            "id": "abc-456",
            "content": "No tags",
            "tags": [],
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
        },
    )

    result = await store_memory(content="No tags", ctx=ctx)
    assert "abc-456" in result
    client.post.assert_called_once_with(
        "/api/memories", json={"content": "No tags"}
    )


@pytest.mark.asyncio
async def test_store_memory_error(client, ctx):
    client.post.return_value = make_response(
        400,
        {"error": "content is required and must be a non-empty string"},
    )

    result = await store_memory(content="", ctx=ctx)
    assert "error" in result.lower()


@pytest.mark.asyncio
async def test_fetch_memories_success(client, ctx):
    client.get.return_value = make_response(
        200,
        {
            "memories": [
                {
                    "id": "abc-123",
                    "content": "Test memory",
                    "tags": ["test"],
                    "createdAt": "2026-01-01T00:00:00Z",
                    "updatedAt": "2026-01-01T00:00:00Z",
                }
            ],
            "total": 1,
        },
    )

    result = await fetch_memories(query="test", ctx=ctx)
    assert "1 memories" in result
    assert "Test memory" in result
    client.get.assert_called_once_with("/api/memories", params={"query": "test"})


@pytest.mark.asyncio
async def test_fetch_memories_with_tags(client, ctx):
    client.get.return_value = make_response(
        200,
        {"memories": [], "total": 0},
    )

    result = await fetch_memories(tags=["work", "project"], ctx=ctx)
    assert "no memories found" in result.lower()
    client.get.assert_called_once_with(
        "/api/memories", params={"tags": "work,project"}
    )


@pytest.mark.asyncio
async def test_fetch_memories_no_params(client, ctx):
    client.get.return_value = make_response(
        200,
        {"memories": [], "total": 0},
    )

    result = await fetch_memories(ctx=ctx)
    assert "no memories found" in result.lower()
    client.get.assert_called_once_with("/api/memories", params={})


@pytest.mark.asyncio
async def test_fetch_memories_error(client, ctx):
    client.get.return_value = make_response(500, {"error": "Internal server error"})

    result = await fetch_memories(ctx=ctx)
    assert "error" in result.lower()


# --- store_conversation tests ---


@pytest.mark.asyncio
async def test_store_conversation_success(client, ctx):
    client.post.return_value = make_response(
        200,
        {
            "id": "conv-123",
            "title": "Test conversation",
            "source": "test",
            "sourceId": "src-1",
            "tags": ["test"],
            "messages": [
                {"id": "m1", "role": "user", "content": "Hello", "position": 0},
                {"id": "m2", "role": "assistant", "content": "Hi!", "position": 1},
            ],
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
        },
    )

    result = await store_conversation(
        source_id="src-1",
        title="Test conversation",
        messages=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ],
        tags=["test"],
        ctx=ctx,
    )
    assert "conv-123" in result
    assert "messages: 2" in result
    client.post.assert_called_once_with(
        "/api/conversations",
        json={
            "sourceId": "src-1",
            "title": "Test conversation",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ],
            "tags": ["test"],
        },
    )


@pytest.mark.asyncio
async def test_store_conversation_minimal(client, ctx):
    client.post.return_value = make_response(
        200,
        {
            "id": "conv-456",
            "title": "",
            "source": "",
            "sourceId": "src-2",
            "tags": [],
            "messages": [],
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
        },
    )

    result = await store_conversation(source_id="src-2", ctx=ctx)
    assert "conv-456" in result
    client.post.assert_called_once_with(
        "/api/conversations", json={"sourceId": "src-2"}
    )


@pytest.mark.asyncio
async def test_store_conversation_error(client, ctx):
    client.post.return_value = make_response(
        400,
        {"error": "sourceId is required and must be a non-empty string"},
    )

    result = await store_conversation(source_id="", ctx=ctx)
    assert "error" in result.lower()


# --- search_conversations tests ---


@pytest.mark.asyncio
async def test_search_conversations_success(client, ctx):
    client.get.return_value = make_response(
        200,
        {
            "conversations": [
                {
                    "id": "conv-1",
                    "title": "TypeScript discussion",
                    "tags": ["dev"],
                    "score": 0.85,
                },
                {
                    "id": "conv-2",
                    "title": "Python tips",
                    "tags": [],
                    "score": 0.72,
                },
            ],
            "total": 2,
        },
    )

    result = await search_conversations(query="programming", ctx=ctx)
    assert "2 conversations" in result
    assert "TypeScript discussion" in result
    assert "0.850" in result
    assert "conv-1" in result
    client.get.assert_called_once_with(
        "/api/conversations", params={"query": "programming"}
    )


@pytest.mark.asyncio
async def test_search_conversations_empty(client, ctx):
    client.get.return_value = make_response(
        200, {"conversations": [], "total": 0}
    )

    result = await search_conversations(query="nonexistent", ctx=ctx)
    assert "no conversations found" in result.lower()


@pytest.mark.asyncio
async def test_search_conversations_with_tags(client, ctx):
    client.get.return_value = make_response(
        200, {"conversations": [], "total": 0}
    )

    result = await search_conversations(tags=["work", "project"], ctx=ctx)
    assert "no conversations found" in result.lower()
    client.get.assert_called_once_with(
        "/api/conversations", params={"tags": "work,project"}
    )


# --- get_conversation tests ---


@pytest.mark.asyncio
async def test_get_conversation_success(client, ctx):
    client.get.return_value = make_response(
        200,
        {
            "id": "conv-1",
            "title": "Test Chat",
            "tags": ["dev"],
            "messages": [
                {"role": "user", "content": "What is Python?"},
                {"role": "assistant", "content": "Python is a programming language."},
            ],
        },
    )

    result = await get_conversation(id="conv-1", ctx=ctx)
    assert "Test Chat" in result
    assert "**user**: What is Python?" in result
    assert "**assistant**: Python is a programming language." in result
    client.get.assert_called_once_with("/api/conversations/conv-1")


@pytest.mark.asyncio
async def test_get_conversation_not_found(client, ctx):
    client.get.return_value = make_response(
        404, {"error": "conversation not found"}
    )

    result = await get_conversation(id="nonexistent", ctx=ctx)
    assert "not found" in result.lower()
