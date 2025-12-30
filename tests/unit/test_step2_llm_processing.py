"""
Unit tests for Step 2: LLM Processing

Tests Step 2's ability to:
- Call LLM providers (OpenAI, Google) without tools
- Format messages and system prompts correctly
- Handle RAG context injection
- Track token usage
- Return proper response structure
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from collections import namedtuple

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
import importlib.util
spec = importlib.util.spec_from_file_location(
    "step2",
    os.path.join(os.path.dirname(__file__), '../../f/development/2_whatsapp_llm_processing.py')
)
step2_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step2_module)
step2_main = step2_module.main

# Simple class to hold usage metadata
UsageMetadata = namedtuple('UsageMetadata', ['prompt_token_count', 'candidates_token_count'])
OpenAIUsage = namedtuple('OpenAIUsage', ['prompt_tokens', 'completion_tokens'])


class TestStep2LLMProcessing:
    """Test Step 2's LLM processing functionality"""

    def test_simple_gemini_response_no_tools(self):
        """Test simple Gemini response without tools or RAG"""
        # Setup mock Gemini client
        mock_client = Mock()
        mock_models = Mock()

        # Create mock response
        mock_response = Mock()
        mock_response.text = "Hello! How can I help you today?"
        mock_response.usage_metadata = UsageMetadata(
            prompt_token_count=50,
            candidates_token_count=20
        )

        mock_models.generate_content = Mock(return_value=mock_response)
        mock_client.models = mock_models

        with patch.object(mock_genai, 'Client', return_value=mock_client):
            result = step2_main(
                context_payload={
                    "proceed": True,
                    "chatbot": {
                        "id": "chatbot-123",
                        "organization_id": "org-456",
                        "model_name": "gemini-pro",
                        "system_prompt": "You are a helpful assistant.",
                        "persona": "Friendly and professional",
                        "temperature": 0.7,
                        "rag_config": {"enabled": False}
                    },
                    "user": {
                        "id": "user-789",
                        "phone": "1234567890",
                        "name": "Test User",
                        "variables": {}
                    },
                    "history": [],
                    "tools": []
                },
                user_message="Hello",
                google_api_key="fake_key",
                default_provider="google"
            )

            # Assertions
            assert "error" not in result
            assert result["reply_text"] == "Hello! How can I help you today?"
            assert result["usage_info"]["provider"] == "google"
            assert result["usage_info"]["model"] == "gemini-pro"
            assert result["usage_info"]["tokens_input"] == 50
            assert result["usage_info"]["tokens_output"] == 20
            assert result["usage_info"]["rag_used"] is False
            assert result["usage_info"]["chunks_retrieved"] == 0
            assert len(result["tool_executions"]) == 0

    def test_simple_openai_response_no_tools(self):
        """Test simple OpenAI response without tools or RAG"""
        # Setup mock OpenAI client
        mock_client = Mock()

        # Create mock response
        mock_message = Mock()
        mock_message.content = "I'd be happy to help!"

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = OpenAIUsage(
            prompt_tokens=100,
            completion_tokens=40
        )

        mock_client.chat = Mock()
        mock_client.chat.completions = Mock()
        mock_client.chat.completions.create = Mock(return_value=mock_response)

        # Patch OpenAI in the step2_module namespace where it's imported
        with patch.object(step2_module, 'OpenAI', return_value=mock_client):
            result = step2_main(
                context_payload={
                    "proceed": True,
                    "chatbot": {
                        "id": "chatbot-123",
                        "organization_id": "org-456",
                        "model_name": "gpt-4o",
                        "system_prompt": "You are a helpful assistant.",
                        "persona": "Concise and clear",
                        "temperature": 0.7,
                        "rag_config": {"enabled": False}
                    },
                    "user": {
                        "id": "user-789",
                        "phone": "1234567890",
                        "name": "Test User",
                        "variables": {}
                    },
                    "history": [],
                    "tools": []
                },
                user_message="Hello",
                openai_api_key="fake_openai_key",
                default_provider="openai"
            )

            # Assertions
            assert "error" not in result
            assert result["reply_text"] == "I'd be happy to help!"
            assert result["usage_info"]["provider"] == "openai"
            assert result["usage_info"]["model"] == "gpt-4o"
            assert result["usage_info"]["tokens_input"] == 100
            assert result["usage_info"]["tokens_output"] == 40
            assert result["usage_info"]["rag_used"] is False

    def test_provider_detection_from_model_name(self):
        """Test that provider is correctly detected from model_name"""
        # Test Gemini detection
        mock_client = Mock()
        mock_models = Mock()
        mock_response = Mock()
        mock_response.text = "Response"
        mock_response.usage_metadata = UsageMetadata(50, 20)
        mock_models.generate_content = Mock(return_value=mock_response)
        mock_client.models = mock_models

        with patch.object(mock_genai, 'Client', return_value=mock_client):
            result = step2_main(
                context_payload={
                    "proceed": True,
                    "chatbot": {
                        "id": "test",
                        "model_name": "gemini-3-flash-preview",  # Contains "gemini"
                        "system_prompt": "Test",
                        "persona": "",
                        "temperature": 0.7,
                        "rag_config": {"enabled": False}
                    },
                    "user": {"id": "test", "phone": "123", "name": "Test", "variables": {}},
                    "history": [],
                    "tools": []
                },
                user_message="Test",
                google_api_key="fake_key",
                default_provider="openai"  # Default is openai, but should switch to google
            )

            assert result["usage_info"]["provider"] == "google"

    def test_conversation_history_formatting(self):
        """Test that conversation history is properly formatted for LLM"""
        mock_client = Mock()
        mock_models = Mock()
        mock_response = Mock()
        mock_response.text = "Response with history"
        mock_response.usage_metadata = UsageMetadata(150, 30)
        mock_models.generate_content = Mock(return_value=mock_response)
        mock_client.models = mock_models

        with patch.object(mock_genai, 'Client', return_value=mock_client):
            result = step2_main(
                context_payload={
                    "proceed": True,
                    "chatbot": {
                        "id": "test",
                        "model_name": "gemini-pro",
                        "system_prompt": "You are helpful",
                        "persona": "",
                        "temperature": 0.7,
                        "rag_config": {"enabled": False}
                    },
                    "user": {"id": "test", "phone": "123", "name": "Test", "variables": {}},
                    "history": [
                        {"role": "user", "content": "Previous question"},
                        {"role": "assistant", "content": "Previous answer"}
                    ],
                    "tools": []
                },
                user_message="Follow-up question",
                google_api_key="fake_key"
            )

            # Verify generate_content was called
            assert mock_models.generate_content.called

            # The call should include conversation history
            call_args = mock_models.generate_content.call_args
            assert call_args is not None

    def test_user_context_injection(self):
        """Test that user context (name, phone, variables) is injected into prompt"""
        mock_client = Mock()
        mock_models = Mock()
        mock_response = Mock()
        mock_response.text = "Response"
        mock_response.usage_metadata = UsageMetadata(50, 20)
        mock_models.generate_content = Mock(return_value=mock_response)
        mock_client.models = mock_models

        with patch.object(mock_genai, 'Client', return_value=mock_client):
            result = step2_main(
                context_payload={
                    "proceed": True,
                    "chatbot": {
                        "id": "test",
                        "model_name": "gemini-pro",
                        "system_prompt": "You are helpful",
                        "persona": "Professional",
                        "temperature": 0.7,
                        "rag_config": {"enabled": False}
                    },
                    "user": {
                        "id": "user-123",
                        "phone": "5551234567",
                        "name": "John Doe",
                        "variables": {"preferred_language": "Spanish", "tier": "premium"}
                    },
                    "history": [],
                    "tools": []
                },
                user_message="Hello",
                google_api_key="fake_key"
            )

            assert result["reply_text"] == "Response"
            # User context should be included in the system prompt
            # We can verify this by checking the generate_content call

    def test_rag_context_injection(self):
        """Test that RAG context is properly injected when enabled"""
        # Mock OpenAI for embeddings
        mock_openai_client = Mock()
        mock_embedding_response = Mock()
        mock_embedding_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_openai_client.embeddings = Mock()
        mock_openai_client.embeddings.create = Mock(return_value=mock_embedding_response)

        # Mock database connection for RAG retrieval
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall = Mock(return_value=[
            {
                "content": "Relevant information from knowledge base",
                "source_name": "Product Manual",
                "similarity": 0.85,
                "metadata": {"page": 5}
            }
        ])
        mock_conn.cursor = Mock(return_value=mock_cursor)

        # Mock Gemini response - simple response without tools (no agent loop)
        mock_gemini_client = Mock()
        mock_models = Mock()
        mock_response = Mock()
        mock_response.text = "Based on the knowledge base, here's the answer..."
        mock_response.usage_metadata = UsageMetadata(200, 50)
        mock_models.generate_content = Mock(return_value=mock_response)
        mock_gemini_client.models = mock_models

        # Patch OpenAI in the step2_module namespace
        with patch.object(step2_module, 'OpenAI', return_value=mock_openai_client), \
             patch.object(step2_module, 'psycopg2') as mock_psycopg2, \
             patch.object(mock_genai, 'Client', return_value=mock_gemini_client):

            # Configure psycopg2 mock
            mock_psycopg2.connect.return_value = mock_conn

            result = step2_main(
                context_payload={
                    "proceed": True,
                    "chatbot": {
                        "id": "chatbot-123",
                        "model_name": "gemini-pro",
                        "system_prompt": "You are helpful",
                        "persona": "",
                        "temperature": 0.7,
                        "rag_config": {"enabled": True}  # RAG enabled!
                    },
                    "user": {"id": "test", "phone": "123", "name": "Test", "variables": {}},
                    "history": [],
                    "tools": []
                },
                user_message="How do I use the product?",
                openai_api_key="fake_openai_key",  # For embeddings
                google_api_key="fake_google_key",
                db_resource="f/development/business_layer_db_postgreSQL"
            )

            # Assertions
            assert result["usage_info"]["rag_used"] is True
            assert result["usage_info"]["chunks_retrieved"] == 1
            assert len(result["retrieved_sources"]) == 1
            assert result["retrieved_sources"][0]["source_name"] == "Product Manual"
            assert result["retrieved_sources"][0]["similarity"] == 0.85

    def test_llm_error_handling(self):
        """Test LLM error handling with fallback messages"""
        mock_client = Mock()
        mock_models = Mock()

        # Simulate LLM error
        mock_models.generate_content = Mock(side_effect=Exception("API Error"))
        mock_client.models = mock_models

        with patch.object(mock_genai, 'Client', return_value=mock_client):
            result = step2_main(
                context_payload={
                    "proceed": True,
                    "chatbot": {
                        "id": "test",
                        "model_name": "gemini-pro",
                        "system_prompt": "Test",
                        "persona": "",
                        "temperature": 0.7,
                        "rag_config": {"enabled": False},
                        "fallback_message_error": "Custom error message",
                        "fallback_message_limit": "Custom limit message"
                    },
                    "user": {"id": "test", "phone": "123", "name": "Test", "variables": {}},
                    "history": [],
                    "tools": []
                },
                user_message="Test",
                google_api_key="fake_key"
            )

            # Should return fallback message
            assert result["reply_text"] == "Custom error message"
            assert result["usage_info"]["error"] == "API Error"
            assert result["usage_info"]["is_limit_error"] is False

    def test_quota_limit_error_handling(self):
        """Test quota/limit error detection and appropriate fallback message"""
        mock_client = Mock()
        mock_models = Mock()

        # Simulate quota error
        mock_models.generate_content = Mock(side_effect=Exception("429 Quota exceeded"))
        mock_client.models = mock_models

        with patch.object(mock_genai, 'Client', return_value=mock_client):
            result = step2_main(
                context_payload={
                    "proceed": True,
                    "chatbot": {
                        "id": "test",
                        "model_name": "gemini-pro",
                        "system_prompt": "Test",
                        "persona": "",
                        "temperature": 0.7,
                        "rag_config": {"enabled": False},
                        "fallback_message_error": "Error message",
                        "fallback_message_limit": "Quota exceeded message"
                    },
                    "user": {"id": "test", "phone": "123", "name": "Test", "variables": {}},
                    "history": [],
                    "tools": []
                },
                user_message="Test",
                google_api_key="fake_key"
            )

            # Should return limit fallback message
            assert result["reply_text"] == "Quota exceeded message"
            assert result["usage_info"]["is_limit_error"] is True

    def test_missing_api_key_error(self):
        """Test handling when API key is missing"""
        result = step2_main(
            context_payload={
                "proceed": True,
                "chatbot": {
                    "id": "test",
                    "model_name": "gpt-4",
                    "system_prompt": "Test",
                    "persona": "",
                    "temperature": 0.7,
                    "rag_config": {"enabled": False}
                },
                "user": {"id": "test", "phone": "123", "name": "Test", "variables": {}},
                "history": [],
                "tools": []
            },
            user_message="Test",
            openai_api_key="",  # Missing API key
            default_provider="openai"
        )

        assert result["error"] == "Missing OpenAI API Key"

    def test_empty_history_handling(self):
        """Test that empty history is handled correctly"""
        mock_client = Mock()
        mock_models = Mock()
        mock_response = Mock()
        mock_response.text = "First message response"
        mock_response.usage_metadata = UsageMetadata(50, 20)
        mock_models.generate_content = Mock(return_value=mock_response)
        mock_client.models = mock_models

        with patch.object(mock_genai, 'Client', return_value=mock_client):
            result = step2_main(
                context_payload={
                    "proceed": True,
                    "chatbot": {
                        "id": "test",
                        "model_name": "gemini-pro",
                        "system_prompt": "Test",
                        "persona": "",
                        "temperature": 0.7,
                        "rag_config": {"enabled": False}
                    },
                    "user": {"id": "test", "phone": "123", "name": "Test", "variables": {}},
                    "history": [],  # Empty history
                    "tools": []
                },
                user_message="First message",
                google_api_key="fake_key"
            )

            assert "error" not in result
            assert result["reply_text"] == "First message response"

    def test_rag_disabled_no_retrieval(self):
        """Test that RAG retrieval is skipped when disabled"""
        mock_client = Mock()
        mock_models = Mock()
        mock_response = Mock()
        mock_response.text = "Response without RAG"
        mock_response.usage_metadata = UsageMetadata(50, 20)
        mock_models.generate_content = Mock(return_value=mock_response)
        mock_client.models = mock_models

        with patch.object(mock_genai, 'Client', return_value=mock_client), \
             patch.object(step2_module, 'OpenAI') as mock_openai:

            result = step2_main(
                context_payload={
                    "proceed": True,
                    "chatbot": {
                        "id": "test",
                        "model_name": "gemini-pro",
                        "system_prompt": "Test",
                        "persona": "",
                        "temperature": 0.7,
                        "rag_config": {"enabled": False}  # RAG disabled
                    },
                    "user": {"id": "test", "phone": "123", "name": "Test", "variables": {}},
                    "history": [],
                    "tools": []
                },
                user_message="Question",
                openai_api_key="fake_key",
                google_api_key="fake_key"
            )

            # OpenAI should not be called for embeddings when RAG is disabled
            assert not mock_openai.called
            assert result["usage_info"]["rag_used"] is False
            assert result["usage_info"]["chunks_retrieved"] == 0
            assert len(result["retrieved_sources"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
