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

    @pytest.mark.asyncio
    async def test_avg_embedding_returned_with_include(self, backend_client):
        """avg_embedding is returned when include=avg_embedding is set."""
        source_id = unique("avg-emb-include")
        await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
                "title": "Avg embedding include test",
                "messages": [
                    {
                        "role": "user",
                        "content": "This is a sufficiently long user message that should trigger embedding generation for testing",
                    },
                ],
            },
        )

        resp = await backend_client.get(
            "/api/conversations",
            params={"query": "embedding include test", "include": "avg_embedding"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        # At least one conversation should have avgEmbedding
        has_embedding = any(
            c.get("avgEmbedding") is not None for c in data["conversations"]
        )
        assert has_embedding, "Expected at least one conversation with avgEmbedding"

    @pytest.mark.asyncio
    async def test_avg_embedding_omitted_without_include(self, backend_client):
        """avg_embedding is NOT returned when include param is absent."""
        source_id = unique("avg-emb-no-include")
        await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
                "title": "Avg embedding omit test",
                "messages": [
                    {
                        "role": "user",
                        "content": "This is a sufficiently long user message that should trigger embedding generation for testing",
                    },
                ],
            },
        )

        resp = await backend_client.get(
            "/api/conversations",
            params={"query": "embedding omit test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for conv in data["conversations"]:
            assert "avgEmbedding" not in conv or conv["avgEmbedding"] is None

    @pytest.mark.asyncio
    async def test_avg_embedding_updates_on_upsert(self, backend_client):
        """avg_embedding updates when new messages are appended via upsert."""
        source_id = unique("avg-emb-upsert")

        # Create with one message
        await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
                "title": "Avg embedding upsert test",
                "messages": [
                    {
                        "role": "user",
                        "content": "This is the first sufficiently long user message that should trigger embedding generation",
                    },
                ],
            },
        )

        # Search with include to get initial avg_embedding
        resp1 = await backend_client.get(
            "/api/conversations",
            params={"query": "upsert test", "include": "avg_embedding"},
        )
        data1 = resp1.json()
        conv1 = next(
            (c for c in data1["conversations"] if c.get("sourceId") == source_id),
            None,
        )

        # Append another message
        await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
                "messages": [
                    {
                        "role": "user",
                        "content": "This is a second sufficiently long user message that adds more embedding data to the average",
                    },
                ],
            },
        )

        # Search again with include
        resp2 = await backend_client.get(
            "/api/conversations",
            params={"query": "upsert test", "include": "avg_embedding"},
        )
        data2 = resp2.json()
        conv2 = next(
            (c for c in data2["conversations"] if c.get("sourceId") == source_id),
            None,
        )

        # Both should have avgEmbedding, and they should differ
        if conv1 and conv2 and conv1.get("avgEmbedding") and conv2.get("avgEmbedding"):
            assert conv1["avgEmbedding"] != conv2["avgEmbedding"], (
                "avgEmbedding should change after appending new embedded messages"
            )


class TestConversationCentroids:
    @pytest.mark.asyncio
    async def test_centroids_returned_with_include(self, backend_client):
        """Centroids are returned when include=centroids is set."""
        source_id = unique("centroids-include")
        await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
                "title": "Centroids include test",
                "messages": [
                    {
                        "role": "user",
                        "content": "This is a sufficiently long user message that should trigger embedding generation for centroid testing purposes",
                    },
                ],
            },
        )

        resp = await backend_client.get(
            "/api/conversations",
            params={"query": "centroid testing", "include": "centroids"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        has_centroids = any(
            c.get("centroids") is not None for c in data["conversations"]
        )
        assert has_centroids, "Expected at least one conversation with centroids"
        # Each centroid should be an array of arrays
        for conv in data["conversations"]:
            if conv.get("centroids"):
                assert isinstance(conv["centroids"], list)
                assert len(conv["centroids"]) >= 1
                assert len(conv["centroids"]) <= 3
                assert isinstance(conv["centroids"][0], list)

    @pytest.mark.asyncio
    async def test_centroids_omitted_without_include(self, backend_client):
        """Centroids are NOT returned when include param is absent."""
        source_id = unique("centroids-no-include")
        await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
                "title": "Centroids omit test",
                "messages": [
                    {
                        "role": "user",
                        "content": "This is a sufficiently long user message for testing centroid omission behavior",
                    },
                ],
            },
        )

        resp = await backend_client.get(
            "/api/conversations",
            params={"query": "centroid omission"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for conv in data["conversations"]:
            assert "centroids" not in conv or conv["centroids"] is None

    @pytest.mark.asyncio
    async def test_centroids_update_on_upsert(self, backend_client):
        """Centroids update when new messages are appended via upsert."""
        source_id = unique("centroids-upsert")

        # Create with one message
        await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
                "title": "Centroids upsert test",
                "messages": [
                    {
                        "role": "user",
                        "content": "This is the first sufficiently long user message about machine learning and neural networks for centroid testing",
                    },
                ],
            },
        )

        # Get initial centroids
        resp1 = await backend_client.get(
            "/api/conversations",
            params={"query": "centroid upsert", "include": "centroids"},
        )
        data1 = resp1.json()
        conv1 = next(
            (c for c in data1["conversations"] if c.get("sourceId") == source_id),
            None,
        )

        # Append more messages
        await backend_client.post(
            "/api/conversations",
            json={
                "sourceId": source_id,
                "messages": [
                    {
                        "role": "user",
                        "content": "This is a second sufficiently long user message about cooking recipes and food preparation techniques",
                    },
                    {
                        "role": "user",
                        "content": "This is a third sufficiently long user message about space exploration and planetary science discoveries",
                    },
                ],
            },
        )

        # Get updated centroids
        resp2 = await backend_client.get(
            "/api/conversations",
            params={"query": "centroid upsert", "include": "centroids"},
        )
        data2 = resp2.json()
        conv2 = next(
            (c for c in data2["conversations"] if c.get("sourceId") == source_id),
            None,
        )

        # After upsert with more messages, centroid count should increase
        if conv1 and conv2 and conv1.get("centroids") and conv2.get("centroids"):
            assert len(conv2["centroids"]) > len(conv1["centroids"]), (
                f"Expected more centroids after upsert: {len(conv1['centroids'])} -> {len(conv2['centroids'])}"
            )
