"""
Unit tests for knowledge base quota enforcement.

Tests the check_knowledge_quota.py utility with all quota limit scenarios.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import importlib.util
from pathlib import Path
from contextlib import contextmanager

# ============================================================================
# MOCK WMILL MODULE BEFORE IMPORTING MODULE UNDER TEST
# ============================================================================

# Create a mock wmill module
mock_wmill = Mock()
sys.modules['wmill'] = mock_wmill

# Now dynamically import the module under test
MODULE_PATH = Path(__file__).parent.parent.parent / "f" / "development" / "utils" / "check_knowledge_quota.py"
spec = importlib.util.spec_from_file_location("check_knowledge_quota", MODULE_PATH)
check_knowledge_quota_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_knowledge_quota_module)

# Get the main function
check_quota = check_knowledge_quota_module.main


def create_mock_db_connection(mock_db_resource):
    """Create a mock context manager for get_db_connection that uses real DB."""
    @contextmanager
    def mock_get_db_connection(db_resource=None, use_dict_cursor=True):
        import psycopg2
        db_params = {
            "host": mock_db_resource["host"],
            "port": mock_db_resource["port"],
            "user": mock_db_resource["user"],
            "password": mock_db_resource["password"],
            "dbname": mock_db_resource["dbname"],
            "sslmode": "disable",
        }
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()
        try:
            yield conn, cur
        finally:
            cur.close()
            conn.close()
    return mock_get_db_connection


@pytest.mark.unit
class TestQuotaEnforcement:
    """Test quota enforcement for knowledge base operations."""

    @pytest.fixture
    def mock_db_resource(self, test_db_config):
        """Mock database resource that returns test database config."""
        return {
            "host": test_db_config["host"],
            "port": test_db_config["port"],
            "user": test_db_config["user"],
            "password": test_db_config["password"],
            "dbname": test_db_config["dbname"]
        }

    @pytest.fixture
    def quota_data(self):
        """Sample organization quota data."""
        return {
            "org_id": "11111111-1111-1111-1111-111111111111",
            "max_pdfs": 50,
            "max_urls": 20,
            "max_daily_ingestions": 100,
            "max_storage": 500,
            "current_pdfs": 10,
            "current_urls": 5,
            "current_storage": 100,
            "today_ingestions": 25
        }

    def test_pdf_quota_available(self, mock_db_resource, quota_data, db_with_autocommit):
        """Test PDF upload allowed when under quota."""
        # Setup: Insert test data
        db_with_autocommit.execute("""
            UPDATE organizations
            SET max_knowledge_pdfs = %s,
                current_knowledge_pdfs = %s,
                max_knowledge_storage_mb = %s,
                current_storage_mb = %s,
                max_knowledge_ingestions_per_day = %s
            WHERE id = %s
        """, (
            quota_data["max_pdfs"],
            quota_data["current_pdfs"],
            quota_data["max_storage"],
            quota_data["current_storage"],
            quota_data["max_daily_ingestions"],
            quota_data["org_id"]
        ))

        # Execute: Mock get_db_connection and call check_quota
        with patch.object(check_knowledge_quota_module, 'get_db_connection',
                          create_mock_db_connection(mock_db_resource)):
            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="pdf",
                file_size_mb=10.0,
                db_resource="test_resource"
            )

        # Assert: Should be allowed
        assert result["allowed"] is True
        assert result["quota_type"] is None
        assert result["current"] == quota_data["current_pdfs"]
        assert result["max"] == quota_data["max_pdfs"]
        assert result["remaining"] == quota_data["max_pdfs"] - quota_data["current_pdfs"]

    def test_pdf_quota_exceeded(self, mock_db_resource, quota_data, db_with_autocommit):
        """Test PDF upload blocked when quota exceeded."""
        # Setup: Set current PDFs to max
        db_with_autocommit.execute("""
            UPDATE organizations
            SET max_knowledge_pdfs = %s,
                current_knowledge_pdfs = %s
            WHERE id = %s
        """, (
            quota_data["max_pdfs"],
            quota_data["max_pdfs"],  # At limit
            quota_data["org_id"]
        ))

        # Execute: Mock get_db_connection and call check_quota
        with patch.object(check_knowledge_quota_module, 'get_db_connection',
                          create_mock_db_connection(mock_db_resource)):

            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="pdf",
                file_size_mb=5.0,
                db_resource="test_resource"
            )

        # Assert: Should be blocked
        assert result["allowed"] is False
        assert result["quota_type"] == "PDF_LIMIT_EXCEEDED"
        assert result["current"] == quota_data["max_pdfs"]
        assert result["max"] == quota_data["max_pdfs"]
        assert result["remaining"] == 0

    def test_url_quota_exceeded(self, mock_db_resource, quota_data, db_with_autocommit):
        """Test URL ingestion blocked when quota exceeded."""
        # Setup: Set current URLs to max
        db_with_autocommit.execute("""
            UPDATE organizations
            SET max_knowledge_urls = %s,
                current_knowledge_urls = %s
            WHERE id = %s
        """, (
            quota_data["max_urls"],
            quota_data["max_urls"],  # At limit
            quota_data["org_id"]
        ))

        # Execute: Mock get_db_connection and call check_quota
        with patch.object(check_knowledge_quota_module, 'get_db_connection',
                          create_mock_db_connection(mock_db_resource)):

            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="url",
                file_size_mb=0.5,
                db_resource="test_resource"
            )

        # Assert: Should be blocked
        assert result["allowed"] is False
        assert result["quota_type"] == "URL_LIMIT_EXCEEDED"
        assert result["current"] == quota_data["max_urls"]
        assert result["max"] == quota_data["max_urls"]
        assert result["remaining"] == 0

    def test_storage_quota_exceeded(self, mock_db_resource, quota_data, db_with_autocommit):
        """Test upload blocked when storage quota exceeded."""
        # Setup: Storage almost at limit
        db_with_autocommit.execute("""
            UPDATE organizations
            SET max_knowledge_storage_mb = %s,
                current_storage_mb = %s
            WHERE id = %s
        """, (
            quota_data["max_storage"],
            quota_data["max_storage"] - 5,  # 5MB remaining
            quota_data["org_id"]
        ))

        # Execute: Mock get_db_connection and call check_quota
        with patch.object(check_knowledge_quota_module, 'get_db_connection',
                          create_mock_db_connection(mock_db_resource)):

            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="pdf",
                file_size_mb=10.0,  # Too large
                db_resource="test_resource"
            )

        # Assert: Should be blocked
        assert result["allowed"] is False
        assert result["quota_type"] == "STORAGE_LIMIT_EXCEEDED"
        assert result["max"] == quota_data["max_storage"]

    def test_daily_ingestion_quota_exceeded(self, mock_db_resource, quota_data, db_with_autocommit):
        """Test ingestion blocked when daily limit exceeded."""
        # Setup: Add daily ingestion count at limit
        db_with_autocommit.execute("""
            UPDATE organizations
            SET max_knowledge_ingestions_per_day = %s
            WHERE id = %s
        """, (
            quota_data["max_daily_ingestions"],
            quota_data["org_id"]
        ))

        db_with_autocommit.execute("""
            INSERT INTO daily_ingestion_counts (organization_id, date, ingestion_count)
            VALUES (%s, CURRENT_DATE, %s)
            ON CONFLICT (organization_id, date)
            DO UPDATE SET ingestion_count = %s
        """, (
            quota_data["org_id"],
            quota_data["max_daily_ingestions"],
            quota_data["max_daily_ingestions"]
        ))

        # Execute: Mock get_db_connection and call check_quota
        with patch.object(check_knowledge_quota_module, 'get_db_connection',
                          create_mock_db_connection(mock_db_resource)):

            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="pdf",
                file_size_mb=1.0,
                db_resource="test_resource"
            )

        # Assert: Should be blocked
        assert result["allowed"] is False
        assert result["quota_type"] == "DAILY_INGESTION_LIMIT_EXCEEDED"
        assert result["current"] == quota_data["max_daily_ingestions"]
        assert result["max"] == quota_data["max_daily_ingestions"]
        assert result["remaining"] == 0

    def test_chatbot_not_found(self, mock_db_resource):
        """Test error handling for non-existent chatbot."""
        # Execute: Mock get_db_connection and call check_quota
        with patch.object(check_knowledge_quota_module, 'get_db_connection',
                          create_mock_db_connection(mock_db_resource)):

            result = check_quota(
                chatbot_id="00000000-0000-0000-0000-000000000000",
                source_type="pdf",
                file_size_mb=1.0,
                db_resource="test_resource"
            )

        # Assert: Should return not found error
        assert result["allowed"] is False
        assert result["quota_type"] == "CHATBOT_NOT_FOUND"

    def test_remaining_calculation(self, mock_db_resource, quota_data, db_with_autocommit):
        """Test correct calculation of remaining quota."""
        # Setup: Set specific quota values
        current = 15
        maximum = 50

        db_with_autocommit.execute("""
            UPDATE organizations
            SET max_knowledge_pdfs = %s,
                current_knowledge_pdfs = %s
            WHERE id = %s
        """, (maximum, current, quota_data["org_id"]))

        # Execute: Mock get_db_connection and call check_quota
        with patch.object(check_knowledge_quota_module, 'get_db_connection',
                          create_mock_db_connection(mock_db_resource)):

            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="pdf",
                file_size_mb=1.0,
                db_resource="test_resource"
            )

        # Assert: Remaining should be correctly calculated
        assert result["allowed"] is True
        assert result["remaining"] == maximum - current  # Should be 35

    def test_edge_case_exactly_at_storage_limit(self, mock_db_resource, quota_data, db_with_autocommit):
        """Test storage quota when exactly at limit (edge case)."""
        # Setup: Storage at exactly max - 1MB
        db_with_autocommit.execute("""
            UPDATE organizations
            SET max_knowledge_storage_mb = %s,
                current_storage_mb = %s
            WHERE id = %s
        """, (
            100,
            99,  # Exactly 1MB remaining
            quota_data["org_id"]
        ))

        # Execute: Test 1 - 0.5MB file should be allowed
        with patch.object(check_knowledge_quota_module, 'get_db_connection',
                          create_mock_db_connection(mock_db_resource)):
            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="pdf",
                file_size_mb=0.5,
                db_resource="test_resource"
            )
        assert result["allowed"] is True

        # Execute: Test 2 - 1.5MB file should be blocked
        with patch.object(check_knowledge_quota_module, 'get_db_connection',
                          create_mock_db_connection(mock_db_resource)):
            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="pdf",
                file_size_mb=1.5,
                db_resource="test_resource"
            )
        assert result["allowed"] is False
        assert result["quota_type"] == "STORAGE_LIMIT_EXCEEDED"

    def test_different_plan_tiers(self, mock_db_resource, db_with_autocommit):
        """Test that different organizations can have different quotas."""
        # Setup: Create org with free tier (low limits)
        db_with_autocommit.execute("""
            UPDATE organizations
            SET max_knowledge_pdfs = 10,
                current_knowledge_pdfs = 5,
                plan_tier = 'free'
            WHERE id = '11111111-1111-1111-1111-111111111111'
        """)

        # Execute: Test free tier chatbot
        with patch.object(check_knowledge_quota_module, 'get_db_connection',
                          create_mock_db_connection(mock_db_resource)):
            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="pdf",
                file_size_mb=1.0,
                db_resource="test_resource"
            )

        # Assert: Should respect free tier limits
        assert result["allowed"] is True
        assert result["max"] == 10
        assert result["remaining"] == 5

    def test_doc_type_uses_pdf_quota(self, mock_db_resource, quota_data, db_with_autocommit):
        """Test that 'doc' source type uses PDF quota limits."""
        # Setup: Set PDF quota
        db_with_autocommit.execute("""
            UPDATE organizations
            SET max_knowledge_pdfs = %s,
                current_knowledge_pdfs = %s
            WHERE id = %s
        """, (
            quota_data["max_pdfs"],
            quota_data["current_pdfs"],
            quota_data["org_id"]
        ))

        # Execute: Check quota for 'doc' type
        with patch.object(check_knowledge_quota_module, 'get_db_connection',
                          create_mock_db_connection(mock_db_resource)):
            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="doc",
                file_size_mb=1.0,
                db_resource="test_resource"
            )

        # Assert: Should use PDF quota
        assert result["allowed"] is True
        assert result["current"] == quota_data["current_pdfs"]
        assert result["max"] == quota_data["max_pdfs"]

    def test_unknown_source_type_allows_with_default_remaining(self, mock_db_resource, quota_data, db_with_autocommit):
        """Test that unknown source types are allowed with default remaining."""
        # Setup: Basic organization setup
        db_with_autocommit.execute("""
            UPDATE organizations
            SET max_knowledge_pdfs = %s,
                current_knowledge_pdfs = %s
            WHERE id = %s
        """, (
            quota_data["max_pdfs"],
            quota_data["current_pdfs"],
            quota_data["org_id"]
        ))

        # Execute: Check quota for unknown type
        with patch.object(check_knowledge_quota_module, 'get_db_connection',
                          create_mock_db_connection(mock_db_resource)):
            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="unknown_type",
                file_size_mb=1.0,
                db_resource="test_resource"
            )

        # Assert: Should be allowed with default remaining
        assert result["allowed"] is True
        assert result["remaining"] == 999  # Default value for unknown types

    def test_url_quota_available(self, mock_db_resource, quota_data, db_with_autocommit):
        """Test URL ingestion allowed when under quota."""
        # Setup: Set URL quota well under limit
        db_with_autocommit.execute("""
            UPDATE organizations
            SET max_knowledge_urls = %s,
                current_knowledge_urls = %s
            WHERE id = %s
        """, (
            quota_data["max_urls"],
            quota_data["current_urls"],
            quota_data["org_id"]
        ))

        # Execute: Check quota for URL
        with patch.object(check_knowledge_quota_module, 'get_db_connection',
                          create_mock_db_connection(mock_db_resource)):
            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="url",
                file_size_mb=0.1,
                db_resource="test_resource"
            )

        # Assert: Should be allowed
        assert result["allowed"] is True
        assert result["quota_type"] is None
        assert result["current"] == quota_data["current_urls"]
        assert result["max"] == quota_data["max_urls"]
        assert result["remaining"] == quota_data["max_urls"] - quota_data["current_urls"]
