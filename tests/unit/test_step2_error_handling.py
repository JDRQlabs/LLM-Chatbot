"""
Unit tests for Step 2: Error handling and edge cases

Tests Step 2's ability to handle error responses from Step 1.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../f/development'))

# Mock required modules before importing step2
mock_wmill = Mock()
mock_wmill.get_variable.return_value = "fake_google_api_key"
sys.modules['wmill'] = mock_wmill

# Mock Google GenAI SDK
mock_genai = Mock()
mock_genai_types = Mock()
sys.modules['google.genai'] = mock_genai
sys.modules['google.genai.types'] = mock_genai_types

# Import the module under test
# Note: Can't import directly because filename starts with number
# Import using importlib instead
import importlib.util
spec = importlib.util.spec_from_file_location(
    "step2",
    os.path.join(os.path.dirname(__file__), '../../f/development/2_whatsapp_llm_processing.py')
)
step2_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step2_module)
step2_main = step2_module.main


class TestStep2ErrorHandling:
    """Test Step 2's error handling"""

    def test_step1_failed_chatbot_not_found(self):
        """Test Step 2 handles 'Chatbot not found' error from Step 1"""
        # Simulate Step 1 error response
        context_payload = {
            "proceed": False,
            "reason": "Chatbot not found",
            "notify_admin": True
        }

        result = step2_main(
            context_payload=context_payload,
            user_message="Hello",
            openai_api_key="",
            google_api_key="fake_key",
            default_provider="google"
        )

        # Assertions
        assert "error" in result
        assert result["error"] == "Chatbot not found"
        assert "reply_text" in result
        assert "unable to process" in result["reply_text"].lower()
        assert result["should_notify_admin"] is True

    def test_step1_failed_quota_exceeded(self):
        """Test Step 2 handles quota exceeded error"""
        context_payload = {
            "proceed": False,
            "reason": "Usage quota exceeded",
            "notify_admin": False
        }

        result = step2_main(
            context_payload=context_payload,
            user_message="Hello",
            google_api_key="fake_key"
        )

        assert result["error"] == "Usage quota exceeded"
        assert result["should_notify_admin"] is False

    def test_step1_failed_duplicate_message(self):
        """Test Step 2 handles duplicate message error"""
        context_payload = {
            "proceed": False,
            "reason": "Duplicate - Already Processed"
        }

        result = step2_main(
            context_payload=context_payload,
            user_message="Hello",
            google_api_key="fake_key"
        )

        assert result["error"] == "Duplicate - Already Processed"
        assert "reply_text" in result

    def test_step1_success_no_proceed_key(self):
        """Test handling when proceed key is missing (defaults to False)"""
        context_payload = {
            # Missing "proceed" key
            "chatbot": {"id": "123"},
            "user": {},
            "history": [],
            "tools": []
        }

        result = step2_main(
            context_payload=context_payload,
            user_message="Hello",
            google_api_key="fake_key"
        )

        # Should treat as failure since proceed defaults to False
        assert "error" in result

    def test_step1_proceed_false_explicit(self):
        """Test explicit proceed=False is handled"""
        context_payload = {
            "proceed": False,  # Explicit False
            "reason": "Chatbot is disabled"
        }

        result = step2_main(
            context_payload=context_payload,
            user_message="Hello",
            google_api_key="fake_key"
        )

        assert result["error"] == "Chatbot is disabled"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
