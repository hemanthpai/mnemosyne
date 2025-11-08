# Phase 3 Test Suite

Comprehensive automated tests for the A-MEM (Atomic Memory) implementation.

## Test Coverage

### 1. Settings Tests (`test_settings.py`)
**Coverage: Settings model and API**

- ✅ Singleton pattern enforcement
- ✅ Default values verification
- ✅ Cache clearing on save
- ✅ API key masking (security)
- ✅ Generation config fallback to embeddings config
- ✅ GET `/api/settings/` endpoint
- ✅ PUT `/api/settings/update/` endpoint
- ✅ Validation:
  - Temperature (0.0-1.0)
  - Timeouts (1-600 seconds)
  - Max tokens (1-100000)
  - Provider (ollama, openai, openai_compatible)
- ✅ Multi-field updates

**Total: 13 tests**

### 2. LLM Service Tests (`test_llm_service.py`)
**Coverage: LLM service with separate generation configuration**

- ✅ Config loading from database
- ✅ Fallback to embeddings config when generation fields empty
- ✅ Partial config override (mix of embeddings + generation)
- ✅ Config defaults used when params not provided
- ✅ Param override of config defaults
- ✅ Correct endpoint selection (separate for embeddings/generation)
- ✅ Correct API key usage (separate for embeddings/generation)
- ✅ Correct timeout usage
- ✅ Error handling (network errors, invalid responses)

**Total: 9 tests**

### 3. Extraction Tests (`test_extraction.py`)
**Coverage: Atomic note extraction from conversations**

- ✅ Successful extraction with multiple notes
- ✅ JSON parsing from markdown code blocks
- ✅ Duplicate detection and skipping
- ✅ Empty notes array handling
- ✅ Field validation (required fields)
- ✅ Retry logic on JSON parse error
- ✅ Max retries (3 attempts)
- ✅ Skip already extracted turns
- ✅ Temperature escalation on retries (0.3 → 0.5 → 0.7)
- ✅ Prompt contains key instructions
- ✅ Rollback on embedding failure

**Total: 11 tests**

### 4. Relationship Tests (`test_relationships.py`)
**Coverage: Relationship building between atomic notes**

- ✅ Successful relationship creation
- ✅ Weak relationship skipping (< 0.3 strength)
- ✅ Existing relationship updates (higher strength wins)
- ✅ No similar notes handling
- ✅ Self-exclusion (note doesn't relate to itself)
- ✅ Importance score calculation:
  - No relationships (equals confidence)
  - With outgoing relationships
  - With incoming relationships
  - Capped at max (confidence + 2.0)
  - Both directions
- ✅ Unique constraint enforcement (no duplicate relationships)
- ✅ Different relationship types allowed

**Total: 13 tests**

### 5. Integration Tests (`test_integration.py`)
**Coverage: End-to-end pipeline testing**

- ✅ Store conversation turn via API
- ✅ List conversations via API
- ✅ Search conversations via API (fast mode)
- ✅ Settings update affects generation behavior
- ✅ Generation/embeddings config separation
- ✅ Atomic note creation and querying
- ✅ Knowledge graph traversal
- ✅ Note ordering by importance

**Total: 8 tests**

## Running Tests

### Run All Tests

```bash
# Inside Docker container
docker exec mnemosyne_app python manage.py test memories.tests

# Or from host with sg docker
sg docker "docker exec mnemosyne_app python manage.py test memories.tests"
```

### Run Specific Test Files

```bash
# Settings tests only
python manage.py test memories.tests.test_settings

# LLM service tests only
python manage.py test memories.tests.test_llm_service

# Extraction tests only
python manage.py test memories.tests.test_extraction

# Relationship tests only
python manage.py test memories.tests.test_relationships

# Integration tests only
python manage.py test memories.tests.test_integration
```

### Run Specific Test Cases

```bash
# Run single test class
python manage.py test memories.tests.test_settings.SettingsModelTest

# Run single test method
python manage.py test memories.tests.test_settings.SettingsModelTest.test_singleton_pattern
```

### Verbose Output

```bash
# Show detailed test output
python manage.py test memories.tests --verbosity=2

# Show even more detail
python manage.py test memories.tests --verbosity=3
```

### Test Coverage Report

```bash
# Install coverage
pip install coverage

# Run with coverage
coverage run --source='memories' manage.py test memories.tests

# View report
coverage report

# Generate HTML report
coverage html
# Open htmlcov/index.html
```

## Test Organization

```
backend/memories/tests/
├── __init__.py                 # Test suite initialization
├── README.md                   # This file
├── test_settings.py            # Settings model & API tests
├── test_llm_service.py         # LLM service tests
├── test_extraction.py          # Extraction pipeline tests
├── test_relationships.py       # Relationship building tests
└── test_integration.py         # End-to-end integration tests
```

## Mocking Strategy

Tests use `unittest.mock` to avoid external dependencies:

- **LLM API calls**: Mocked to return pre-defined responses
- **Vector database**: Mocked to avoid Qdrant dependency
- **Background tasks**: Mocked to avoid Django-Q dependency

This ensures:
- ✅ **Fast execution**: No network calls or external services
- ✅ **Reliability**: Tests don't fail due to external service issues
- ✅ **Deterministic**: Same inputs always produce same results
- ✅ **Isolation**: Each test is independent

## What's Tested

### Phase 3 Components

1. **Settings Model**
   - Singleton pattern
   - Database storage
   - Cache management
   - API key security

2. **Settings API**
   - GET endpoint
   - PUT endpoint with validation
   - Field validation rules

3. **LLM Service**
   - Separate generation configuration
   - Fallback logic
   - Config precedence
   - Error handling

4. **Extraction Pipeline**
   - JSON parsing
   - Note creation
   - Duplicate prevention
   - Retry logic
   - Validation

5. **Relationship Building**
   - Relationship creation
   - Strength-based filtering
   - Duplicate handling
   - Importance scoring

6. **Integration**
   - Full API workflows
   - Settings-to-LLM integration
   - Knowledge graph operations

## Test Statistics

- **Total Tests**: 54
- **Test Files**: 5
- **Lines of Test Code**: ~1,200
- **Components Covered**: Settings, LLM, Extraction, Relationships, Integration
- **Coverage Target**: >80%

## Adding New Tests

When adding new Phase 3 features:

1. Add unit tests to the appropriate file
2. Add integration tests if it touches multiple components
3. Mock external dependencies
4. Follow the existing test patterns
5. Run full test suite before committing

## Continuous Integration

To integrate with CI/CD:

```bash
# In CI pipeline
docker-compose up -d db qdrant redis
docker-compose run app python manage.py test memories.tests --verbosity=2
```

## Common Test Patterns

### Testing Django Models

```python
def test_model_creation(self):
    obj = MyModel.objects.create(field="value")
    self.assertIsNotNone(obj.id)
    self.assertEqual(obj.field, "value")
```

### Testing API Endpoints

```python
def test_api_endpoint(self):
    response = self.client.post(
        '/api/endpoint/',
        data={'key': 'value'},
        content_type='application/json'
    )
    self.assertEqual(response.status_code, 200)
    data = response.json()
    self.assertTrue(data['success'])
```

### Mocking External Services

```python
@patch('module.external_service')
def test_with_mock(self, mock_service):
    mock_service.return_value = {'result': 'mocked'}
    result = my_function()
    self.assertEqual(result, 'mocked')
```

## Troubleshooting

### Tests Failing Due to Database State

```bash
# Reset test database
python manage.py flush --no-input
python manage.py migrate
```

### Tests Failing Due to Cache

Each test should clear cache in `setUp()`:
```python
def setUp(self):
    cache.clear()
```

### Tests Timing Out

Increase test timeout or check for infinite loops in mocked services.

## Next Steps

- [ ] Add performance benchmarks
- [ ] Add stress tests for high-volume scenarios
- [ ] Add tests for error recovery
- [ ] Measure and improve code coverage
- [ ] Add frontend integration tests
