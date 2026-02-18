FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /tests
COPY pyproject.toml ./
RUN uv sync --no-install-project
COPY conftest.py test_integration.py test_conversation_integration.py ./
COPY test_retrieval_quality.py* ./

CMD ["uv", "run", "pytest", "-v", "--tb=short"]
