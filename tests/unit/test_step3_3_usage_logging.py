"""
Unit tests for Step 3.3: Usage Logging

Tests Step 3.3's ability to:
- Log token usage and message counts
- Calculate costs accurately
- Update usage_summary for quick quota checks
- Skip logging when previous steps failed
- Handle token estimation fallbacks
- Test different provider pricing
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../f/development'))

# Mock wmill module before importing step3_3
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
    "step3_3",
    os.path.join(os.path.dirname(__file__), '../../f/development/3_3_log_usage.py')
)
step3_3_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step3_3_module)
step3_3_main = step3_3_module.main
_get_cost_per_1k_tokens = step3_3_module._get_cost_per_1k_tokens


class TestStep3_3UsageLogging:
    """Test Step 3.3's usage logging functionality"""

    @patch('psycopg2.connect')
    def test_successful_usage_logging(self, mock_connect):
        """Test successful logging of usage data"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock the RETURNING id from INSERT
        mock_cursor.fetchone.return_value = {"id": 12345}

        result = step3_3_main(
            context_payload={
                "proceed": True,
                "chatbot": {
                    "id": "chatbot-123",
                    "organization_id": "org-456",
                    "model_name": "gemini-3-flash-preview"
                },
                "user": {"id": "contact-789"}
            },
            llm_result={
                "reply_text": "Hello! How can I help you today?",
                "usage_info": {
                    "provider": "google",
                    "model": "gemini-3-flash-preview",
                    "tokens_input": 50,
                    "tokens_output": 30
                }
            },
            send_result={"success": True},
            webhook_event_id=1
        )

        # Assertions
        assert result["success"] is True
        assert result["usage_log_id"] == 12345
        assert result["tokens_used"] == 80  # 50 + 30
        assert result["message_count"] == 1
        assert result["estimated_cost"] > 0

        # Verify two SQL executes (INSERT usage_logs, UPDATE usage_summary)
        assert mock_cursor.execute.call_count == 2

        # Verify INSERT usage_logs call
        insert_call = mock_cursor.execute.call_args_list[0]
        assert "INSERT INTO usage_logs" in insert_call[0][0]
        assert insert_call[0][1] == (
            "org-456",
            "chatbot-123",
            "contact-789",
            1,  # webhook_event_id
            1,  # message_count
            50,  # tokens_input
            30,  # tokens_output
            80,  # tokens_total
            "gemini-3-flash-preview",
            "google",
            pytest.approx(0.00002, rel=1e-6),  # estimated_cost (80 tokens * 0.00025 / 1000 = 0.00002)
        )

        # Verify UPDATE usage_summary call
        update_call = mock_cursor.execute.call_args_list[1]
        assert "INSERT INTO usage_summary" in update_call[0][0]
        assert "ON CONFLICT (organization_id)" in update_call[0][0]
        assert "DO UPDATE SET" in update_call[0][0]

        # Verify commit
        assert mock_conn.commit.called

    @patch('psycopg2.connect')
    def test_token_estimation_fallback(self, mock_connect):
        """Test token estimation when LLM doesn't provide usage info"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"id": 100}

        # LLM result without usage_info
        result = step3_3_main(
            context_payload={
                "proceed": True,
                "chatbot": {
                    "id": "chatbot-123",
                    "organization_id": "org-456",
                    "model_name": "gemini-pro"
                },
                "user": {"id": "contact-789"}
            },
            llm_result={
                "reply_text": "This is a test response with some text.",  # ~40 chars = ~10 tokens
                "usage_info": {}  # No token counts
            },
            send_result={"success": True}
        )

        assert result["success"] is True
        assert result["tokens_used"] > 0  # Should have estimated tokens

    @patch('psycopg2.connect')
    def test_cost_calculation_openai(self, mock_connect):
        """Test cost calculation for OpenAI models"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"id": 100}

        result = step3_3_main(
            context_payload={
                "proceed": True,
                "chatbot": {
                    "id": "chatbot-123",
                    "organization_id": "org-456",
                    "model_name": "gpt-4o"
                },
                "user": {"id": "contact-789"}
            },
            llm_result={
                "usage_info": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "tokens_input": 1000,
                    "tokens_output": 500
                }
            },
            send_result={"success": True}
        )

        assert result["success"] is True
        # gpt-4o costs $0.005 per 1k tokens
        # 1500 tokens * 0.005 / 1000 = 0.0075
        assert result["estimated_cost"] == pytest.approx(0.0075, rel=1e-6)

    @patch('psycopg2.connect')
    def test_skip_when_step1_failed(self, mock_connect):
        """Test that usage is not logged when Step 1 failed"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = step3_3_main(
            context_payload={
                "proceed": False,  # Step 1 failed
                "reason": "Chatbot not found"
            },
            llm_result={"usage_info": {}},
            send_result={"success": True}
        )

        assert result["success"] is False
        assert "Step 1 failed" in result["error"]
        assert not mock_cursor.execute.called

    @patch('psycopg2.connect')
    def test_skip_when_step2_failed(self, mock_connect):
        """Test that usage is not logged when Step 2 (LLM) failed"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = step3_3_main(
            context_payload={
                "proceed": True,
                "chatbot": {"id": "chatbot-123", "organization_id": "org-456"},
                "user": {"id": "contact-789"}
            },
            llm_result={
                "error": "LLM quota exceeded"  # Step 2 failed
            },
            send_result={"success": True}
        )

        assert result["success"] is False
        assert "Step 2 failed" in result["error"]
        assert not mock_cursor.execute.called

    @patch('psycopg2.connect')
    def test_skip_when_step3_failed(self, mock_connect):
        """Test that usage is not logged when Step 3 (send to WhatsApp) failed"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = step3_3_main(
            context_payload={
                "proceed": True,
                "chatbot": {"id": "chatbot-123", "organization_id": "org-456"},
                "user": {"id": "contact-789"}
            },
            llm_result={"usage_info": {}},
            send_result={
                "success": False,  # Message not delivered!
                "error": "WhatsApp API error"
            }
        )

        assert result["success"] is False
        assert "Step 3 failed" in result["error"]
        assert "message not delivered" in result["error"]
        assert not mock_cursor.execute.called

    @patch('psycopg2.connect')
    def test_database_error_rollback(self, mock_connect):
        """Test that database errors trigger rollback"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate database error
        mock_cursor.execute.side_effect = Exception("Database constraint violation")

        result = step3_3_main(
            context_payload={
                "proceed": True,
                "chatbot": {"id": "chatbot-123", "organization_id": "org-456"},
                "user": {"id": "contact-789"}
            },
            llm_result={"usage_info": {}},
            send_result={"success": True}
        )

        assert result["success"] is False
        assert "Database constraint violation" in result["error"]
        
        # Verify rollback was called
        assert mock_conn.rollback.called

    @patch('psycopg2.connect')
    def test_usage_summary_upsert(self, mock_connect):
        """Test that usage_summary is updated via UPSERT pattern"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"id": 100}

        result = step3_3_main(
            context_payload={
                "proceed": True,
                "chatbot": {
                    "id": "chatbot-123",
                    "organization_id": "org-456",
                    "model_name": "gemini-pro"
                },
                "user": {"id": "contact-789"}
            },
            llm_result={
                "usage_info": {
                    "tokens_input": 100,
                    "tokens_output": 50
                }
            },
            send_result={"success": True}
        )

        assert result["success"] is True

        # Verify second SQL call updates usage_summary
        update_call = mock_cursor.execute.call_args_list[1]
        assert "ON CONFLICT (organization_id)" in update_call[0][0]
        assert "DO UPDATE SET" in update_call[0][0]
        assert "current_period_messages =" in update_call[0][0]
        assert "current_period_tokens =" in update_call[0][0]

    def test_cost_calculation_for_different_providers(self):
        """Test cost calculation helper for various providers/models"""
        # OpenAI GPT-4o
        cost = _get_cost_per_1k_tokens("openai", "gpt-4o")
        assert cost == 0.005

        # OpenAI GPT-4o-mini - Now correctly matches specific model first
        # (pricing dict is ordered from most specific to least specific)
        cost = _get_cost_per_1k_tokens("openai", "gpt-4o-mini")
        assert cost == 0.0002  # Correctly matches "gpt-4o-mini" first

        # Google Gemini Flash
        cost = _get_cost_per_1k_tokens("google", "gemini-3-flash-preview")
        assert cost == 0.00025

        # Anthropic Claude Sonnet
        cost = _get_cost_per_1k_tokens("anthropic", "claude-3-sonnet")
        assert cost == 0.003

        # Unknown provider - should return fallback
        cost = _get_cost_per_1k_tokens("unknown", "unknown-model")
        assert cost == 0.001  # Fallback rate

    @patch('psycopg2.connect')
    def test_webhook_event_id_tracking(self, mock_connect):
        """Test that webhook_event_id is properly tracked"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"id": 100}

        webhook_id = 99999

        result = step3_3_main(
            context_payload={
                "proceed": True,
                "chatbot": {"id": "chatbot-123", "organization_id": "org-456"},
                "user": {"id": "contact-789"}
            },
            llm_result={"usage_info": {"tokens_input": 10, "tokens_output": 10}},
            send_result={"success": True},
            webhook_event_id=webhook_id
        )

        assert result["success"] is True

        # Verify webhook_event_id was included in INSERT
        insert_call = mock_cursor.execute.call_args_list[0]
        assert webhook_id in insert_call[0][1]

    @patch('psycopg2.connect')
    def test_cleanup_on_error(self, mock_connect):
        """Test that database connections are properly closed on error"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate error
        mock_cursor.execute.side_effect = Exception("Test error")

        result = step3_3_main(
            context_payload={
                "proceed": True,
                "chatbot": {"id": "chatbot-123", "organization_id": "org-456"},
                "user": {"id": "contact-789"}
            },
            llm_result={"usage_info": {}},
            send_result={"success": True}
        )

        assert result["success"] is False

        # Verify cleanup
        assert mock_cursor.close.called
        assert mock_conn.close.called

    @patch('psycopg2.connect')
    def test_returns_tokens_even_on_logging_failure(self, mock_connect):
        """Test that token count is still returned even if logging fails"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate logging failure
        mock_cursor.execute.side_effect = Exception("Logging failed")

        result = step3_3_main(
            context_payload={
                "proceed": True,
                "chatbot": {"id": "chatbot-123", "organization_id": "org-456"},
                "user": {"id": "contact-789"}
            },
            llm_result={
                "usage_info": {
                    "tokens_input": 100,
                    "tokens_output": 50
                }
            },
            send_result={"success": True}
        )

        assert result["success"] is False
        # Tokens still reported despite logging failure
        assert result["tokens_used"] == 150


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
