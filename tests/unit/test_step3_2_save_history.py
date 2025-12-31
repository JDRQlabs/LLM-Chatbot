"""
Unit tests for Step 3.2: Save Chat History

Tests Step 3.2's ability to:
- Save user and assistant messages to database
- Update user variables from LLM extraction
- Skip saving when previous steps failed
- Handle database errors gracefully
- Maintain conversation threading
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../f/development'))

# Mock wmill module before importing step3_2
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
    "step3_2",
    os.path.join(os.path.dirname(__file__), '../../f/development/3_2_save_chat_history.py')
)
step3_2_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step3_2_module)
step3_2_main = step3_2_module.main


class TestStep3_2SaveHistory:
    """Test Step 3.2's chat history persistence functionality"""

    @patch('psycopg2.connect')
    def test_successful_message_persistence(self, mock_connect):
        """Test successful saving of user and assistant messages"""
        # Setup mock database
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = step3_2_main(
            context_payload={
                "proceed": True,
                "user": {"id": "contact-123"}
            },
            user_message="Hello, how are you?",
            llm_result={
                "reply_text": "I'm doing great, thanks for asking!",
                "updated_variables": {}
            },
            send_result={"success": True}
        )

        # Assertions
        assert result["success"] is True
        
        # Verify two INSERT statements were executed (user + assistant)
        assert mock_cursor.execute.call_count == 2
        
        # Verify first call was user message
        first_call = mock_cursor.execute.call_args_list[0]
        assert "INSERT INTO messages" in first_call[0][0]
        assert "'user'" in first_call[0][0]
        assert first_call[0][1] == ("contact-123", "Hello, how are you?")
        
        # Verify second call was assistant message
        second_call = mock_cursor.execute.call_args_list[1]
        assert "INSERT INTO messages" in second_call[0][0]
        assert "'assistant'" in second_call[0][0]
        assert second_call[0][1] == ("contact-123", "I'm doing great, thanks for asking!")
        
        # Verify commit was called
        assert mock_conn.commit.called

    @patch('psycopg2.connect')
    def test_variable_update_persistence(self, mock_connect):
        """Test that LLM-extracted variables are persisted"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = step3_2_main(
            context_payload={
                "proceed": True,
                "user": {"id": "contact-123"}
            },
            user_message="My email is john@example.com",
            llm_result={
                "reply_text": "Got it, I've saved your email address.",
                "updated_variables": {"email": "john@example.com", "email_verified": False}
            },
            send_result={"success": True}
        )

        assert result["success"] is True
        
        # Should have 3 executes: user message, assistant message, variable update
        assert mock_cursor.execute.call_count == 3
        
        # Verify variable update call
        third_call = mock_cursor.execute.call_args_list[2]
        assert "UPDATE contacts" in third_call[0][0]
        assert "variables = variables ||" in third_call[0][0]
        # Variables are JSON dumped
        import json
        assert json.loads(third_call[0][1][0]) == {"email": "john@example.com", "email_verified": False}
        assert third_call[0][1][1] == "contact-123"

    @patch('psycopg2.connect')
    def test_skip_when_step1_failed(self, mock_connect):
        """Test that history is not saved when Step 1 failed"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = step3_2_main(
            context_payload={
                "proceed": False,  # Step 1 failed
                "reason": "Chatbot not found"
            },
            user_message="Hello",
            llm_result={"reply_text": "Hi"},
            send_result={"success": True}
        )

        # Should not save
        assert result["success"] is False
        assert "Step 1 failed" in result["error"]
        
        # Database should not be touched
        assert not mock_cursor.execute.called

    @patch('psycopg2.connect')
    def test_skip_when_step2_failed(self, mock_connect):
        """Test that history is not saved when Step 2 (LLM) failed"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = step3_2_main(
            context_payload={
                "proceed": True,
                "user": {"id": "contact-123"}
            },
            user_message="Hello",
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
        """Test that history is not saved when Step 3 (send to WhatsApp) failed"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = step3_2_main(
            context_payload={
                "proceed": True,
                "user": {"id": "contact-123"}
            },
            user_message="Hello",
            llm_result={"reply_text": "Hi there!"},
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
    def test_database_connection_error(self, mock_connect):
        """Test handling of database connection failures"""
        # Simulate connection failure
        mock_connect.side_effect = Exception("Connection refused")

        result = step3_2_main(
            context_payload={
                "proceed": True,
                "user": {"id": "contact-123"}
            },
            user_message="Hello",
            llm_result={"reply_text": "Hi"},
            send_result={"success": True}
        )

        assert result["success"] is False
        assert "Connection refused" in result["error"]

    @patch('psycopg2.connect')
    def test_database_insert_error(self, mock_connect):
        """Test handling of database insert failures"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate INSERT failure
        mock_cursor.execute.side_effect = Exception("Foreign key constraint violation")

        result = step3_2_main(
            context_payload={
                "proceed": True,
                "user": {"id": "contact-999"}  # Non-existent contact
            },
            user_message="Hello",
            llm_result={"reply_text": "Hi"},
            send_result={"success": True}
        )

        assert result["success"] is False
        assert "Foreign key constraint violation" in result["error"]

    @patch('psycopg2.connect')
    def test_empty_reply_text_handling(self, mock_connect):
        """Test handling when LLM returns no reply text"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = step3_2_main(
            context_payload={
                "proceed": True,
                "user": {"id": "contact-123"}
            },
            user_message="Hello",
            llm_result={
                "reply_text": None,  # No reply text
                "updated_variables": {}
            },
            send_result={"success": True}
        )

        assert result["success"] is True
        
        # Should only insert user message (not assistant message)
        assert mock_cursor.execute.call_count == 1
        
        # Verify only user message was inserted
        first_call = mock_cursor.execute.call_args_list[0]
        assert "'user'" in first_call[0][0]

    @patch('psycopg2.connect')
    def test_no_variable_updates(self, mock_connect):
        """Test that no UPDATE is executed when there are no variable updates"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = step3_2_main(
            context_payload={
                "proceed": True,
                "user": {"id": "contact-123"}
            },
            user_message="Hello",
            llm_result={
                "reply_text": "Hi there!",
                "updated_variables": {}  # No new variables
            },
            send_result={"success": True}
        )

        assert result["success"] is True
        
        # Should only have 2 executes (user + assistant messages, no variable update)
        assert mock_cursor.execute.call_count == 2

    @patch('psycopg2.connect')
    def test_conversation_threading(self, mock_connect):
        """Test that messages maintain conversation threading via contact_id"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        contact_id = "contact-abc-123"

        result = step3_2_main(
            context_payload={
                "proceed": True,
                "user": {"id": contact_id}
            },
            user_message="What's the weather?",
            llm_result={
                "reply_text": "It's sunny today!",
                "updated_variables": {}
            },
            send_result={"success": True}
        )

        assert result["success"] is True
        
        # Both messages should have the same contact_id
        user_call = mock_cursor.execute.call_args_list[0]
        assistant_call = mock_cursor.execute.call_args_list[1]
        
        assert user_call[0][1][0] == contact_id
        assert assistant_call[0][1][0] == contact_id

    @patch('psycopg2.connect')
    def test_cleanup_on_error(self, mock_connect):
        """Test that database connections are properly closed on error"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate error during execution
        mock_cursor.execute.side_effect = Exception("Test error")

        result = step3_2_main(
            context_payload={
                "proceed": True,
                "user": {"id": "contact-123"}
            },
            user_message="Hello",
            llm_result={"reply_text": "Hi"},
            send_result={"success": True}
        )

        assert result["success"] is False
        
        # Verify cleanup was called
        assert mock_cursor.close.called
        assert mock_conn.close.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
