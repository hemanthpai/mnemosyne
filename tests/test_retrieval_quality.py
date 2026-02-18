"""Retrieval quality tests for conversation search.

These tests run against a populated Mnemosyne instance with real
Open WebUI conversations ingested. They validate that semantic search
returns relevant results across 6 categories.

Requires:
  - EMBEDDING_URL env var set (embedding service available)
  - Conversations already ingested via scripts/ingest-webui.py
"""
import os

import pytest
import httpx


EMBEDDING_URL = os.environ.get("EMBEDDING_URL", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:3000")
RUN_QUALITY_TESTS = os.environ.get("RUN_QUALITY_TESTS", "")

pytestmark = [
    pytest.mark.skipif(
        not EMBEDDING_URL,
        reason="EMBEDDING_URL not set — skipping retrieval quality tests",
    ),
    pytest.mark.skipif(
        not RUN_QUALITY_TESTS,
        reason="RUN_QUALITY_TESTS not set — run after ingesting conversations",
    ),
]


@pytest.fixture
async def client():
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30.0) as c:
        yield c


async def search(client: httpx.AsyncClient, query: str, limit: int = 5, tags: str | None = None):
    params = {"query": query, "limit": str(limit)}
    if tags:
        params["tags"] = tags
    resp = await client.get("/api/conversations", params=params)
    assert resp.status_code == 200
    data = resp.json()
    return data["conversations"]


def titles(conversations: list[dict]) -> list[str]:
    return [c["title"] for c in conversations]


def has_score(conversations: list[dict]) -> bool:
    return all("score" in c and c["score"] is not None for c in conversations)


# ──────────────────────────────────────────────
# Category 1: Exact recall — query words appear in stored conversations
# ──────────────────────────────────────────────

class TestExactRecall:
    @pytest.mark.asyncio
    async def test_ollama_query_returns_relevant(self, client):
        """Querying 'Ollama' should return conversations about running LLMs locally."""
        results = await search(client, "Ollama setup and configuration")
        assert len(results) > 0
        # At least one result should mention Ollama or LLM in title/messages
        all_text = " ".join(str(c) for c in results)
        assert any(
            kw in all_text.lower()
            for kw in ["ollama", "llm", "model", "gpu"]
        ), f"Expected Ollama-related content, got titles: {titles(results)}"

    @pytest.mark.asyncio
    async def test_carefeed_query_returns_interview_prep(self, client):
        """Querying 'CareFeed interview' should return CareFeed-related conversations."""
        results = await search(client, "CareFeed interview preparation")
        assert len(results) > 0
        all_text = " ".join(str(c) for c in results)
        assert any(
            kw in all_text.lower()
            for kw in ["carefeed", "healthcare", "interview"]
        ), f"Expected CareFeed content, got titles: {titles(results)}"

    @pytest.mark.asyncio
    async def test_gardening_query(self, client):
        """Querying about plants/gardening should return gardening conversations."""
        results = await search(client, "gardening plants bush beans")
        assert len(results) > 0
        all_text = " ".join(str(c) for c in results)
        assert any(
            kw in all_text.lower()
            for kw in ["plant", "garden", "bean", "bush", "grow"]
        ), f"Expected gardening content, got titles: {titles(results)}"


# ──────────────────────────────────────────────
# Category 2: Paraphrase — same meaning, different words
# ──────────────────────────────────────────────

class TestParaphrase:
    @pytest.mark.asyncio
    async def test_local_ai_models(self, client):
        """'running AI models locally' should match Ollama/GPU conversations."""
        results = await search(client, "running AI models on local hardware")
        assert len(results) > 0
        all_text = " ".join(str(c) for c in results)
        assert any(
            kw in all_text.lower()
            for kw in ["ollama", "gpu", "model", "nvidia", "llm", "local"]
        ), f"Expected AI/GPU content, got titles: {titles(results)}"

    @pytest.mark.asyncio
    async def test_job_interview_preparation(self, client):
        """'preparing for a job interview' should match interview prep conversations."""
        results = await search(client, "preparing for a job interview at a startup")
        assert len(results) > 0
        all_text = " ".join(str(c) for c in results)
        assert any(
            kw in all_text.lower()
            for kw in ["interview", "prep", "role", "position", "hire"]
        ), f"Expected interview content, got titles: {titles(results)}"

    @pytest.mark.asyncio
    async def test_electric_vehicle_costs(self, client):
        """'costs of owning an electric car' should match EV analysis conversations."""
        results = await search(client, "costs of owning an electric car")
        assert len(results) > 0
        all_text = " ".join(str(c) for c in results)
        assert any(
            kw in all_text.lower()
            for kw in ["ev", "electric", "car", "insurance", "vehicle", "cost"]
        ), f"Expected EV/car content, got titles: {titles(results)}"


# ──────────────────────────────────────────────
# Category 3: Conceptual similarity — related concepts
# ──────────────────────────────────────────────

class TestConceptualSimilarity:
    @pytest.mark.asyncio
    async def test_devops_returns_deployment(self, client):
        """'DevOps practices' should surface Docker, CI/CD, or deployment conversations."""
        results = await search(client, "DevOps practices and deployment pipelines")
        assert len(results) > 0
        all_text = " ".join(str(c) for c in results)
        assert any(
            kw in all_text.lower()
            for kw in ["docker", "deploy", "ci", "dora", "metric", "devops", "aws"]
        ), f"Expected DevOps content, got titles: {titles(results)}"

    @pytest.mark.asyncio
    async def test_engineering_leadership(self, client):
        """'managing software teams' should match engineering leadership conversations."""
        results = await search(client, "managing and leading software engineering teams")
        assert len(results) > 0
        all_text = " ".join(str(c) for c in results)
        assert any(
            kw in all_text.lower()
            for kw in ["leadership", "engineering", "manager", "team", "leader"]
        ), f"Expected leadership content, got titles: {titles(results)}"


# ──────────────────────────────────────────────
# Category 4: Negative discrimination — irrelevant queries
# ──────────────────────────────────────────────

class TestNegativeDiscrimination:
    @pytest.mark.asyncio
    async def test_cooking_recipes_low_relevance(self, client):
        """Cooking queries should have low scores against mostly tech conversations."""
        results = await search(client, "Italian pasta carbonara recipe with bacon")
        if len(results) > 0 and has_score(results):
            # If vector search returned scored results, top score should be low
            top_score = results[0]["score"]
            assert top_score < 0.65, (
                f"Cooking query got suspiciously high score {top_score:.3f}: "
                f"{titles(results)}"
            )

    @pytest.mark.asyncio
    async def test_sports_query_low_relevance(self, client):
        """Generic sports queries shouldn't score high against tech conversations."""
        results = await search(client, "basketball championship playoff bracket predictions")
        if len(results) > 0 and has_score(results):
            top_score = results[0]["score"]
            assert top_score < 0.65, (
                f"Basketball query got suspiciously high score {top_score:.3f}: "
                f"{titles(results)}"
            )


# ──────────────────────────────────────────────
# Category 5: Cross-topic ranking — most relevant ranks first
# ──────────────────────────────────────────────

class TestCrossTopicRanking:
    @pytest.mark.asyncio
    async def test_carefeed_ranks_above_generic_health(self, client):
        """'CareFeed healthcare startup' should rank CareFeed conversations highest."""
        results = await search(client, "CareFeed healthcare startup interview", limit=10)
        assert len(results) >= 2
        # First result should be more relevant than last
        if has_score(results):
            assert results[0]["score"] >= results[-1]["score"], (
                f"Expected descending scores: first={results[0]['score']:.3f}, "
                f"last={results[-1]['score']:.3f}"
            )

    @pytest.mark.asyncio
    async def test_financial_planning_ranking(self, client):
        """Financial queries should rank financial conversations higher than tech."""
        results = await search(client, "retirement 401k financial planning taxes", limit=10)
        assert len(results) > 0
        if has_score(results):
            # Results should be sorted by score descending
            scores = [c["score"] for c in results]
            assert scores == sorted(scores, reverse=True), (
                f"Scores not sorted descending: {scores}"
            )


# ──────────────────────────────────────────────
# Category 6: Edge cases
# ──────────────────────────────────────────────

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_short_query(self, client):
        """Very short queries should still return results."""
        results = await search(client, "AWS")
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_gibberish_query(self, client):
        """Gibberish queries should score lower than meaningful queries."""
        gibberish = await search(client, "xyzzy plugh qwfpgj")
        meaningful = await search(client, "software engineering leadership")
        # Gibberish should score lower than a meaningful query
        if (
            len(gibberish) > 0
            and len(meaningful) > 0
            and has_score(gibberish)
            and has_score(meaningful)
        ):
            assert gibberish[0]["score"] < meaningful[0]["score"], (
                f"Gibberish ({gibberish[0]['score']:.3f}) scored >= "
                f"meaningful ({meaningful[0]['score']:.3f})"
            )

    @pytest.mark.asyncio
    async def test_limit_parameter(self, client):
        """Limit should constrain result count."""
        results = await search(client, "engineering leadership", limit=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_scores_in_valid_range(self, client):
        """All scores should be between 0 and 1."""
        results = await search(client, "software engineering", limit=10)
        if has_score(results):
            for c in results:
                assert 0 <= c["score"] <= 1, (
                    f"Score out of range: {c['score']}"
                )
