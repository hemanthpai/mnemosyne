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
        source_id = unique("src")
        resp = await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
                "title": title,
                "source": "test",
                "tags": ["integration"],
                "messages": [
                    {"role": "user", "content": "Hello, how are you?"},
                    {"role": "assistant", "content": "I'm doing well!"},
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == title
        assert body["source"] == "test"
        assert body["sourceId"] == source_id
        assert body["tags"] == ["integration"]
        assert "id" in body
        assert len(body["messages"]) == 2
        assert body["messages"][0]["role"] == "user"
        assert body["messages"][0]["position"] == 0
        assert body["messages"][1]["role"] == "assistant"
        assert body["messages"][1]["position"] == 1

    @pytest.mark.asyncio
    async def test_store_validation_missing_source_id(self, backend_client):
        resp = await backend_client.post(
            "/api/conversations",
            json={
                "title": "No source id",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_store_validation_empty_messages(self, backend_client):
        resp = await backend_client.post(
            "/api/conversations",
            json={"sourceId": unique("src"), "messages": []},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_store_validation_bad_message(self, backend_client):
        resp = await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": unique("src"),
                "messages": [{"role": "user"}],
            },
        )
        assert resp.status_code == 400


class TestConversationUpsert:
    @pytest.mark.asyncio
    async def test_create_via_upsert(self, backend_client):
        source_id = unique("upsert-create")
        resp = await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
                "title": "Created via upsert",
                "messages": [
                    {"role": "user", "content": "First message"},
                    {"role": "assistant", "content": "First response"},
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sourceId"] == source_id
        assert body["title"] == "Created via upsert"
        assert len(body["messages"]) == 2

    @pytest.mark.asyncio
    async def test_append_messages(self, backend_client):
        source_id = unique("upsert-append")

        # Create
        resp1 = await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
                "title": "Append test",
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"},
                ],
            },
        )
        assert resp1.status_code == 200
        conv_id = resp1.json()["id"]

        # Append
        resp2 = await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
                "messages": [
                    {"role": "user", "content": "Follow up question"},
                    {"role": "assistant", "content": "Follow up answer"},
                ],
            },
        )
        assert resp2.status_code == 200
        body = resp2.json()
        assert body["id"] == conv_id
        assert len(body["messages"]) == 4
        assert body["messages"][2]["position"] == 2
        assert body["messages"][2]["content"] == "Follow up question"
        assert body["messages"][3]["position"] == 3

    @pytest.mark.asyncio
    async def test_update_metadata(self, backend_client):
        source_id = unique("upsert-meta")

        # Create with initial metadata
        await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
                "title": "Original title",
                "tags": ["original"],
            },
        )

        # Update metadata
        resp = await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
                "title": "Updated title",
                "tags": ["updated", "new-tag"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Updated title"
        assert body["tags"] == ["updated", "new-tag"]

    @pytest.mark.asyncio
    async def test_source_id_required(self, backend_client):
        resp = await backend_client.post(
            "/api/conversations",
            json={
                "title": "Missing source id",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_minimal_source_id_only(self, backend_client):
        source_id = unique("upsert-minimal")
        resp = await backend_client.post(
            "/api/conversations",
            json={"sourceId": source_id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sourceId"] == source_id
        assert body["title"] == ""


class TestConversationGetById:
    @pytest.mark.asyncio
    async def test_get_by_id(self, backend_client):
        title = unique("getbyid")
        source_id = unique("src")
        store_resp = await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
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
        source_id = unique("src")
        await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
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
        source_id = unique("src")
        await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
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
                "sourceId": unique("src"),
                "title": title,
                "tags": [tag],
                "messages": [{"role": "user", "content": "Tagged content"}],
            },
        )
        await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": unique("src"),
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
                    "sourceId": unique(f"limit-{i}"),
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
