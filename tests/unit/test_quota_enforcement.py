"""
Unit tests for knowledge base quota enforcement.

Tests the check_knowledge_quota.py utility with all quota limit scenarios.
"""

import pytest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "f" / "development" / "utils"))

from check_knowledge_quota import main as check_quota


@pytest.mark.unit
class TestQuotaEnforcement:
    """Test quota enforcement for knowledge base operations."""

    @pytest.fixture
    def mock_wmill_resource(self):
        """Mock Windmill resource for database connection."""
        return {
            "host": "localhost",
            "port": 5434,  # Test database port
            "user": "test_user",
            "password": "test_password",
            "dbname": "test_business_logic"  # Test database name
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

    def test_pdf_quota_available(self, mock_wmill_resource, quota_data, db_with_autocommit):
        """Test PDF upload allowed when under quota."""
        with patch('wmill.get_resource', return_value=mock_wmill_resource):
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

            # Test: Check quota for PDF (well under limit)
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

    def test_pdf_quota_exceeded(self, mock_wmill_resource, quota_data, db_with_autocommit):
        """Test PDF upload blocked when quota exceeded."""
        with patch('wmill.get_resource', return_value=mock_wmill_resource):
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

            # Test: Try to add another PDF
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

    def test_url_quota_exceeded(self, mock_wmill_resource, quota_data, db_with_autocommit):
        """Test URL ingestion blocked when quota exceeded."""
        with patch('wmill.get_resource', return_value=mock_wmill_resource):
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

            # Test: Try to add another URL
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

    def test_storage_quota_exceeded(self, mock_wmill_resource, quota_data, db_with_autocommit):
        """Test upload blocked when storage quota exceeded."""
        with patch('wmill.get_resource', return_value=mock_wmill_resource):
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

            # Test: Try to upload 10MB file (exceeds remaining space)
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

    def test_daily_ingestion_quota_exceeded(self, mock_wmill_resource, quota_data, db_with_autocommit):
        """Test ingestion blocked when daily limit exceeded."""
        with patch('wmill.get_resource', return_value=mock_wmill_resource):
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

            # Test: Try to ingest another document
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

    def test_chatbot_not_found(self, mock_wmill_resource):
        """Test error handling for non-existent chatbot."""
        with patch('wmill.get_resource', return_value=mock_wmill_resource):
            # Test: Check quota for non-existent chatbot
            result = check_quota(
                chatbot_id="00000000-0000-0000-0000-000000000000",
                source_type="pdf",
                file_size_mb=1.0,
                db_resource="test_resource"
            )

            # Assert: Should return not found error
            assert result["allowed"] is False
            assert result["quota_type"] == "CHATBOT_NOT_FOUND"

    def test_remaining_calculation(self, mock_wmill_resource, quota_data, db_with_autocommit):
        """Test correct calculation of remaining quota."""
        with patch('wmill.get_resource', return_value=mock_wmill_resource):
            # Setup: Set specific quota values
            current = 15
            maximum = 50

            db_with_autocommit.execute("""
                UPDATE organizations
                SET max_knowledge_pdfs = %s,
                    current_knowledge_pdfs = %s
                WHERE id = %s
            """, (maximum, current, quota_data["org_id"]))

            # Test: Check quota
            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="pdf",
                file_size_mb=1.0,
                db_resource="test_resource"
            )

            # Assert: Remaining should be correctly calculated
            assert result["allowed"] is True
            assert result["remaining"] == maximum - current  # Should be 35

    def test_edge_case_exactly_at_storage_limit(self, mock_wmill_resource, quota_data, db_with_autocommit):
        """Test storage quota when exactly at limit (edge case)."""
        with patch('wmill.get_resource', return_value=mock_wmill_resource):
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

            # Test 1: 0.5MB file should be allowed
            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="pdf",
                file_size_mb=0.5,
                db_resource="test_resource"
            )
            assert result["allowed"] is True

            # Test 2: 1.5MB file should be blocked
            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="pdf",
                file_size_mb=1.5,
                db_resource="test_resource"
            )
            assert result["allowed"] is False
            assert result["quota_type"] == "STORAGE_LIMIT_EXCEEDED"

    def test_different_plan_tiers(self, mock_wmill_resource, db_with_autocommit):
        """Test that different organizations can have different quotas."""
        with patch('wmill.get_resource', return_value=mock_wmill_resource):
            # Setup: Create two chatbots with different org quotas
            # Org 1: Free tier (low limits)
            db_with_autocommit.execute("""
                UPDATE organizations
                SET max_knowledge_pdfs = 10,
                    current_knowledge_pdfs = 5,
                    plan_tier = 'free'
                WHERE id = '11111111-1111-1111-1111-111111111111'
            """)

            # Test: Free tier chatbot
            result = check_quota(
                chatbot_id="22222222-2222-2222-2222-222222222222",
                source_type="pdf",
                file_size_mb=1.0,
                db_resource="test_resource"
            )
            assert result["allowed"] is True
            assert result["max"] == 10
            assert result["remaining"] == 5
