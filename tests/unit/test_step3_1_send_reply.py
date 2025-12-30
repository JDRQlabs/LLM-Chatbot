"""
Unit tests for Step 3a: Send reply to WhatsApp

Tests Step 3a's ability to:
- Send messages via WhatsApp Business API
- Handle missing text gracefully
- Format phone numbers correctly
- Handle API errors
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../f/development'))

# Import the module under test
import importlib.util
spec = importlib.util.spec_from_file_location(
    "step3a",
    os.path.join(os.path.dirname(__file__), '../../f/development/3_1_send_reply_to_whatsapp.py')
)
step3a_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step3a_module)
step3a_main = step3a_module.main


class TestStep3aSendReply:
    """Test Step 3a's WhatsApp reply functionality"""

    @patch('requests.post')
    def test_successful_message_send(self, mock_post):
        """Test successful message sending"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messaging_product": "whatsapp",
            "contacts": [{"input": "16315551181", "wa_id": "16315551181"}],
            "messages": [{"id": "wamid.ABC123"}]
        }
        mock_post.return_value = mock_response

        # Call function
        result = step3a_main(
            phone_number_id="123456123",
            context_payload={
                "chatbot": {"wa_token": "test_token"},
                "user": {"phone": "16315551181"}
            },
            llm_result={"reply_text": "Hello! How can I help you?"}
        )

        # Assertions
        assert result["success"] is True
        assert "meta_response" in result

        # Verify API was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "https://graph.facebook.com/v22.0/123456123/messages" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test_token"
        assert call_args[1]["json"]["text"]["body"] == "Hello! How can I help you?"

    def test_no_text_to_send(self):
        """Test handling when LLM result has no reply_text"""
        result = step3a_main(
            phone_number_id="123456123",
            context_payload={
                "chatbot": {"wa_token": "test_token"},
                "user": {"phone": "16315551181"}
            },
            llm_result={}  # No reply_text
        )

        # Assertions
        assert result["success"] is False

    @patch('requests.post')
    def test_api_error_handling(self, mock_post):
        """Test handling of WhatsApp API errors"""
        import requests

        # Mock failed API response
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = '{"error": {"message": "Invalid phone number"}}'
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("API Error")
        mock_post.return_value = mock_response

        result = step3a_main(
            phone_number_id="123456123",
            context_payload={
                "chatbot": {"wa_token": "test_token"},
                "user": {"phone": "invalid"}
            },
            llm_result={"reply_text": "Test message"}
        )

        # Assertions
        assert result["success"] is False
        assert "error" in result

    @patch('requests.post')
    def test_phone_number_formatting(self, mock_post):
        """Test that phone numbers are formatted correctly"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response

        # Test with + prefix (should be removed)
        result = step3a_main(
            phone_number_id="123456123",
            context_payload={
                "chatbot": {"wa_token": "test_token"},
                "user": {"phone": "+16315551181"}  # Has + prefix
            },
            llm_result={"reply_text": "Test"}
        )

        # Verify phone was formatted correctly
        call_args = mock_post.call_args
        assert call_args[1]["json"]["to"] == "16315551181"  # No + prefix


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
