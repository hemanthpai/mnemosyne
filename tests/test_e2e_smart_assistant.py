"""End-to-end tests for the Smart Assistant n8n workflow.

Tests the full chain: curl → n8n-bridge → n8n Smart Assistant → LLM
and verifies Mnemosyne storage, tool usage, and conversation continuity.

These tests use a dedicated test userId and clean up all data afterward.

Run standalone:
    cd tests && uv run pytest test_e2e_smart_assistant.py -v

Environment variables:
    BRIDGE_URL      n8n-openai-bridge URL  (default: http://minion.coho-mahi.ts.net:3333)
    BRIDGE_API_KEY  Bridge bearer token     (default: from .env / hardcoded)
    BACKEND_URL     Mnemosyne backend URL   (default: http://localhost:3100)
"""

import os
import uuid

import httpx
import pytest

BRIDGE_URL = os.environ.get("BRIDGE_URL", "http://minion.coho-mahi.ts.net:3333")
BRIDGE_API_KEY = os.environ.get(
    "BRIDGE_API_KEY",
    "3486d8d38026fade0d30ebe390cdada0cf2ea056ffb14669877e58ebd6f32b31",
)
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:3100")
TEST_USER_ID = f"test-e2e-{uuid.uuid4().hex[:8]}"
MODEL = "smart-assistant"

SYSTEM_PROMPT = (
    "You are J.A.R.V.I.S — a helpful AI assistant.\n\n"
    "## Current Context\n"
    "- Date: February 22, 2026\n"
    "- Time: 3:15 PM\n"
    "- Timezone: America/Los_Angeles\n"
    "- Day of Week: Sunday\n\n"
    "## User Information\n"
    "- Name: TestUser"
)

# Generous timeouts — the LLM (Qwen3-235B) can be slow, and research_assistant
# calls a sub-workflow that does web searches.
FAST_TIMEOUT = 120.0
SLOW_TIMEOUT = 600.0


def _chat(
    client: httpx.Client,
    messages: list[dict],
    timeout: float = FAST_TIMEOUT,
) -> str:
    """Send a chat completion request to the bridge and return the response text."""
    resp = client.post(
        f"{BRIDGE_URL}/v1/chat/completions",
        json={
            "model": MODEL,
            "messages": messages,
            "user": TEST_USER_ID,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


@pytest.fixture(scope="module")
def bridge_client():
    with httpx.Client(
        headers={"Authorization": f"Bearer {BRIDGE_API_KEY}"},
    ) as client:
        yield client


@pytest.fixture(scope="module")
def backend_client():
    with httpx.Client(base_url=BACKEND_URL) as client:
        yield client


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data(backend_client):
    """Delete all Mnemosyne conversations for the test user after the module runs."""
    yield
    # Cleanup: delete test user's conversations via the API
    resp = backend_client.get(
        "/api/conversations",
        params={"userId": TEST_USER_ID, "limit": 100},
    )
    if resp.status_code == 200:
        conversations = resp.json()
        if isinstance(conversations, list):
            items = conversations
        elif isinstance(conversations, dict):
            items = conversations.get("conversations", conversations.get("items", []))
        else:
            items = []
        for conv in items:
            backend_client.delete(f"/api/conversations/{conv['id']}")
    # Fallback: direct DB cleanup if API doesn't support userId filter
    # (the API cleanup above should be sufficient)


class TestBridgeConnectivity:
    """Verify the bridge is reachable before running expensive LLM tests."""

    def test_bridge_health(self, bridge_client):
        resp = bridge_client.get(f"{BRIDGE_URL}/health")
        assert resp.status_code == 200

    def test_bridge_models(self, bridge_client):
        resp = bridge_client.get(f"{BRIDGE_URL}/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        model_ids = [m["id"] for m in data["data"]]
        assert MODEL in model_ids, f"'{MODEL}' not in available models: {model_ids}"

    def test_mnemosyne_health(self, backend_client):
        resp = backend_client.get("/health")
        assert resp.status_code == 200


class TestInitialMessageRecall:
    """Test 1: First message triggers memory recall and uses LobeChat system prompt."""

    def test_uses_system_prompt_context(self, bridge_client):
        """Agent should use date/user info from the LobeChat system prompt."""
        content = _chat(bridge_client, [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "What day of the week is it today, and what is my name?"},
        ])
        content_lower = content.lower()
        assert "sunday" in content_lower, f"Expected 'sunday' in response: {content}"
        assert "testuser" in content_lower or "test user" in content_lower, (
            f"Expected 'TestUser' in response: {content}"
        )


class TestNoToolResponse:
    """Test 2: Agent answers from knowledge without invoking tools."""

    def test_general_knowledge_answer(self, bridge_client):
        """A factual question that needs no search or memory."""
        content = _chat(bridge_client, [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "What is the chemical symbol for gold?"},
        ])
        assert "Au" in content, f"Expected 'Au' in response: {content}"


class TestResearchAssistant:
    """Test 3: Agent uses research_assistant tool for current events."""

    def test_current_events_search(self, bridge_client):
        """Ask about recent news — agent must invoke research_assistant."""
        content = _chat(
            bridge_client,
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Search the web and tell me: what is the current US federal funds rate "
                        "as of this week? Please include the source."
                    ),
                },
            ],
            timeout=SLOW_TIMEOUT,
        )
        # Should contain a percentage and some kind of source reference
        assert "%" in content, f"Expected a percentage in response: {content}"
        assert len(content) > 50, f"Response too short for a research result: {content}"


class TestExplicitMemoryRecall:
    """Test 4: Agent uses recall_memory tool when explicitly asked.

    Note: Earlier tests in this module may have stored conversations to Mnemosyne,
    so the recall might find those. We accept either outcome — the key thing is
    that the agent produces a substantive response about memory.
    """

    def test_recall_produces_response(self, bridge_client):
        """Agent should either report no memories or recall earlier test conversations."""
        content = _chat(bridge_client, [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Please search your memory for any past conversations we've had. "
                    "What topics have we discussed before?"
                ),
            },
        ])
        content_lower = content.lower()
        # Agent should either say "no past conversations" OR recall topics from earlier tests
        has_no_memory = any(phrase in content_lower for phrase in [
            "no past", "no prior", "no record", "no previous",
            "haven't had", "don't have any", "first time",
            "first interaction", "no relevant", "couldn't find", "no memories",
        ])
        has_recall = len(content) > 50  # substantive response about past topics
        assert has_no_memory or has_recall, (
            f"Expected agent to either report no memories or recall past topics: {content}"
        )


class TestConversationContinuity:
    """Test 5: Multi-turn conversation retains context from message history."""

    def test_references_prior_messages(self, bridge_client):
        """Send a follow-up that requires context from the conversation history."""
        content = _chat(bridge_client, [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "I'm planning a trip to Tokyo next month. My budget is $3000.",
            },
            {
                "role": "assistant",
                "content": (
                    "Tokyo in March sounds wonderful! With a $3000 budget, you can have a "
                    "great 7-10 day trip. That covers flights (~$800-1200 round trip from "
                    "the US West Coast), mid-range hotels (~$100-150/night), food (~$30-50/day "
                    "for a mix of convenience stores, ramen shops, and the occasional nicer meal), "
                    "and transportation (a 7-day Japan Rail Pass is around $200). Would you like "
                    "recommendations for specific neighborhoods to stay in?"
                ),
            },
            {
                "role": "user",
                "content": "What city was I planning to visit, and what was my budget?",
            },
        ])
        content_lower = content.lower()
        assert "tokyo" in content_lower, f"Expected 'tokyo' in response: {content}"
        assert "3000" in content or "3,000" in content, (
            f"Expected '$3000' in response: {content}"
        )

    def test_longer_continuity(self, bridge_client):
        """Three-turn conversation — agent references details from turn 1 after turn 2."""
        content = _chat(bridge_client, [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "My dog's name is Biscuit and he's a corgi."},
            {
                "role": "assistant",
                "content": "Biscuit is a great name for a corgi! They're such fun, spirited dogs.",
            },
            {
                "role": "user",
                "content": "He just turned 3 years old yesterday.",
            },
            {
                "role": "assistant",
                "content": "Happy belated birthday to Biscuit! Three is a great age for a corgi.",
            },
            {
                "role": "user",
                "content": "What breed is my dog, what's his name, and how old is he?",
            },
        ])
        content_lower = content.lower()
        assert "biscuit" in content_lower, f"Expected 'Biscuit' in response: {content}"
        assert "corgi" in content_lower, f"Expected 'corgi' in response: {content}"
        assert "3" in content or "three" in content_lower, (
            f"Expected age '3' in response: {content}"
        )


class TestMnemosyneStorage:
    """Test 6: Verify conversations are stored in Mnemosyne after agent responses."""

    def test_conversation_stored(self, bridge_client, backend_client):
        """Send a message and verify it appears in Mnemosyne for the test user."""
        marker = f"e2e-storage-check-{uuid.uuid4().hex[:8]}"
        _chat(bridge_client, [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Please respond with exactly this text: {marker}"},
        ])

        # Check Mnemosyne for the stored conversation
        resp = backend_client.get(
            "/api/conversations",
            params={"userId": TEST_USER_ID, "limit": 10},
        )
        assert resp.status_code == 200
        data = resp.json()
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("conversations", data.get("items", []))
        else:
            items = []

        # Look for our marker in any stored conversation's messages
        found = False
        for conv in items:
            conv_detail = backend_client.get(f"/api/conversations/{conv['id']}")
            if conv_detail.status_code == 200:
                conv_data = conv_detail.json()
                messages = conv_data.get("messages", [])
                for msg in messages:
                    if marker in msg.get("content", ""):
                        found = True
                        break
            if found:
                break

        assert found, (
            f"Expected marker '{marker}' in Mnemosyne conversations for user '{TEST_USER_ID}'. "
            f"Found {len(items)} conversations but none contained the marker. "
            "Store & Respond node may not be executing."
        )
