"""
Pytest configuration and shared fixtures for testing the WhatsApp chatbot flow.

This module provides:
- Database fixtures (connection, transaction management, cleanup)
- Mock fixtures (Windmill, LLM, WhatsApp API)
- Test data factories
- Utilities for testing
"""

import os
import sys
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, Generator
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import test harness modules
from tests.test_harness.windmill_mock import WindmillMock
from tests.test_harness.llm_mock import LLMMock
from tests.test_harness.whatsapp_mock import WhatsAppMock


# ============================================================================
# CONFIGURATION
# ============================================================================

@pytest.fixture(scope="session")
def test_db_config() -> Dict[str, Any]:
    """Database configuration for tests."""
    return {
        "host": os.getenv("TEST_DB_HOST", "localhost"),
        "port": int(os.getenv("TEST_DB_PORT", "5434")),
        "user": os.getenv("TEST_DB_USER", "test_user"),
        "password": os.getenv("TEST_DB_PASSWORD", "test_password"),
        "dbname": os.getenv("TEST_DB_NAME", "test_business_logic"),
        "sslmode": "disable",
    }


@pytest.fixture(scope="session")
def test_env_vars() -> Dict[str, str]:
    """Environment variables for tests."""
    return {
        "WHATSAPP_PHONE_NUMBER_ID": "test_phone_123",
        "WHATSAPP_ACCESS_TOKEN": "test_token_xyz",
        "OWNER_EMAIL": "test@example.com",
        "GOOGLE_API_KEY": "test_google_key",
        "OPENAI_API_KEY": "test_openai_key",
        "WM_WORKSPACE": "test_workspace",
        "WM_TOKEN": "test_windmill_token",
        "WM_BASE_URL": "http://localhost:8000",
    }


@pytest.fixture(scope="session", autouse=True)
def set_test_env_vars(test_env_vars):
    """Automatically set environment variables for all tests."""
    import os

    # Store original values
    original_values = {}
    for key, value in test_env_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value

    yield

    # Restore original values
    for key, original_value in original_values.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def db_connection(test_db_config):
    """
    Create a database connection for the entire test session.
    This connection is used to reset the database between tests.
    """
    conn = psycopg2.connect(**test_db_config)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def db_cursor(db_connection):
    """
    Provide a cursor for each test function.
    Uses a transaction that gets rolled back after each test.
    """
    # Start a transaction
    db_connection.autocommit = False
    cursor = db_connection.cursor(cursor_factory=RealDictCursor)
    
    yield cursor
    
    # Rollback transaction after test
    db_connection.rollback()
    cursor.close()
    db_connection.autocommit = True


@pytest.fixture(scope="function")
def clean_db(db_connection, test_env_vars):
    """
    Reset database to a clean state before each test.
    Runs the drop, create, and seed SQL scripts.
    """
    cursor = db_connection.cursor()
    
    # Read and execute SQL files
    sql_dir = PROJECT_ROOT / "db"
    
    # Drop tables
    with open(sql_dir / "drop.sql") as f:
        cursor.execute(f.read())
    
    # Create schema
    with open(sql_dir / "create.sql") as f:
        cursor.execute(f.read())
    
    # Seed data (with environment variable substitution)
    with open(sql_dir / "seed.sql") as f:
        seed_sql = f.read()
        # Replace environment variables
        for key, value in test_env_vars.items():
            seed_sql = seed_sql.replace(f"${{{key}}}", value)
        cursor.execute(seed_sql)
    
    cursor.close()
    
    yield  # Test runs here
    
    # No cleanup needed - next test will reset


@pytest.fixture
def db_with_data(clean_db, db_cursor):
    """
    Provides a database with seed data and a cursor for queries.
    This is the most commonly used database fixture.
    """
    return db_cursor


@pytest.fixture
def db_with_autocommit(clean_db, db_connection):
    """
    Provides a database cursor with autocommit enabled.

    Use this fixture for tests that call external scripts/processes
    that create their own database connections, as they need to see
    committed data (not just data in the current transaction).

    WARNING: Changes made with this fixture are NOT automatically
    rolled back, so clean_db is used to reset between tests.
    """
    cursor = db_connection.cursor(cursor_factory=RealDictCursor)
    yield cursor
    cursor.close()


# ============================================================================
# MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_wmill():
    """Mock Windmill functions (get_resource, get_variable)."""
    return WindmillMock()


@pytest.fixture
def mock_llm():
    """Mock LLM providers (OpenAI, Google)."""
    return LLMMock()


@pytest.fixture
def mock_whatsapp():
    """Mock WhatsApp API calls."""
    return WhatsAppMock()


@pytest.fixture
def mock_all_external(mock_wmill, mock_llm, mock_whatsapp):
    """
    Mock all external dependencies at once.
    Useful for integration tests.
    """
    with patch('wmill.get_resource', mock_wmill.get_resource), \
         patch('wmill.get_variable', mock_wmill.get_variable), \
         patch('openai.OpenAI', mock_llm.get_openai_client), \
         patch('google.generativeai.GenerativeModel', mock_llm.get_google_client), \
         patch('requests.post', mock_whatsapp.post):
        
        yield {
            "wmill": mock_wmill,
            "llm": mock_llm,
            "whatsapp": mock_whatsapp,
        }


# ============================================================================
# TEST DATA FACTORIES
# ============================================================================

@pytest.fixture
def sample_webhook_payload():
    """Generate a sample WhatsApp webhook payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "test_entry_123",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "test_phone_123"
                            },
                            "contacts": [
                                {
                                    "profile": {
                                        "name": "Test User"
                                    },
                                    "wa_id": "15559876543"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "15559876543",
                                    "id": "wamid.test.message.001",
                                    "timestamp": "1234567890",
                                    "text": {
                                        "body": "Hello, can you help me?"
                                    },
                                    "type": "text"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_context_payload():
    """Generate a sample context payload from Step 1."""
    return {
        "proceed": True,
        "webhook_event_id": 1,
        "chatbot": {
            "id": "22222222-2222-2222-2222-222222222222",
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "name": "Test Bot",
            "system_prompt": "You are a helpful assistant.",
            "persona": "Friendly and professional",
            "model_name": "gemini-pro",
            "temperature": 0.7,
            "wa_token": "test_token_xyz",
            "rag_config": {
                "enabled": False,
                "index": None,
                "namespace": None
            }
        },
        "user": {
            "id": "44444444-4444-4444-4444-444444444444",
            "phone": "15559876543",
            "name": "Test User",
            "variables": {},
            "tags": []
        },
        "history": [],
        "tools": [],
        "usage_info": {
            "has_quota": True,
            "messages_used": 0,
            "tokens_used": 0,
            "messages_remaining": 1000,
            "tokens_remaining": 1000000
        }
    }


@pytest.fixture
def sample_llm_result():
    """Generate a sample LLM response from Step 2."""
    return {
        "reply_text": "Hello! I'd be happy to help you. What do you need assistance with?",
        "updated_variables": {},
        "usage_info": {
            "provider": "google",
            "model": "gemini-pro",
            "tokens_input": 150,
            "tokens_output": 80,
        }
    }


@pytest.fixture
def gemini_simple_response():
    """Simple text response from Gemini (no tools)"""
    return {
        "reply_text": "Hello! How can I help?",
        "updated_variables": {},
        "tool_executions": [],
        "retrieved_sources": [],
        "usage_info": {
            "provider": "google",
            "model": "gemini-pro",
            "tokens_input": 50,
            "tokens_output": 20,
            "tool_calls": 0,
            "rag_used": False,
            "chunks_retrieved": 0,
            "iterations": 1
        }
    }


@pytest.fixture
def gemini_tool_call_response():
    """Gemini response with tool call"""
    return {
        "reply_text": "I've checked the weather for you.",
        "updated_variables": {},
        "tool_executions": [
            {
                "tool_name": "get_weather",
                "arguments": {"city": "NYC"},
                "result": {"temperature": 72, "condition": "sunny"}
            }
        ],
        "retrieved_sources": [],
        "usage_info": {
            "provider": "google",
            "model": "gemini-pro",
            "tokens_input": 100,
            "tokens_output": 50,
            "tool_calls": 1,
            "rag_used": False,
            "chunks_retrieved": 0,
            "iterations": 2
        }
    }


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


@pytest.fixture
def openai_embedding_1536():
    """Valid 1536-dimensional embedding for testing"""
    return "[" + ", ".join(["0.1"] * 1536) + "]"


# ============================================================================
# UTILITY FIXTURES
# ============================================================================

@pytest.fixture
def assert_db_state():
    """Helper fixture for asserting database state."""
    def _assert(cursor, table: str, conditions: Dict[str, Any], expected_count: int = 1):
        """
        Assert that a table has the expected number of rows matching conditions.
        
        Args:
            cursor: Database cursor
            table: Table name
            conditions: Dict of column: value conditions
            expected_count: Expected number of matching rows
        """
        where_clauses = " AND ".join(f"{k} = %s" for k in conditions.keys())
        query = f"SELECT COUNT(*) as count FROM {table} WHERE {where_clauses}"
        
        cursor.execute(query, tuple(conditions.values()))
        result = cursor.fetchone()
        
        assert result["count"] == expected_count, \
            f"Expected {expected_count} rows in {table} matching {conditions}, found {result['count']}"
    
    return _assert


@pytest.fixture
def query_helper(db_cursor):
    """Helper fixture for common database queries."""
    class QueryHelper:
        def __init__(self, cursor):
            self.cursor = cursor
        
        def get_organization(self, org_id: str) -> Dict:
            self.cursor.execute("SELECT * FROM organizations WHERE id = %s", (org_id,))
            return self.cursor.fetchone()
        
        def get_chatbot(self, chatbot_id: str) -> Dict:
            self.cursor.execute("SELECT * FROM chatbots WHERE id = %s", (chatbot_id,))
            return self.cursor.fetchone()
        
        def get_contact(self, contact_id: str) -> Dict:
            self.cursor.execute("SELECT * FROM contacts WHERE id = %s", (contact_id,))
            return self.cursor.fetchone()
        
        def get_messages(self, contact_id: str) -> list:
            self.cursor.execute(
                "SELECT * FROM messages WHERE contact_id = %s ORDER BY created_at",
                (contact_id,)
            )
            return self.cursor.fetchall()
        
        def get_usage_logs(self, org_id: str) -> list:
            self.cursor.execute(
                "SELECT * FROM usage_logs WHERE organization_id = %s ORDER BY created_at",
                (org_id,)
            )
            return self.cursor.fetchall()
        
        def get_webhook_event(self, message_id: str) -> Dict:
            self.cursor.execute(
                "SELECT * FROM webhook_events WHERE whatsapp_message_id = %s",
                (message_id,)
            )
            return self.cursor.fetchone()
    
    return QueryHelper(db_cursor)


# ============================================================================
# SESSION HOOKS
# ============================================================================

def pytest_configure(config):
    """Pytest configuration hook."""
    # Add custom markers
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "db: Tests requiring database")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Auto-mark database tests
        if "db_cursor" in item.fixturenames or "clean_db" in item.fixturenames:
            item.add_marker(pytest.mark.db)
        
        # Auto-mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)