# Mnemosyne Backend

Backend services for the Mnemosyne memory management system.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables:
```bash
# Django settings
export DJANGO_SETTINGS_MODULE=memory_service.settings

# Database settings
export DATABASE_URL=sqlite:///path/to/db.sqlite3  # or your preferred database

# Neo4j connection settings
export NEO4J_URI=neo4j://localhost:7687
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=password
```

## Running Tests

### Unit Tests

Run unit tests with:
```bash
python -m pytest
```

### Integration Tests

#### Neo4j Integration Tests

The Neo4j integration tests require a running Neo4j instance. The tests are configured to use a test Neo4j instance running on port 7688.

1. Start the Neo4j test container:
```bash
# From the project root
docker-compose -f docker-compose.test.yml up -d
```

2. Run the Neo4j integration tests:
```bash
# Set Django settings for tests
export DJANGO_SETTINGS_MODULE=memories.tests.test_settings

# Run tests
python -m pytest memories/tests/test_graph_service.py
```

#### LLM Integration Tests

LLM integration tests can use either:
- A real OpenAI-compatible API endpoint
- A mock LLM endpoint (tests will automatically fall back to mocks when no real endpoint is available)

To use a real OpenAI-compatible endpoint:

```bash
# OpenAI API settings
export OLLAMA_BASE_URL="http://localhost:11434"
# Set Django settings for tests
export DJANGO_SETTINGS_MODULE=memories.tests.test_settings

# Run tests
python -m pytest memories/tests/test_graph_service.py
```

If no valid endpoint is provided, LLM-dependent tests will either use mocks or skip the test depending on the specific test requirements.

## Performance Tests

Performance tests require a real LLM API endpoint and will be skipped if no valid endpoint is configured:

```bash
# Run with a real endpoint configured
python -m pytest memories/tests/test_graph_service.py::GraphServiceIntegrationTest::test_performance_simple
```
