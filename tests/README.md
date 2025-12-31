# Testing Guide

This directory contains comprehensive tests for the WhatsApp chatbot flow.

## Directory Structure

```
tests/
├── README.md                           # This file
├── conftest.py                         # Pytest configuration & fixtures
├── pytest.ini                          # Pytest settings
├── requirements.txt                    # Test dependencies
├── test_harness/                       # Mock implementations
│   ├── __init__.py
│   ├── windmill_mock.py               # Mock wmill functions
│   ├── llm_mock.py                    # Mock OpenAI/Google APIs
│   └── whatsapp_mock.py               # Mock WhatsApp API
├── unit/                              # Unit tests for individual steps
│   ├── test_step1_context_loading.py
│   ├── test_step2_llm_processing.py
│   ├── test_step3_1_send_reply.py
│   ├── test_step4__save_history.py
│   └── test_step5__usage_logging.py
├── integration/                        # Integration tests
│   ├── test_full_flow.py
│   └── test_database_operations.py
└── fixtures/                          # Test data
    ├── sample_webhook_payloads.json
    └── sample_llm_responses.json
```

## Setup

### 1. Install Dependencies

```bash
pip install -r tests/requirements.txt
```

### 2. Start Test Database

```bash
# Start the test database container
docker-compose -f docker-compose.test.yml up -d

# Wait for it to be healthy
docker-compose -f docker-compose.test.yml ps

# The database will auto-initialize with the schema from db/*.sql
```

### 3. Configure Environment

Create a `.env.test` file (or use your existing `.env`):

```bash
# Test Database
TEST_DB_HOST=localhost
TEST_DB_PORT=5434
TEST_DB_USER=test_user
TEST_DB_PASSWORD=test_password
TEST_DB_NAME=test_business_logic

# Test API Keys (can be fake for testing)
GOOGLE_API_KEY=test_google_key
OPENAI_API_KEY=test_openai_key
WHATSAPP_PHONE_NUMBER_ID=test_phone_123
WHATSAPP_ACCESS_TOKEN=test_token_xyz
OWNER_EMAIL=test@example.com
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Tests for a specific step
pytest tests/unit/test_step1_context_loading.py

# Tests with database
pytest -m db

# Tests without database
pytest -m "not db"
```

### Run with Coverage

```bash
pytest --cov=f/development --cov-report=html
```

### Run in Verbose Mode

```bash
pytest -v
pytest -vv  # Extra verbose
```

### Run Specific Test

```bash
# By test name
pytest tests/unit/test_step1_context_loading.py::TestIdempotency::test_duplicate_message_blocked

# By keyword match
pytest -k "idempotency"
pytest -k "usage_limits"
```

## Test Fixtures

### Database Fixtures

- **`clean_db`** - Resets database to seed state before test
- **`db_with_data`** - Provides DB cursor with seed data
- **`db_cursor`** - Raw database cursor (auto-rollback)
- **`query_helper`** - Helper methods for common queries

Example usage:

```python
def test_something(db_with_data, query_helper):
    # Database is clean and seeded
    org = query_helper.get_organization("11111111-1111-1111-1111-111111111111")
    assert org["name"] == "Dev Corp"
```

### Mock Fixtures

- **`mock_wmill`** - Mock Windmill functions
- **`mock_llm`** - Mock LLM providers
- **`mock_whatsapp`** - Mock WhatsApp API
- **`mock_all_external`** - All mocks together

Example usage:

```python
def test_something(mock_wmill, mock_llm):
    # Configure mock responses
    mock_llm.add_response("This is a test response", tokens_input=100, tokens_output=50)
    
    # Patch and test
    with patch('wmill.get_resource', mock_wmill.get_resource):
        result = my_function()
    
    # Verify
    assert mock_llm.get_call_count() == 1
```

### Data Fixtures

- **`sample_webhook_payload`** - WhatsApp webhook payload
- **`sample_context_payload`** - Step 1 output
- **`sample_llm_result`** - Step 2 output

## Writing Tests

### Unit Test Template

```python
import pytest
from unittest.mock import patch

def test_feature_name(db_with_data, mock_wmill):
    """Test that feature works as expected."""
    # Arrange
    with patch('wmill.get_resource', mock_wmill.get_resource):
        # Import the module AFTER patching
        from f.development import module_under_test
        
        # Act
        result = module_under_test.main(
            param1="value1",
            param2="value2"
        )
    
    # Assert
    assert result["expected_field"] == "expected_value"
```

### Integration Test Template

```python
import pytest
from unittest.mock import patch

def test_full_flow(clean_db, mock_all_external):
    """Test complete flow from webhook to response."""
    # Configure mocks
    mocks = mock_all_external
    mocks["llm"].add_response("Test response")
    
    # Run flow
    # ... simulate full workflow
    
    # Verify end-to-end behavior
    assert mocks["whatsapp"].get_call_count() == 1
```

## Test Database

### Resetting the Database

The database automatically resets before each test using the `clean_db` fixture. If you need to manually reset:

```bash
# Stop and remove test database
docker-compose -f docker-compose.test.yml down -v

# Restart
docker-compose -f docker-compose.test.yml up -d
```

### Inspecting Test Data

```bash
# Connect to test database
docker exec -it test_business_logic_db psql -U test_user -d test_business_logic

# View tables
\dt

# Query data
SELECT * FROM organizations;
SELECT * FROM chatbots;
```

### Custom Test Data

To add custom test data, modify `db/seed.sql` or insert data in your test:

```python
def test_with_custom_data(db_with_data):
    # Insert test data
    db_with_data.execute(
        "INSERT INTO contacts (id, chatbot_id, phone_number, name) VALUES (%s, %s, %s, %s)",
        ("test-id", "chatbot-id", "15551234567", "Test User")
    )
    db_with_data.connection.commit()
    
    # Run test
    # ...
```

## Best Practices

### 1. Use Appropriate Test Level

- **Unit Tests**: Test individual functions with mocked dependencies
- **Integration Tests**: Test multiple components together with real database
- **E2E Tests**: Use Windmill's built-in testing for full workflow

### 2. Keep Tests Fast

- Use mocks for external APIs (LLM, WhatsApp)
- Use real database for data integrity tests
- Run slow tests separately: `pytest -m "not slow"`

### 3. Test Isolation

- Each test should be independent
- Use `clean_db` fixture for tests that modify data
- Don't rely on test execution order

### 4. Descriptive Names

```python
# Good
def test_duplicate_message_blocked_when_already_completed()

# Bad
def test_dup_msg()
```

### 5. AAA Pattern

```python
def test_something():
    # Arrange - Set up test data
    data = {"key": "value"}
    
    # Act - Execute the code
    result = function_under_test(data)
    
    # Assert - Verify results
    assert result == expected_value
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: test_business_logic
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5434:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r tests/requirements.txt
      
      - name: Run tests
        run: |
          pytest --cov --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Debugging Tests

### Print Database State

```python
def test_something(db_with_data):
    # Print all contacts
    db_with_data.execute("SELECT * FROM contacts")
    for row in db_with_data.fetchall():
        print(row)
```

### Use pytest's built-in debugging

```bash
# Drop into debugger on failure
pytest --pdb

# Drop into debugger at start of test
pytest --trace
```

### Inspect Mock Calls

```python
def test_something(mock_llm, mock_whatsapp):
    # ... run test
    
    # Inspect calls
    print(f"LLM called {mock_llm.get_call_count()} times")
    print(f"Last call: {mock_llm.get_last_call()}")
    print(f"WhatsApp messages: {mock_whatsapp.get_sent_messages()}")
```

## Common Issues

### Issue: Database Connection Failed

**Solution**: Ensure test database is running
```bash
docker-compose -f docker-compose.test.yml ps
docker-compose -f docker-compose.test.yml up -d
```

### Issue: Import Errors

**Solution**: Ensure project root is in Python path
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

### Issue: Tests Interfering With Each Other

**Solution**: Use `clean_db` fixture to reset between tests

### Issue: Mocks Not Working

**Solution**: Patch AFTER imports
```python
# Wrong
from module import function
with patch('module.function'):
    ...

# Right
with patch('module.function'):
    from module import function
    ...
```

## Performance

### Test Execution Time

Track slow tests:
```bash
pytest --durations=10
```

### Parallel Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel
pytest -n auto
```

## Maintenance

### Adding New Tests

1. Create test file in appropriate directory
2. Import fixtures from `conftest.py`
3. Follow naming convention: `test_*.py`
4. Add docstrings explaining what's tested

### Updating Test Data

1. Modify `db/seed.sql` for permanent changes
2. Use fixtures for test-specific data

### Deprecating Tests

Mark tests as expected to fail:
```python
@pytest.mark.xfail(reason="Known issue #123")
def test_something():
    ...
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Testing Best Practices](https://docs.pytest.org/en/latest/goodpractices.html)
- [Mocking Guide](https://docs.python.org/3/library/unittest.mock.html)