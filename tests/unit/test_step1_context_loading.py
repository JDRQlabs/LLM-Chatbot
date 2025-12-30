"""
Unit tests for Step 1: Context loading and validation

Tests Step 1's ability to:
- Validate chatbots and load configuration
- Check for duplicate messages (idempotency)
- Load user data and conversation history
- Handle various error conditions
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from psycopg2.extras import RealDictCursor

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../f/development'))

# Mock wmill module before importing step1
mock_wmill = Mock()
mock_wmill.get_resource.return_value = {
    "host": "localhost",
    "port": 5432,
    "user": "test_user",
    "password": "test_password",
    "dbname": "test_db"
}
sys.modules['wmill'] = mock_wmill

# Import the module under test
import importlib.util
spec = importlib.util.spec_from_file_location(
    "step1",
    os.path.join(os.path.dirname(__file__), '../../f/development/1_whatsapp_context_loading.py')
)
step1_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step1_module)
step1_main = step1_module.main


class TestStep1ContextLoading:
    """Test Step 1's context loading functionality"""

    @patch('psycopg2.connect')
    def test_duplicate_message_detection(self, mock_connect):
        """Test that duplicate messages are detected via whatsapp_message_id"""
        # Setup mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate duplicate message already exists (RealDictCursor returns dict-like rows)
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "status": "completed",
            "processed_at": "2025-01-15 10:00:00"
        }

        result = step1_main(
            whatsapp_phone_id="123456123",
            user_phone="16315551181",
            message_id="ABGGFlA5Fpa",  # Same message ID
            user_name="Test User"
        )

        # Assertions
        assert result["proceed"] is False
        assert result["reason"] == "Duplicate - Already Processed"

    @patch('psycopg2.connect')
    def test_chatbot_not_found(self, mock_connect):
        """Test handling when chatbot doesn't exist for phone_number_id"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Setup responses: no duplicate, create webhook event, but no chatbot found
        mock_cursor.fetchone.side_effect = [
            None,  # No duplicate message
            {"id": 999},   # Webhook event ID created (RealDictCursor returns dict)
            None   # No chatbot found
        ]

        result = step1_main(
            whatsapp_phone_id="999999999",  # Non-existent phone ID
            user_phone="16315551181",
            message_id="ABGGFlA5Fpa_NEW",
            user_name="Test User"
        )

        # Assertions
        assert result["proceed"] is False
        assert result["reason"] == "Chatbot not found"
        assert result["notify_admin"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
