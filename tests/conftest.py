import os
import pytest
import httpx


BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:3000")
MCP_URL = os.environ.get("MCP_URL", "http://mcp-server:8080")


@pytest.fixture
def backend_url():
    return BACKEND_URL


@pytest.fixture
def mcp_url():
    return MCP_URL


@pytest.fixture
async def backend_client(backend_url):
    async with httpx.AsyncClient(base_url=backend_url) as client:
        yield client


@pytest.fixture(autouse=True)
async def clean_memories(backend_url):
    """Each test starts with a clean slate by storing no prior state.

    Since the backend uses in-memory storage and we can't clear it via API,
    we rely on each test composing unique content to avoid collisions.
    """
    yield
