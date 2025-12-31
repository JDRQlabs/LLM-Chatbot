# Comprehensive Testing Plan

## Executive Summary

This plan outlines a systematic approach to achieve comprehensive test coverage for the WhatsApp chatbot backend while adhering to pytest best practices. Current coverage: ~35%. Target: >80% for critical paths.

**Key Principles:**
1. **Simplicity** - Minimize test code, maximize clarity
2. **Real Implementation** - Test actual backend code, no custom test implementations
3. **Pytest Best Practices** - Fixtures, importlib mode, strict config, deterministic tests
4. **Fast Feedback** - Unit tests run in <1s, integration tests in <5s

---

## 1. Test Organization Structure

### Current Structure (Already Good)
```
tests/
├── conftest.py              # Shared fixtures ✓
├── unit/                    # Fast, isolated tests ✓
│   ├── test_step1_context_loading.py
│   ├── test_step2_*.py
│   └── test_quota_enforcement.py
├── integration/             # Multi-component tests ✓
│   ├── test_rag_api_endpoints.py
│   ├── test_database_operations.py
│   └── test_full_flow.py
└── test_harness/            # Mock utilities ✓
    ├── windmill_mock.py
    ├── llm_mock.py
    └── whatsapp_mock.py
```

### Import Mode (Already Configured)
- Using `importlib` mode via direct imports
- Scripts import using `importlib.util.spec_from_file_location`
- No sys.path manipulation in tests (only in conftest.py setup)

### Markers (Already Configured in pytest.ini)
```ini
-m unit      # Fast, no DB, mocked externals
-m integration  # Real DB, minimal mocking
-m slow      # >5s execution
-m db        # Requires database
```

---

## 2. Fixture Strategy

### Core Fixtures (Already in conftest.py)

#### Database Fixtures
```python
# Use db_with_data (default) - Auto rollback, fast, isolated
def test_message_creation(db_with_data):
    # Changes rollback automatically

# Use db_with_autocommit - For testing external scripts
def test_windmill_script(db_with_autocommit):
    # Script sees committed data
    # clean_db resets between tests
```

#### Mock Fixtures
```python
# Use mock_all_external - For integration tests
def test_flow(mock_all_external, db_with_data):
    # All external APIs mocked
    # Database real
```

### New Fixtures Needed

```python
# 1. LLM Response Fixtures (add to conftest.py)
@pytest.fixture
def gemini_simple_response():
    """Simple text response from Gemini (no tools)"""
    return {
        "reply_text": "Hello! How can I help?",
        "updated_variables": {},
        "usage_info": {
            "provider": "google",
            "model": "gemini-pro",
            "tokens_input": 50,
            "tokens_output": 20
        }
    }

@pytest.fixture
def gemini_tool_call_response():
    """Gemini response with tool call"""
    return {
        "tool_calls": [
            {"name": "get_weather", "args": {"city": "NYC"}}
        ],
        "usage_info": {...}
    }

# 2. Message History Fixture
@pytest.fixture
def conversation_history(db_with_data, sample_context_payload):
    """Pre-populate conversation history"""
    contact_id = sample_context_payload["user"]["id"]
    db_with_data.execute("""
        INSERT INTO messages (contact_id, direction, content, created_at)
        VALUES
            (%s, 'incoming', 'Hello', NOW() - INTERVAL '2 minutes'),
            (%s, 'outgoing', 'Hi there!', NOW() - INTERVAL '1 minute')
    """, (contact_id, contact_id))
    return contact_id

# 3. Vector Embedding Fixture (add to conftest.py)
@pytest.fixture
def openai_embedding_1536():
    """Valid 1536-dimensional embedding for testing"""
    return "[" + ", ".join(["0.1"] * 1536) + "]"
```

---

## 4. Simplification Strategies

### Strategy 1: Import Real Code, Don't Duplicate

❌ **Bad - Custom Test Implementation:**
```python
def test_quota_check():
    # Custom quota logic in test
    max_pdfs = 100
    current_pdfs = 50
    if current_pdfs < max_pdfs:
        assert True
```

✅ **Good - Import Real Implementation:**
```python
from f.development.utils.check_knowledge_quota import main as check_quota

def test_quota_check(mock_wmill_resource, db_with_autocommit):
    # Use real implementation
    with patch('wmill.get_resource', return_value=mock_wmill_resource):
        result = check_quota(
            organization_id="org-123",
            file_size_mb=10.0
        )
    assert result["allowed"] is True
```

### Strategy 2: Use Fixtures for Test Data

❌ **Bad - Inline Data Setup:**
```python
def test_message_creation(db_cursor):
    # Lots of setup code
    db_cursor.execute("INSERT INTO organizations ...")
    db_cursor.execute("INSERT INTO chatbots ...")
    db_cursor.execute("INSERT INTO contacts ...")
    # Actual test buried in setup
```

✅ **Good - Fixture-Based Setup:**
```python
def test_message_creation(db_with_data, sample_context_payload):
    # Clean test - setup in fixtures
    contact_id = sample_context_payload["user"]["id"]
    # Test logic only
```

### Strategy 3: Parametrize Instead of Duplicate

❌ **Bad - Duplicate Tests:**
```python
def test_quota_pdf_exceeded():
    # Test with PDFs

def test_quota_url_exceeded():
    # Test with URLs (same logic)

def test_quota_storage_exceeded():
    # Test with storage (same logic)
```

✅ **Good - Parametrized Test:**
```python
@pytest.mark.parametrize("quota_type,expected_message", [
    ("max_pdfs", "PDF upload limit reached"),
    ("max_urls", "URL ingestion limit reached"),
    ("max_storage", "Storage quota exceeded"),
])
def test_quota_exceeded(quota_type, expected_message, ...):
    # Single test, multiple scenarios
```

### Strategy 4: Use Helper Methods in conftest.py

❌ **Bad - Repeated Query Code:**
```python
def test_a(db_cursor):
    db_cursor.execute("SELECT * FROM chatbots WHERE id = %s", (id,))
    chatbot = db_cursor.fetchone()

def test_b(db_cursor):
    db_cursor.execute("SELECT * FROM chatbots WHERE id = %s", (id,))
    chatbot = db_cursor.fetchone()
```

✅ **Good - Use query_helper Fixture:**
```python
def test_a(query_helper):
    chatbot = query_helper.get_chatbot(chatbot_id)

def test_b(query_helper):
    chatbot = query_helper.get_chatbot(chatbot_id)
```

---

## 5. Backend Code Reuse

### Pattern 1: Import Windmill Scripts Directly

```python
# Import the actual script
import importlib.util
spec = importlib.util.spec_from_file_location(
    "step1",
    "f/development/1_whatsapp_context_loading.py"
)
step1_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step1_module)

# Test the real function
def test_step1_logic(mock_wmill):
    result = step1_module.main(
        whatsapp_phone_id="123",
        user_phone="16315551234",
        message_id="wamid.123",
        user_name="Test User"
    )
    assert result["proceed"] is True
```

### Pattern 2: Test Utilities Directly

```python
# Import real utility
from f.development.utils.check_knowledge_quota import main as check_quota

def test_quota_enforcement():
    # Test real implementation
    result = check_quota(org_id="...", file_size_mb=50.0)
```

### Pattern 3: Test Database Schema/Triggers

```python
def test_knowledge_counter_trigger(db_with_data):
    """Test the real database trigger increments counters"""
    # Insert knowledge source
    db_with_data.execute("""
        INSERT INTO knowledge_sources (chatbot_id, source_type, name)
        VALUES (%s, 'pdf', 'test.pdf')
    """, (chatbot_id,))

    # Verify trigger updated counters
    db_with_data.execute("""
        SELECT pdf_count FROM chatbots WHERE id = %s
    """, (chatbot_id,))
    assert db_with_data.fetchone()["pdf_count"] == 1
```

---

## 6. Flaky Test Prevention

### Rule 1: No Global State
```python
# ❌ Bad - Global state
cache = {}

def test_with_cache():
    cache["key"] = "value"  # Affects other tests

# ✅ Good - Isolated state
def test_with_cache(monkeypatch):
    cache = {}
    monkeypatch.setattr("module.cache", cache)
```

### Rule 2: Fixed Timestamps
```python
# ❌ Bad - Time-dependent
def test_expiry():
    created_at = datetime.now()
    # Flaky if test runs slow

# ✅ Good - Fixed time
from freezegun import freeze_time

@freeze_time("2025-01-15 10:00:00")
def test_expiry():
    # Deterministic
```

### Rule 3: Use pytest.approx for Floats
```python
# ❌ Bad - Exact float comparison
assert cost == 0.001

# ✅ Good - Approximate comparison
assert cost == pytest.approx(0.001, rel=1e-6)
```

### Rule 4: Proper Cleanup
```python
# ✅ Use fixtures with yield for cleanup
@pytest.fixture
def temp_file():
    f = open("test.txt", "w")
    yield f
    f.close()
    os.remove("test.txt")
```

### Rule 5: Deterministic Test Order
```python
# Don't rely on test execution order
# Each test should be independent
```

---

## 7. Implementation Templates

### Template 1: Unit Test for Step 1 (Context Loading)

```python
@patch('psycopg2.connect')
def test_user_data_loading(mock_connect):
    """Test Step 1 loads user data correctly"""
    # Setup mock database
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Mock responses: no duplicate, webhook created, chatbot found, user found
    mock_cursor.fetchone.side_effect = [
        None,  # No duplicate
        {"id": 1},  # Webhook event
        {"id": "chatbot-123", "name": "Test Bot", ...},  # Chatbot
        {"id": "user-456", "name": "John", "phone": "1234567890"}  # User
    ]

    # Call real function
    result = step1_main(
        whatsapp_phone_id="phone-123",
        user_phone="1234567890",
        message_id="msg-789",
        user_name="John"
    )

    # Verify
    assert result["proceed"] is True
    assert result["user"]["id"] == "user-456"
    assert result["user"]["name"] == "John"
```

### Template 2: Integration Test for Step 2 (LLM Processing)

```python
def test_step2_simple_response(mock_all_external, db_with_data, sample_context_payload):
    """Test Step 2 generates simple LLM response"""
    # Configure LLM mock
    mock_all_external["llm"].set_response({
        "reply_text": "Hello! How can I help?",
        "updated_variables": {},
        "usage_info": {
            "provider": "google",
            "model": "gemini-pro",
            "tokens_input": 50,
            "tokens_output": 20
        }
    })

    # Import and call real Step 2
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "step2",
        "f/development/2_whatsapp_llm_processing.py"
    )
    step2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(step2)

    result = step2.main(
        context=sample_context_payload,
        user_message="Hello"
    )

    # Verify
    assert result["reply_text"] == "Hello! How can I help?"
    assert result["usage_info"]["tokens_input"] == 50
```

### Template 3: Database Test for Triggers

```python
def test_knowledge_source_counter_increment(db_with_data):
    """Test trigger increments pdf_count when PDF added"""
    # Setup
    chatbot_id = "22222222-2222-2222-2222-222222222222"

    # Get initial count
    db_with_data.execute(
        "SELECT pdf_count FROM chatbots WHERE id = %s",
        (chatbot_id,)
    )
    initial_count = db_with_data.fetchone()["pdf_count"]

    # Add PDF source
    db_with_data.execute("""
        INSERT INTO knowledge_sources (chatbot_id, source_type, name)
        VALUES (%s, 'pdf', 'test.pdf')
    """, (chatbot_id,))

    # Verify trigger updated count
    db_with_data.execute(
        "SELECT pdf_count FROM chatbots WHERE id = %s",
        (chatbot_id,)
    )
    new_count = db_with_data.fetchone()["pdf_count"]
    assert new_count == initial_count + 1
```

### Template 4: API Endpoint Test

```python
def test_upload_pdf_endpoint(client, db_with_data, mock_quota_check):
    """Test POST /api/knowledge/upload endpoint"""
    # Setup
    mock_quota_check.return_value = {"allowed": True}

    # Prepare file upload
    files = {
        "file": ("test.pdf", b"PDF content", "application/pdf")
    }
    data = {
        "chatbot_id": "chatbot-123",
        "name": "Test Document"
    }

    # Call endpoint
    response = client.post(
        "/api/knowledge/upload",
        data=data,
        files=files
    )

    # Verify response
    assert response.status_code == 200
    assert response.json()["status"] == "uploaded"

    # Verify database
    db_with_data.execute("""
        SELECT * FROM knowledge_sources
        WHERE chatbot_id = %s AND name = %s
    """, ("chatbot-123", "Test Document"))
    source = db_with_data.fetchone()
    assert source is not None
    assert source["source_type"] == "pdf"
```

### Template 5: Parametrized Test

```python
@pytest.mark.parametrize("source_type,expected_count_field", [
    ("pdf", "pdf_count"),
    ("url", "url_count"),
])
def test_source_counter_by_type(db_with_data, source_type, expected_count_field):
    """Test counters update correctly for different source types"""
    chatbot_id = "22222222-2222-2222-2222-222222222222"

    # Add source
    db_with_data.execute(f"""
        INSERT INTO knowledge_sources (chatbot_id, source_type, name)
        VALUES (%s, %s, 'test')
    """, (chatbot_id, source_type))

    # Verify count
    db_with_data.execute(
        f"SELECT {expected_count_field} FROM chatbots WHERE id = %s",
        (chatbot_id,)
    )
    count = db_with_data.fetchone()[expected_count_field]
    assert count > 0
```

---

## 8. Testing Checklist

Before marking a test complete, verify:

- [ ] Test is in correct directory (unit/ vs integration/)
- [ ] Test uses appropriate fixture (db_with_data vs db_with_autocommit)
- [ ] Test has clear docstring explaining what it tests
- [ ] Test imports real implementation (no duplicate logic)
- [ ] Test is deterministic (no time/randomness dependencies)
- [ ] Test cleans up after itself (or uses fixtures that do)
- [ ] Test is parametrized if testing multiple similar cases
- [ ] Test assertions are clear and specific
- [ ] Test runs in <1s (unit) or <5s (integration)
- [ ] Test has appropriate markers (@pytest.mark.unit, @pytest.mark.db, etc.)

---

## 9. Success Metrics

### Coverage Targets
- **Critical Path (Step 1-3):** >90% line coverage
- **RAG System:** >80% line coverage
- **Utilities:** >85% line coverage
- **API Endpoints:** 100% endpoint coverage

### Performance Targets
- **Unit Tests:** <1s per test, <30s total suite
- **Integration Tests:** <5s per test, <2min total suite
- **Full Suite:** <3min total

### Quality Targets
- **Zero flaky tests:** All tests pass 100/100 runs
- **Zero skipped tests:** All tests enabled and passing
- **Clear failures:** Test failures point to exact issue

---