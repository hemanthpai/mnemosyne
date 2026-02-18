"""Integration tests for Mnemosyne backend API and MCP server.

These tests run against live Docker services.
"""
import os
import uuid

import pytest
import httpx
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession


def unique(prefix: str = "test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ──────────────────────────────────────────────
# Category 1: Backend API tests
# ──────────────────────────────────────────────


class TestBackendHealth:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, backend_client):
        resp = await backend_client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestBackendMemories:
    @pytest.mark.asyncio
    async def test_store_and_fetch_memory(self, backend_client):
        content = unique("memory")
        resp = await backend_client.post(
            "/api/memories",
            json={"content": content, "tags": ["integration"]},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["content"] == content
        assert body["tags"] == ["integration"]
        assert "id" in body

        # Fetch it back
        resp = await backend_client.get(
            "/api/memories", params={"query": content}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(m["content"] == content for m in data["memories"])

    @pytest.mark.asyncio
    async def test_store_memory_validation(self, backend_client):
        resp = await backend_client.post(
            "/api/memories",
            json={"content": "", "tags": []},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_filter_by_tags(self, backend_client):
        tag = unique("tag")
        content = unique("tagged")
        await backend_client.post(
            "/api/memories",
            json={"content": content, "tags": [tag]},
        )
        await backend_client.post(
            "/api/memories",
            json={"content": unique("other"), "tags": ["unrelated"]},
        )

        resp = await backend_client.get(
            "/api/memories", params={"tags": tag}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert all(
            tag in m["tags"]
            for m in data["memories"]
            if m["content"] == content
        )


# ──────────────────────────────────────────────
# Category 2: MCP tool tests
# ──────────────────────────────────────────────


class TestMCPTools:
    @pytest.mark.asyncio
    async def test_mcp_lists_tools(self, mcp_url):
        async with streamablehttp_client(f"{mcp_url}/mcp") as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                assert "store_memory" in tool_names
                assert "fetch_memories" in tool_names

    @pytest.mark.asyncio
    async def test_mcp_store_memory(self, mcp_url):
        content = unique("mcp-store")
        async with streamablehttp_client(f"{mcp_url}/mcp") as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    "store_memory",
                    {"content": content, "tags": ["mcp-test"]},
                )
                text = result.content[0].text
                assert "stored" in text.lower()
                assert "id:" in text.lower()

    @pytest.mark.asyncio
    async def test_mcp_fetch_memories(self, mcp_url):
        content = unique("mcp-fetch")
        async with streamablehttp_client(f"{mcp_url}/mcp") as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                # Store first
                await session.call_tool(
                    "store_memory",
                    {"content": content, "tags": ["mcp-fetch-test"]},
                )
                # Fetch
                result = await session.call_tool(
                    "fetch_memories",
                    {"query": content},
                )
                text = result.content[0].text
                assert content in text


# ──────────────────────────────────────────────
# Category 3: End-to-end tests
# ──────────────────────────────────────────────


class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_store_via_mcp_fetch_via_api(self, mcp_url, backend_client):
        """Store through MCP, verify via direct API call."""
        content = unique("e2e-mcp-to-api")
        async with streamablehttp_client(f"{mcp_url}/mcp") as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                await session.call_tool(
                    "store_memory",
                    {"content": content, "tags": ["e2e"]},
                )

        # Verify via backend API
        resp = await backend_client.get(
            "/api/memories", params={"query": content}
        )
        data = resp.json()
        assert data["total"] >= 1
        assert any(m["content"] == content for m in data["memories"])

    @pytest.mark.asyncio
    async def test_store_via_api_fetch_via_mcp(self, mcp_url, backend_client):
        """Store through API, verify via MCP tool."""
        content = unique("e2e-api-to-mcp")
        await backend_client.post(
            "/api/memories",
            json={"content": content, "tags": ["e2e"]},
        )

        async with streamablehttp_client(f"{mcp_url}/mcp") as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    "fetch_memories",
                    {"query": content},
                )
                text = result.content[0].text
                assert content in text


# ──────────────────────────────────────────────
# Category 4: Semantic search tests (require embedding service)
# ──────────────────────────────────────────────


EMBEDDING_URL = os.environ.get("EMBEDDING_URL", "")


@pytest.mark.skipif(not EMBEDDING_URL, reason="EMBEDDING_URL not set — skipping semantic search tests")
class TestSemanticSearch:
    @pytest.mark.asyncio
    async def test_semantic_similarity_search(self, backend_client):
        """Store a memory and retrieve it with a semantically similar query."""
        content = "The cat sat on the windowsill watching birds outside"
        tag = unique("semantic")
        resp = await backend_client.post(
            "/api/memories",
            json={"content": content, "tags": [tag]},
        )
        assert resp.status_code == 201

        # Search with semantically similar but different words
        resp = await backend_client.get(
            "/api/memories", params={"query": "feline by the window", "tags": tag}
        )
        data = resp.json()
        assert data["total"] >= 1
        assert any(m["content"] == content for m in data["memories"])

    @pytest.mark.asyncio
    async def test_semantic_search_returns_scores(self, backend_client):
        """Vector search results should include similarity scores."""
        content = unique("scored")
        tag = unique("score-test")
        await backend_client.post(
            "/api/memories",
            json={"content": content, "tags": [tag]},
        )

        resp = await backend_client.get(
            "/api/memories", params={"query": content, "tags": tag}
        )
        data = resp.json()
        assert data["total"] >= 1
        # When embeddings are active, results should have scores
        scored = [m for m in data["memories"] if "score" in m]
        assert len(scored) >= 1
        assert all(0 <= m["score"] <= 1 for m in scored)
