"""Integration tests for conversation storage and retrieval API.

These tests run against live Docker services.
"""
import uuid

import pytest


def unique(prefix: str = "test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TestConversationStore:
    @pytest.mark.asyncio
    async def test_store_conversation(self, backend_client):
        title = unique("conv")
        resp = await backend_client.post(
            "/api/conversations",
            json={
                "title": title,
                "source": "test",
                "sourceId": "src-1",
                "tags": ["integration"],
                "messages": [
                    {"role": "user", "content": "Hello, how are you?"},
                    {"role": "assistant", "content": "I'm doing well!"},
                ],
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == title
        assert body["source"] == "test"
        assert body["sourceId"] == "src-1"
        assert body["tags"] == ["integration"]
        assert "id" in body
        assert len(body["messages"]) == 2
        assert body["messages"][0]["role"] == "user"
        assert body["messages"][0]["position"] == 0
        assert body["messages"][1]["role"] == "assistant"
        assert body["messages"][1]["position"] == 1

    @pytest.mark.asyncio
    async def test_store_validation_missing_title(self, backend_client):
        resp = await backend_client.post(
            "/api/conversations",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_store_validation_empty_messages(self, backend_client):
        resp = await backend_client.post(
            "/api/conversations",
            json={"title": "Test", "messages": []},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_store_validation_bad_message(self, backend_client):
        resp = await backend_client.post(
            "/api/conversations",
            json={
                "title": "Test",
                "messages": [{"role": "user"}],
            },
        )
        assert resp.status_code == 400


class TestConversationGetById:
    @pytest.mark.asyncio
    async def test_get_by_id(self, backend_client):
        title = unique("getbyid")
        store_resp = await backend_client.post(
            "/api/conversations",
            json={
                "title": title,
                "messages": [
                    {"role": "user", "content": "Question"},
                    {"role": "assistant", "content": "Answer"},
                ],
            },
        )
        conv_id = store_resp.json()["id"]

        resp = await backend_client.get(f"/api/conversations/{conv_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == conv_id
        assert body["title"] == title
        assert len(body["messages"]) == 2

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, backend_client):
        resp = await backend_client.get(
            "/api/conversations/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404


class TestConversationSearch:
    @pytest.mark.asyncio
    async def test_text_search_by_message_content(self, backend_client):
        marker = unique("textsearch")
        await backend_client.post(
            "/api/conversations",
            json={
                "title": "Chat about markers",
                "messages": [
                    {
                        "role": "user",
                        "content": f"I need help with the unique marker {marker} in this sufficiently long message for embedding",
                    },
                    {"role": "assistant", "content": "Sure, I can help!"},
                ],
            },
        )

        resp = await backend_client.get(
            "/api/conversations", params={"query": marker}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(marker in str(c) for c in data["conversations"])

    @pytest.mark.asyncio
    async def test_text_search_by_title(self, backend_client):
        title = unique("titlesearch")
        await backend_client.post(
            "/api/conversations",
            json={
                "title": title,
                "messages": [
                    {
                        "role": "user",
                        "content": f"This is a sufficiently long message about {title} that exceeds the fifty character minimum",
                    },
                ],
            },
        )

        resp = await backend_client.get(
            "/api/conversations", params={"query": title}
        )
        data = resp.json()
        assert data["total"] >= 1
        assert any(c["title"] == title for c in data["conversations"])

    @pytest.mark.asyncio
    async def test_filter_by_tags(self, backend_client):
        tag = unique("tag")
        title = unique("tagged")
        await backend_client.post(
            "/api/conversations",
            json={
                "title": title,
                "tags": [tag],
                "messages": [{"role": "user", "content": "Tagged content"}],
            },
        )
        await backend_client.post(
            "/api/conversations",
            json={
                "title": unique("other"),
                "tags": ["unrelated"],
                "messages": [{"role": "user", "content": "Other content"}],
            },
        )

        resp = await backend_client.get(
            "/api/conversations", params={"tags": tag}
        )
        data = resp.json()
        assert data["total"] >= 1
        assert all(
            tag in c["tags"]
            for c in data["conversations"]
            if c["title"] == title
        )

    @pytest.mark.asyncio
    async def test_limit_parameter(self, backend_client):
        for i in range(3):
            await backend_client.post(
                "/api/conversations",
                json={
                    "title": unique(f"limit-{i}"),
                    "messages": [{"role": "user", "content": f"Content {i}"}],
                },
            )

        resp = await backend_client.get(
            "/api/conversations", params={"limit": "1"}
        )
        data = resp.json()
        assert data["total"] == 1
        assert len(data["conversations"]) == 1
