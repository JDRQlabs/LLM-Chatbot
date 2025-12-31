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
        assert result["reason"] == "Already Processed"

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

    @patch('psycopg2.connect')
    def test_successful_context_loading(self, mock_connect):
        """Test successful loading of all context data"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Setup responses
        mock_cursor.fetchone.side_effect = [
            None,  # No duplicate
            {"id": 1},  # Webhook event created
            {  # Chatbot + organization data
                "id": "chatbot-123",
                "organization_id": "org-456",
                "name": "Test Bot",
                "system_prompt": "You are helpful",
                "persona": "Friendly",
                "model_name": "gemini-pro",
                "temperature": 0.7,
                "rag_enabled": False,
                "whatsapp_access_token": "token_xyz",
                "is_active": True,
                "fallback_message_error": "Error occurred",
                "fallback_message_limit": "Limit reached",
                "org_name": "Test Org",
                "plan_tier": "pro",
                "org_is_active": True,
                "message_limit_monthly": 1000,
                "token_limit_monthly": 100000,
                "billing_period_start": "2025-01-01",
                "billing_period_end": "2025-02-01"
            },
            {  # Usage from get_current_usage()
                "messages_used": 10,
                "tokens_used": 5000
            },
            {  # Contact upserted
                "id": "contact-789",
                "conversation_mode": "auto",
                "variables": {},
                "tags": []
            }
        ]

        # Mock fetchall queries (tools, history)
        mock_cursor.fetchall.side_effect = [
            [],  # No tools/integrations
            []   # No chat history
        ]

        result = step1_main(
            whatsapp_phone_id="123456",
            user_phone="16315551234",
            message_id="msg-new-123",
            user_name="John Doe"
        )

        # Assertions
        assert result["proceed"] is True
        assert result["chatbot"]["id"] == "chatbot-123"
        assert result["chatbot"]["name"] == "Test Bot"
        assert result["user"]["id"] == "contact-789"
        assert result["user"]["name"] == "John Doe"
        assert "history" in result
        assert "tools" in result
        assert "usage_info" in result

    @patch('psycopg2.connect')
    def test_inactive_organization(self, mock_connect):
        """Test handling when organization is inactive"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.side_effect = [
            None,  # No duplicate
            {"id": 1},  # Webhook event
            {  # Chatbot with inactive org
                "id": "bot-123",
                "organization_id": "org-456",
                "is_active": True,
                "org_is_active": False,  # Org is inactive!
                "message_limit_monthly": 1000,
                "token_limit_monthly": 100000
            }
        ]

        result = step1_main(
            whatsapp_phone_id="123",
            user_phone="16315551234",
            message_id="msg-123",
            user_name="Test"
        )

        assert result["proceed"] is False
        assert result["reason"] == "Service Inactive"
        assert result["notify_admin"] is True

    @patch('psycopg2.connect')
    def test_usage_limit_exceeded(self, mock_connect):
        """Test handling when usage limits are exceeded"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.side_effect = [
            None,  # No duplicate
            {"id": 1},  # Webhook event
            {  # Chatbot data
                "id": "bot-123",
                "organization_id": "org-456",
                "is_active": True,
                "org_is_active": True,
                "message_limit_monthly": 100,  # Low limit
                "token_limit_monthly": 10000,
                "billing_period_start": "2025-01-01",
                "billing_period_end": "2025-02-01",
                "whatsapp_access_token": "token_xyz"
            },
            {  # Usage from get_current_usage() - EXCEEDED!
                "messages_used": 150,  # Over the limit of 100
                "tokens_used": 5000
            }
        ]

        result = step1_main(
            whatsapp_phone_id="123",
            user_phone="16315551234",
            message_id="msg-123",
            user_name="Test"
        )

        assert result["proceed"] is False
        assert result["reason"] == "Usage Limit Exceeded"
        assert result["notify_admin"] is True
        assert "usage_info" in result

    @patch('psycopg2.connect')
    def test_manual_mode_human_takeover(self, mock_connect):
        """Test handling when contact is in manual mode"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.side_effect = [
            None,  # No duplicate
            {"id": 1},  # Webhook event
            {  # Chatbot data
                "id": "bot-123",
                "organization_id": "org-456",
                "is_active": True,
                "org_is_active": True,
                "message_limit_monthly": 1000,
                "token_limit_monthly": 100000,
                "billing_period_start": "2025-01-01",
                "billing_period_end": "2025-02-01"
            },
            {  # Usage from get_current_usage()
                "messages_used": 10,
                "tokens_used": 5000
            },
            {  # Contact in manual mode
                "id": "contact-789",
                "conversation_mode": "manual",  # Human takeover!
                "variables": {},
                "tags": []
            }
        ]

        result = step1_main(
            whatsapp_phone_id="123",
            user_phone="16315551234",
            message_id="msg-123",
            user_name="Test"
        )

        assert result["proceed"] is False
        assert result["reason"] == "Manual Mode - Human Agent Required"

    @patch('psycopg2.connect')
    def test_chat_history_loading(self, mock_connect):
        """Test that chat history is loaded and reversed to chronological order"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Setup basic responses
        mock_cursor.fetchone.side_effect = [
            None,  # No duplicate
            {"id": 1},  # Webhook event
            {  # Chatbot
                "id": "bot-123",
                "organization_id": "org-456",
                "name": "Test Bot",
                "system_prompt": "Helpful",
                "persona": "Friendly",
                "model_name": "gemini-pro",
                "temperature": 0.7,
                "rag_enabled": False,
                "whatsapp_access_token": "token",
                "is_active": True,
                "org_is_active": True,
                "message_limit_monthly": 1000,
                "token_limit_monthly": 100000,
                "billing_period_start": "2025-01-01",
                "billing_period_end": "2025-02-01",
                "fallback_message_error": "Error",
                "fallback_message_limit": "Limit"
            },
            {  # Usage from get_current_usage()
                "messages_used": 10,
                "tokens_used": 5000
            },
            {  # Contact
                "id": "contact-789",
                "conversation_mode": "auto",
                "variables": {},
                "tags": []
            }
        ]

        # Mock history (DESC order from DB)
        history_rows = [
            {"role": "assistant", "content": "Response 2", "tool_calls": None, "tool_results": None, "created_at": "2025-01-15 10:02"},
            {"role": "user", "content": "Question 2", "tool_calls": None, "tool_results": None, "created_at": "2025-01-15 10:01"},
            {"role": "assistant", "content": "Response 1", "tool_calls": None, "tool_results": None, "created_at": "2025-01-15 10:00"}
        ]

        mock_cursor.fetchall.side_effect = [
            [],  # Tools
            history_rows  # History
        ]

        result = step1_main(
            whatsapp_phone_id="123",
            user_phone="16315551234",
            message_id="msg-123",
            user_name="Test"
        )

        assert result["proceed"] is True
        # History should be reversed to chronological (oldest first)
        assert len(result["history"]) == 3
        assert result["history"][0]["content"] == "Response 1"  # Oldest
        assert result["history"][2]["content"] == "Response 2"  # Newest

    @patch('psycopg2.connect')
    def test_db_connection_error(self, mock_connect):
        """Test handling of database connection failures"""
        # Simulate connection failure
        mock_connect.side_effect = Exception("Connection refused")

        result = step1_main(
            whatsapp_phone_id="123",
            user_phone="16315551234",
            message_id="msg-123",
            user_name="Test"
        )

        assert result["proceed"] is False
        assert "DB Connection Failed" in result["reason"]
        assert result["notify_admin"] is True

    @patch('psycopg2.connect')
    def test_retry_failed_message(self, mock_connect):
        """Test that failed messages can be retried"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Setup: message exists with 'failed' status
        mock_cursor.fetchone.side_effect = [
            {"id": 1, "status": "failed", "processed_at": "2025-01-15 10:00"},  # Failed message
            {  # Chatbot (after retry allowed)
                "id": "bot-123",
                "organization_id": "org-456",
                "name": "Test Bot",
                "system_prompt": "Helpful",
                "persona": "Friendly",
                "model_name": "gemini-pro",
                "temperature": 0.7,
                "rag_enabled": False,
                "whatsapp_access_token": "token",
                "is_active": True,
                "org_is_active": True,
                "message_limit_monthly": 1000,
                "token_limit_monthly": 100000,
                "billing_period_start": "2025-01-01",
                "billing_period_end": "2025-02-01",
                "fallback_message_error": "Error",
                "fallback_message_limit": "Limit"
            },
            {  # Usage from get_current_usage()
                "messages_used": 10,
                "tokens_used": 5000
            },
            {  # Contact
                "id": "contact-789",
                "conversation_mode": "auto",
                "variables": {},
                "tags": []
            }
        ]

        mock_cursor.fetchall.side_effect = [
            [],  # No tools
            []   # No history
        ]

        result = step1_main(
            whatsapp_phone_id="123",
            user_phone="16315551234",
            message_id="msg-retry",
            user_name="Test"
        )

        # Should proceed with retry
        assert result["proceed"] is True
        assert result["webhook_event_id"] == 1  # Reuses existing webhook event


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
