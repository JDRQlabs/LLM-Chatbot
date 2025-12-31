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

    def test_openai_history_with_content(self):
        """
        GOAL: Test that OpenAI history includes only messages with content
        GIVEN: History with messages that have and don't have content
        WHEN: main is called with OpenAI
        THEN: Only messages with content are added to conversation
        """
        mock_client = Mock()
        mock_message = Mock()
        mock_message.content = "Response"
        mock_choice = Mock()
        mock_choice.message = mock_message
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = OpenAIUsage(100, 40)
        mock_client.chat = Mock()
        mock_client.chat.completions = Mock()
        mock_client.chat.completions.create = Mock(return_value=mock_response)

        with patch.object(step2_module, 'OpenAI', return_value=mock_client):
            result = step2_main(
                context_payload={
                    "proceed": True,
                    "chatbot": {
                        "id": "test",
                        "model_name": "gpt-4o",
                        "system_prompt": "Test",
                        "persona": "",
                        "temperature": 0.7,
                        "rag_config": {"enabled": False}
                    },
                    "user": {"id": "test", "phone": "123", "name": "Test", "variables": {}},
                    "history": [
                        {"role": "user", "content": "First message"},
                        {"role": "assistant", "content": ""},  # Empty content - should be skipped
                        {"role": "user", "content": "Second message"}
                    ],
                    "tools": []
                },
                user_message="Current message",
                openai_api_key="fake_key"
            )

            # Verify the call was made
            assert mock_client.chat.completions.create.called
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs['messages']

            # Should have: system + 2 history messages (skipping empty) + current user message
            assert len(messages) == 4
            assert messages[0]['role'] == 'system'
            assert messages[1]['content'] == 'First message'
            assert messages[2]['content'] == 'Second message'
            assert messages[3]['content'] == 'Current message'

    def test_missing_google_api_key(self):
        """
        GOAL: Test handling when Google API key is missing
        GIVEN: Google provider with no API key
        WHEN: main is called
        THEN: Returns error for missing API key
        """
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
                "history": [],
                "tools": []
            },
            user_message="Test",
            google_api_key="",  # Missing
            default_provider="google"
        )

        assert result["error"] == "Missing Google API Key"

    def test_google_no_usage_metadata_fallback(self):
        """
        GOAL: Test Google token estimation fallback when usage_metadata is missing
        GIVEN: Gemini response without usage_metadata
        WHEN: main processes the response
        THEN: Uses estimate_tokens fallback
        """
        mock_client = Mock()
        mock_models = Mock()
        mock_response = Mock()
        mock_response.text = "Response text"
        # No usage_metadata attribute
        del mock_response.usage_metadata

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
                    "history": [],
                    "tools": []
                },
                user_message="Test",
                google_api_key="fake_key"
            )

            # Should use estimate_tokens
            assert result["usage_info"]["tokens_input"] > 0
            assert result["usage_info"]["tokens_output"] > 0

    def test_unknown_provider_error(self):
        """
        GOAL: Test error handling for unknown provider
        GIVEN: Invalid provider name
        WHEN: main is called
        THEN: Returns error for unknown provider
        """
        result = step2_main(
            context_payload={
                "proceed": True,
                "chatbot": {
                    "id": "test",
                    "model_name": "unknown-model",
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
            default_provider="unknown_provider"
        )

        assert "error" in result
        assert "unknown_provider" in result["error"].lower()


class TestAgentLoop:
    """Test agent loop functionality for both OpenAI and Gemini"""

    def test_openai_agent_loop_with_tool_calls(self):
        """
        GOAL: Test OpenAI agent loop executes tools and returns response
        GIVEN: OpenAI client that returns tool calls then final response
        WHEN: execute_agent_loop_openai is called
        THEN: Tools are executed and final response is returned
        """
        mock_client = Mock()

        # First response: tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "search_knowledge_base"
        mock_tool_call.function.arguments = '{"query": "test query"}'

        mock_message_1 = Mock()
        mock_message_1.tool_calls = [mock_tool_call]
        mock_choice_1 = Mock()
        mock_choice_1.finish_reason = "tool_calls"
        mock_choice_1.message = mock_message_1
        mock_response_1 = Mock()
        mock_response_1.choices = [mock_choice_1]
        mock_response_1.usage = OpenAIUsage(100, 20)

        # Second response: final answer
        mock_message_2 = Mock()
        mock_message_2.content = "Based on the search results, here is the answer."
        mock_choice_2 = Mock()
        mock_choice_2.finish_reason = "stop"
        mock_choice_2.message = mock_message_2
        mock_response_2 = Mock()
        mock_response_2.choices = [mock_choice_2]
        mock_response_2.usage = OpenAIUsage(120, 30)

        mock_client.chat.completions.create = Mock(side_effect=[mock_response_1, mock_response_2])

        # Mock RAG search
        with patch.object(step2_module, 'execute_tool') as mock_execute_tool:
            mock_execute_tool.return_value = {"success": True, "results": [{"content": "info"}]}

            result = step2_module.execute_agent_loop_openai(
                client=mock_client,
                model_name="gpt-4o",
                messages=[{"role": "system", "content": "You are helpful"}],
                tools=[{
                    "type": "function",
                    "function": {
                        "name": "search_knowledge_base",
                        "description": "Search knowledge base"
                    }
                }],
                chatbot_id="chatbot-123",
                temperature=0.7,
                openai_api_key="fake_key",
                db_resource="f/development/db",
                max_iterations=5
            )

            # Assertions
            assert result["reply_text"] == "Based on the search results, here is the answer."
            assert len(result["tool_executions"]) == 1
            assert result["tool_executions"][0]["tool_name"] == "search_knowledge_base"
            assert result["tool_executions"][0]["status"] == "success"
            assert result["usage_info"]["tokens_input"] == 220  # 100 + 120
            assert result["usage_info"]["tokens_output"] == 50  # 20 + 30
            assert result["usage_info"]["iterations"] == 2

    def test_openai_agent_loop_multiple_tool_calls_in_one_response(self):
        """
        GOAL: Test OpenAI agent handles multiple tool calls in single response
        GIVEN: OpenAI response with multiple tool calls
        WHEN: execute_agent_loop_openai processes them
        THEN: All tools are executed and results fed back
        """
        mock_client = Mock()

        # Response with 2 tool calls
        mock_tool_call_1 = Mock()
        mock_tool_call_1.id = "call_1"
        mock_tool_call_1.function.name = "search_knowledge_base"
        mock_tool_call_1.function.arguments = '{"query": "query1"}'

        mock_tool_call_2 = Mock()
        mock_tool_call_2.id = "call_2"
        mock_tool_call_2.function.name = "search_knowledge_base"
        mock_tool_call_2.function.arguments = '{"query": "query2"}'

        mock_message_1 = Mock()
        mock_message_1.tool_calls = [mock_tool_call_1, mock_tool_call_2]
        mock_choice_1 = Mock()
        mock_choice_1.finish_reason = "tool_calls"
        mock_choice_1.message = mock_message_1
        mock_response_1 = Mock()
        mock_response_1.choices = [mock_choice_1]
        mock_response_1.usage = OpenAIUsage(100, 20)

        # Final response
        mock_message_2 = Mock()
        mock_message_2.content = "Combined answer from both searches"
        mock_choice_2 = Mock()
        mock_choice_2.finish_reason = "stop"
        mock_choice_2.message = mock_message_2
        mock_response_2 = Mock()
        mock_response_2.choices = [mock_choice_2]
        mock_response_2.usage = OpenAIUsage(150, 40)

        mock_client.chat.completions.create = Mock(side_effect=[mock_response_1, mock_response_2])

        with patch.object(step2_module, 'execute_tool') as mock_execute_tool:
            mock_execute_tool.return_value = {"success": True, "results": []}

            result = step2_module.execute_agent_loop_openai(
                client=mock_client,
                model_name="gpt-4o",
                messages=[{"role": "user", "content": "Test"}],
                tools=[{"type": "function", "function": {"name": "search_knowledge_base"}}],
                chatbot_id="chatbot-123",
                temperature=0.7,
                openai_api_key="fake_key",
                db_resource="f/development/db",
                max_iterations=5
            )

            # Should have executed both tools
            assert len(result["tool_executions"]) == 2
            assert mock_execute_tool.call_count == 2

    def test_openai_agent_loop_max_iterations(self):
        """
        GOAL: Test OpenAI agent loop stops at max iterations
        GIVEN: Agent that keeps requesting tools
        WHEN: Max iterations is reached
        THEN: Returns max iterations message
        """
        mock_client = Mock()

        # Always return tool calls
        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "search_knowledge_base"
        mock_tool_call.function.arguments = '{"query": "test"}'

        mock_message = Mock()
        mock_message.tool_calls = [mock_tool_call]
        mock_choice = Mock()
        mock_choice.finish_reason = "tool_calls"
        mock_choice.message = mock_message
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = OpenAIUsage(100, 20)

        mock_client.chat.completions.create = Mock(return_value=mock_response)

        with patch.object(step2_module, 'execute_tool') as mock_execute_tool:
            mock_execute_tool.return_value = {"success": True, "results": []}

            result = step2_module.execute_agent_loop_openai(
                client=mock_client,
                model_name="gpt-4o",
                messages=[{"role": "user", "content": "Test"}],
                tools=[{"type": "function", "function": {"name": "search_knowledge_base"}}],
                chatbot_id="chatbot-123",
                temperature=0.7,
                openai_api_key="fake_key",
                db_resource="f/development/db",
                max_iterations=3  # Low limit
            )

            # Should hit max iterations
            assert "need more time" in result["reply_text"].lower() or "rephrase" in result["reply_text"].lower()
            assert result["usage_info"]["max_iterations_reached"] is True
            assert result["usage_info"]["iterations"] == 3

    def test_openai_agent_loop_unexpected_finish_reason(self):
        """
        GOAL: Test handling of unexpected finish_reason
        GIVEN: OpenAI returns unexpected finish_reason
        WHEN: execute_agent_loop_openai processes it
        THEN: Returns appropriate error message
        """
        mock_client = Mock()

        mock_message = Mock()
        mock_message.content = "Partial response"
        mock_choice = Mock()
        mock_choice.finish_reason = "length"  # Unexpected
        mock_choice.message = mock_message
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = OpenAIUsage(100, 20)

        mock_client.chat.completions.create = Mock(return_value=mock_response)

        result = step2_module.execute_agent_loop_openai(
            client=mock_client,
            model_name="gpt-4o",
            messages=[{"role": "user", "content": "Test"}],
            tools=[],
            chatbot_id="chatbot-123",
            temperature=0.7,
            openai_api_key="fake_key",
            db_resource="f/development/db",
            max_iterations=5
        )

        # Should handle unexpected finish reason
        assert result["usage_info"]["finish_reason"] == "length"
        assert result["reply_text"] is not None

    def test_openai_agent_loop_exception_handling(self):
        """
        GOAL: Test OpenAI agent loop handles exceptions gracefully
        GIVEN: OpenAI client that raises exception
        WHEN: execute_agent_loop_openai is called
        THEN: Returns error message with exception info
        """
        mock_client = Mock()
        mock_client.chat.completions.create = Mock(side_effect=Exception("API Error"))

        result = step2_module.execute_agent_loop_openai(
            client=mock_client,
            model_name="gpt-4o",
            messages=[{"role": "user", "content": "Test"}],
            tools=[],
            chatbot_id="chatbot-123",
            temperature=0.7,
            openai_api_key="fake_key",
            db_resource="f/development/db",
            max_iterations=5
        )

        assert "error" in result["reply_text"].lower()
        assert result["usage_info"]["error"] == "API Error"
        assert result["usage_info"]["iterations"] == 1

    def test_openai_agent_loop_via_main(self):
        """
        GOAL: Test OpenAI agent loop is invoked via main when tools are present
        GIVEN: OpenAI chatbot with tools configured
        WHEN: main is called
        THEN: Agent loop is used and tools are available
        """
        mock_client = Mock()

        # Mock agent loop response
        mock_message = Mock()
        mock_message.content = "Response using tools"
        mock_choice = Mock()
        mock_choice.finish_reason = "stop"
        mock_choice.message = mock_message
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = OpenAIUsage(100, 30)

        mock_client.chat.completions.create = Mock(return_value=mock_response)

        with patch.object(step2_module, 'OpenAI', return_value=mock_client):
            result = step2_main(
                context_payload={
                    "proceed": True,
                    "chatbot": {
                        "id": "chatbot-123",
                        "model_name": "gpt-4o",
                        "system_prompt": "Test",
                        "persona": "",
                        "temperature": 0.7,
                        "rag_config": {"enabled": False}
                    },
                    "user": {"id": "test", "phone": "123", "name": "Test", "variables": {}},
                    "history": [],
                    "tools": [
                        {
                            "enabled": True,
                            "provider": "mcp",
                            "name": "test_tool",
                            "config": {
                                "description": "Test tool",
                                "parameters": {}
                            }
                        }
                    ]
                },
                user_message="Test",
                openai_api_key="fake_key"
            )

            assert "error" not in result
            assert result["reply_text"] == "Response using tools"

    def test_gemini_agent_loop_max_iterations(self):
        """
        GOAL: Test Gemini agent loop stops at max iterations
        GIVEN: Gemini that keeps requesting function calls
        WHEN: Max iterations is reached
        THEN: Returns max iterations message
        """
        mock_client = Mock()
        mock_models = Mock()

        # Create function call part
        mock_fc = Mock()
        mock_fc.name = "search_knowledge_base"
        mock_fc.args = {"query": "test"}

        mock_part = Mock()
        mock_part.function_call = mock_fc

        mock_candidate = Mock()
        mock_candidate.content = Mock()
        mock_candidate.content.parts = [mock_part]

        mock_response = Mock()
        mock_response.candidates = [mock_candidate]
        mock_response.usage_metadata = UsageMetadata(100, 20)

        mock_models.generate_content = Mock(return_value=mock_response)
        mock_client.models = mock_models

        with patch.object(step2_module, 'execute_tool') as mock_execute_tool:
            mock_execute_tool.return_value = {"success": True}

            result = step2_module.execute_agent_loop_gemini(
                client=mock_client,
                model_name="gemini-pro",
                system_prompt="Test",
                user_message="Test",
                chat_history=[],
                tools=[{"function": {"name": "search_knowledge_base"}}],
                chatbot_id="chatbot-123",
                temperature=0.7,
                google_api_key="fake_key",
                db_resource="f/development/db",
                fallback_message_error="Error",
                fallback_message_limit="Limit",
                max_iterations=2
            )

            # Should hit max iterations
            assert "reformular" in result["reply_text"].lower() or "información" in result["reply_text"].lower()
            assert result["usage_info"]["max_iterations_reached"] is True


class TestToolExecution:
    """Test tool execution functionality"""

    def test_execute_tool_search_knowledge_base(self):
        """
        GOAL: Test built-in search_knowledge_base tool execution
        GIVEN: Tool call to search_knowledge_base
        WHEN: execute_tool is called
        THEN: RAG search is executed
        """
        with patch.object(step2_module, 'execute_rag_search') as mock_rag_search:
            mock_rag_search.return_value = {"success": True, "results": []}

            result = step2_module.execute_tool(
                tool_name="search_knowledge_base",
                arguments={"query": "test query"},
                tools=[],  # Not in tools list - it's built-in
                chatbot_id="chatbot-123",
                openai_api_key="fake_key",
                db_resource="f/development/db"
            )

            assert result["success"] is True
            mock_rag_search.assert_called_once_with(
                chatbot_id="chatbot-123",
                query="test query",
                openai_api_key="fake_key",
                db_resource="f/development/db"
            )

    def test_execute_tool_not_found(self):
        """
        GOAL: Test error when tool is not found
        GIVEN: Invalid tool name
        WHEN: execute_tool is called
        THEN: Returns tool not found error
        """
        result = step2_module.execute_tool(
            tool_name="nonexistent_tool",
            arguments={},
            tools=[],
            chatbot_id="chatbot-123",
            openai_api_key="fake_key",
            db_resource="f/development/db"
        )

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_execute_tool_mcp(self):
        """
        GOAL: Test MCP tool execution
        GIVEN: MCP tool definition
        WHEN: execute_tool is called
        THEN: MCP tool is executed via HTTP
        """
        tools = [{
            "type": "function",
            "function": {"name": "calculate_price"},
            "_metadata": {
                "tool_type": "mcp",
                "mcp_server_url": "http://mcp-server:3001"
            }
        }]

        with patch.object(step2_module, 'execute_mcp_tool') as mock_mcp:
            mock_mcp.return_value = {"result": "calculated"}

            result = step2_module.execute_tool(
                tool_name="calculate_price",
                arguments={"amount": 100},
                tools=tools,
                chatbot_id="chatbot-123",
                openai_api_key="fake_key",
                db_resource="f/development/db"
            )

            assert result["result"] == "calculated"
            mock_mcp.assert_called_once()

    def test_execute_tool_windmill(self):
        """
        GOAL: Test Windmill tool execution
        GIVEN: Windmill tool definition
        WHEN: execute_tool is called
        THEN: Windmill script is executed
        """
        tools = [{
            "type": "function",
            "function": {"name": "process_data"},
            "_metadata": {
                "tool_type": "windmill",
                "script_path": "f/scripts/process"
            }
        }]

        with patch.object(step2_module, 'execute_windmill_tool') as mock_windmill:
            mock_windmill.return_value = {"success": True, "data": "processed"}

            result = step2_module.execute_tool(
                tool_name="process_data",
                arguments={"input": "data"},
                tools=tools,
                chatbot_id="chatbot-123",
                openai_api_key="fake_key",
                db_resource="f/development/db"
            )

            assert result["success"] is True
            mock_windmill.assert_called_once()

    def test_execute_tool_unknown_type(self):
        """
        GOAL: Test error for unknown tool type
        GIVEN: Tool with unknown type
        WHEN: execute_tool is called
        THEN: Returns unknown tool type error
        """
        tools = [{
            "type": "function",
            "function": {"name": "test_tool"},
            "_metadata": {"tool_type": "unknown"}
        }]

        result = step2_module.execute_tool(
            tool_name="test_tool",
            arguments={},
            tools=tools,
            chatbot_id="chatbot-123",
            openai_api_key="fake_key",
            db_resource="f/development/db"
        )

        assert "error" in result
        assert "unknown tool type" in result["error"].lower()

    def test_execute_tool_exception(self):
        """
        GOAL: Test exception handling in tool execution
        GIVEN: Tool that raises exception
        WHEN: execute_tool is called
        THEN: Returns error message
        """
        tools = [{
            "type": "function",
            "function": {"name": "failing_tool"},
            "_metadata": {"tool_type": "mcp", "mcp_server_url": "http://server"}
        }]

        with patch.object(step2_module, 'execute_mcp_tool') as mock_mcp:
            mock_mcp.side_effect = Exception("Tool failed")

            result = step2_module.execute_tool(
                tool_name="failing_tool",
                arguments={},
                tools=tools,
                chatbot_id="chatbot-123",
                openai_api_key="fake_key",
                db_resource="f/development/db"
            )

            assert "error" in result
            assert "Tool failed" in result["error"]


class TestRAGSearch:
    """Test RAG search execution"""

    def test_execute_rag_search_success(self):
        """
        GOAL: Test successful RAG search execution
        GIVEN: Valid search parameters
        WHEN: execute_rag_search is called
        THEN: Returns formatted search results
        """
        with patch.object(step2_module, 'retrieve_knowledge') as mock_retrieve:
            mock_retrieve.return_value = [
                {
                    "content": "Information about product",
                    "source_name": "Manual",
                    "similarity": 0.9,
                    "metadata": {"page": 10}
                }
            ]

            result = step2_module.execute_rag_search(
                chatbot_id="chatbot-123",
                query="product info",
                openai_api_key="fake_key",
                db_resource="f/development/db"
            )

            assert result["success"] is True
            assert len(result["results"]) == 1
            assert result["results"][0]["content"] == "Information about product"
            assert result["results"][0]["relevance"] == "90%"
            assert result["count"] == 1

    def test_execute_rag_search_no_results(self):
        """
        GOAL: Test RAG search with no results
        GIVEN: Search query that returns no results
        WHEN: execute_rag_search is called
        THEN: Returns empty results with message
        """
        with patch.object(step2_module, 'retrieve_knowledge') as mock_retrieve:
            mock_retrieve.return_value = []

            result = step2_module.execute_rag_search(
                chatbot_id="chatbot-123",
                query="unknown topic",
                openai_api_key="fake_key",
                db_resource="f/development/db"
            )

            assert result["success"] is True
            assert len(result["results"]) == 0
            assert "no relevant information" in result["message"].lower()

    def test_execute_rag_search_exception(self):
        """
        GOAL: Test RAG search exception handling
        GIVEN: retrieve_knowledge raises exception
        WHEN: execute_rag_search is called
        THEN: Returns error message
        """
        with patch.object(step2_module, 'retrieve_knowledge') as mock_retrieve:
            mock_retrieve.side_effect = Exception("Database error")

            result = step2_module.execute_rag_search(
                chatbot_id="chatbot-123",
                query="test",
                openai_api_key="fake_key",
                db_resource="f/development/db"
            )

            assert "error" in result
            assert "Database error" in result["error"]

    def test_retrieve_knowledge_exception_handling(self):
        """
        GOAL: Test retrieve_knowledge exception handling
        GIVEN: Database or API error during retrieval
        WHEN: retrieve_knowledge is called
        THEN: Returns empty list
        """
        with patch.object(step2_module, 'OpenAI') as mock_openai:
            mock_openai.side_effect = Exception("OpenAI error")

            result = step2_module.retrieve_knowledge(
                chatbot_id="chatbot-123",
                query="test",
                openai_api_key="fake_key",
                db_resource="f/development/db"
            )

            assert result == []


class TestMCPToolExecution:
    """Test MCP tool execution"""

    def test_execute_mcp_tool_success(self):
        """
        GOAL: Test successful MCP tool execution
        GIVEN: Valid MCP server and tool
        WHEN: execute_mcp_tool is called
        THEN: HTTP request is made and response returned
        """
        metadata = {
            "mcp_server_url": "http://mcp-server:3001",
            "integration_id": "int-123"
        }

        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"result": "success"}
            mock_post.return_value = mock_response

            result = step2_module.execute_mcp_tool(
                tool_name="calculate_price",
                metadata=metadata,
                arguments={"amount": 100},
                chatbot_id="chatbot-123"
            )

            assert result["result"] == "success"
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args.kwargs['json']['chatbot_id'] == "chatbot-123"
            assert call_args.kwargs['json']['amount'] == 100

    def test_execute_mcp_tool_no_url(self):
        """
        GOAL: Test MCP tool execution with missing URL
        GIVEN: Metadata without server URL
        WHEN: execute_mcp_tool is called
        THEN: Returns error for missing URL
        """
        metadata = {}  # No URL

        result = step2_module.execute_mcp_tool(
            tool_name="test_tool",
            metadata=metadata,
            arguments={},
            chatbot_id="chatbot-123"
        )

        assert "error" in result
        assert "not configured" in result["error"].lower()

    def test_execute_mcp_tool_timeout(self):
        """
        GOAL: Test MCP tool timeout handling
        GIVEN: MCP server that times out
        WHEN: execute_mcp_tool is called
        THEN: Returns timeout error
        """
        metadata = {"mcp_server_url": "http://mcp-server:3001"}

        with patch('requests.post') as mock_post:
            import requests
            mock_post.side_effect = requests.Timeout()

            result = step2_module.execute_mcp_tool(
                tool_name="slow_tool",
                metadata=metadata,
                arguments={},
                chatbot_id="chatbot-123"
            )

            assert "error" in result
            assert "timeout" in result["error"].lower()

    def test_execute_mcp_tool_request_exception(self):
        """
        GOAL: Test MCP tool request exception handling
        GIVEN: MCP server that returns error
        WHEN: execute_mcp_tool is called
        THEN: Returns error message
        """
        metadata = {"mcp_server_url": "http://mcp-server:3001"}

        with patch('requests.post') as mock_post:
            import requests
            mock_post.side_effect = requests.RequestException("Connection error")

            result = step2_module.execute_mcp_tool(
                tool_name="failing_tool",
                metadata=metadata,
                arguments={},
                chatbot_id="chatbot-123"
            )

            assert "error" in result
            assert "Connection error" in result["error"]


class TestWindmillToolExecution:
    """Test Windmill tool execution"""

    def test_execute_windmill_tool_success(self):
        """
        GOAL: Test successful Windmill tool execution
        GIVEN: Valid Windmill script path
        WHEN: execute_windmill_tool is called
        THEN: Script is executed and result returned
        """
        metadata = {"script_path": "f/scripts/process_data"}
        arguments = {"input": "test data"}

        mock_wmill.run_script_by_path = Mock(return_value={"processed": "data"})

        result = step2_module.execute_windmill_tool(
            metadata=metadata,
            arguments=arguments
        )

        assert result["success"] is True
        assert result["data"]["processed"] == "data"
        mock_wmill.run_script_by_path.assert_called_once_with(
            path="f/scripts/process_data",
            args=arguments,
            timeout=30
        )

    def test_execute_windmill_tool_no_script_path(self):
        """
        GOAL: Test Windmill tool with missing script path
        GIVEN: Metadata without script_path
        WHEN: execute_windmill_tool is called
        THEN: Returns error for missing path
        """
        metadata = {}  # No script_path

        result = step2_module.execute_windmill_tool(
            metadata=metadata,
            arguments={}
        )

        assert "error" in result
        assert "not configured" in result["error"].lower()

    def test_execute_windmill_tool_exception(self):
        """
        GOAL: Test Windmill tool exception handling
        GIVEN: Script that raises exception
        WHEN: execute_windmill_tool is called
        THEN: Returns error message
        """
        metadata = {"script_path": "f/scripts/failing"}

        mock_wmill.run_script_by_path = Mock(side_effect=Exception("Script failed"))

        result = step2_module.execute_windmill_tool(
            metadata=metadata,
            arguments={}
        )

        assert "error" in result
        assert "Script failed" in result["error"]


class TestToolPreparation:
    """Test tool definition preparation"""

    def test_prepare_tool_definitions_disabled_tools(self):
        """
        GOAL: Test that disabled tools are skipped
        GIVEN: Tool list with enabled and disabled tools
        WHEN: prepare_tool_definitions is called
        THEN: Only enabled tools are included
        """
        tools = [
            {
                "enabled": True,
                "provider": "mcp",
                "name": "enabled_tool",
                "config": {"description": "Enabled"}
            },
            {
                "enabled": False,
                "provider": "mcp",
                "name": "disabled_tool",
                "config": {"description": "Disabled"}
            }
        ]

        result = step2_module.prepare_tool_definitions(tools, "chatbot-123")

        assert len(result) == 1
        assert result[0]["function"]["name"] == "enabled_tool"

    def test_prepare_tool_definitions_windmill_tool(self):
        """
        GOAL: Test Windmill tool definition preparation
        GIVEN: Windmill tool configuration
        WHEN: prepare_tool_definitions is called
        THEN: Tool is formatted correctly
        """
        tools = [
            {
                "enabled": True,
                "provider": "windmill",
                "name": "windmill_script",
                "description": "Process data",
                "parameters": {"type": "object", "properties": {"input": {"type": "string"}}},
                "settings": {"script_path": "f/scripts/process"},
                "id": "tool-456"
            }
        ]

        result = step2_module.prepare_tool_definitions(tools, "chatbot-123")

        assert len(result) == 1
        assert result[0]["function"]["name"] == "windmill_script"
        assert result[0]["_metadata"]["tool_type"] == "windmill"
        assert result[0]["_metadata"]["script_path"] == "f/scripts/process"


class TestUtilityFunctions:
    """Test utility functions"""

    def test_estimate_tokens(self):
        """
        GOAL: Test token estimation function
        GIVEN: Text of various lengths
        WHEN: estimate_tokens is called
        THEN: Returns reasonable token estimate
        """
        # Short text
        short_tokens = step2_module.estimate_tokens("Hello world")
        assert short_tokens > 0
        assert short_tokens < 10

        # Long text (400 chars = ~100 tokens)
        long_text = "a" * 400
        long_tokens = step2_module.estimate_tokens(long_text)
        assert long_tokens == 100

        # Empty text should return at least 1
        empty_tokens = step2_module.estimate_tokens("")
        assert empty_tokens == 1

    def test_build_tool_instructions_with_llm_instructions(self):
        """
        GOAL: Test build_tool_instructions includes LLM instructions when present
        GIVEN: Tools with llm_instructions field
        WHEN: build_tool_instructions is called
        THEN: LLM instructions are included in output
        """
        tools = [
            {
                "name": "tool_with_instructions",
                "config": {
                    "description": "Test tool",
                    "llm_instructions": "Use this when user asks about pricing"
                }
            },
            {
                "name": "tool_without_instructions",
                "config": {
                    "description": "Another tool"
                }
            }
        ]

        result = step2_module.build_tool_instructions(tools)

        assert "tool_with_instructions" in result
        assert "Use this when user asks about pricing" in result
        assert "tool_without_instructions" in result

    def test_step1_failure_handling(self):
        """
        GOAL: Test proper error handling when Step 1 fails
        GIVEN: context_payload with proceed=False
        WHEN: main is called
        THEN: Returns error message and notify_admin flag
        """
        result = step2_main(
            context_payload={
                "proceed": False,
                "reason": "User is blocked",
                "notify_admin": True
            },
            user_message="Test"
        )

        assert "error" in result
        assert result["error"] == "User is blocked"
        assert result["should_notify_admin"] is True
        assert "unable to process" in result["reply_text"].lower()

    def test_retrieve_knowledge_no_api_key(self):
        """
        GOAL: Test retrieve_knowledge returns empty when no API key
        GIVEN: Empty API key
        WHEN: retrieve_knowledge is called
        THEN: Returns empty list without calling OpenAI
        """
        result = step2_module.retrieve_knowledge(
            chatbot_id="chatbot-123",
            query="test",
            openai_api_key="",  # No API key
            db_resource="f/development/db"
        )

        assert result == []

    def test_openai_agent_loop_json_decode_error(self):
        """
        GOAL: Test handling of malformed JSON in tool call arguments
        GIVEN: Tool call with invalid JSON arguments
        WHEN: execute_agent_loop_openai processes it
        THEN: Handles JSON decode error gracefully
        """
        mock_client = Mock()

        # First response: tool call with malformed JSON
        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "search_knowledge_base"
        mock_tool_call.function.arguments = '{invalid json}'  # Malformed

        mock_message_1 = Mock()
        mock_message_1.tool_calls = [mock_tool_call]
        mock_choice_1 = Mock()
        mock_choice_1.finish_reason = "tool_calls"
        mock_choice_1.message = mock_message_1
        mock_response_1 = Mock()
        mock_response_1.choices = [mock_choice_1]
        mock_response_1.usage = OpenAIUsage(100, 20)

        # Second response: final answer
        mock_message_2 = Mock()
        mock_message_2.content = "Here is the answer"
        mock_choice_2 = Mock()
        mock_choice_2.finish_reason = "stop"
        mock_choice_2.message = mock_message_2
        mock_response_2 = Mock()
        mock_response_2.choices = [mock_choice_2]
        mock_response_2.usage = OpenAIUsage(120, 30)

        mock_client.chat.completions.create = Mock(side_effect=[mock_response_1, mock_response_2])

        with patch.object(step2_module, 'execute_tool') as mock_execute_tool:
            mock_execute_tool.return_value = {"success": True}

            result = step2_module.execute_agent_loop_openai(
                client=mock_client,
                model_name="gpt-4o",
                messages=[{"role": "user", "content": "Test"}],
                tools=[{"type": "function", "function": {"name": "search_knowledge_base"}}],
                chatbot_id="chatbot-123",
                temperature=0.7,
                openai_api_key="fake_key",
                db_resource="f/development/db",
                max_iterations=5
            )

            # Should have handled the error and continued
            assert result["reply_text"] == "Here is the answer"
            # Tool should have been called with empty args
            mock_execute_tool.assert_called_once()
            call_args = mock_execute_tool.call_args
            assert call_args.kwargs['arguments'] == {}

    def test_gemini_agent_loop_with_tool_calls(self):
        """
        GOAL: Test Gemini agent loop executes tools and returns final response
        GIVEN: Gemini client that returns function calls then final response
        WHEN: execute_agent_loop_gemini is called
        THEN: Tools are executed and final response is returned
        """
        mock_client = Mock()
        mock_models = Mock()

        # First response: function call
        mock_fc = Mock()
        mock_fc.name = "search_knowledge_base"
        mock_fc.args = {"query": "test query"}

        mock_part_1 = Mock()
        mock_part_1.function_call = mock_fc

        mock_candidate_1 = Mock()
        mock_candidate_1.content = Mock()
        mock_candidate_1.content.parts = [mock_part_1]

        mock_response_1 = Mock()
        mock_response_1.candidates = [mock_candidate_1]
        mock_response_1.usage_metadata = UsageMetadata(100, 20)

        # Second response: final answer (no function calls)
        mock_part_2 = Mock()
        # Part without function_call attribute
        if hasattr(mock_part_2, 'function_call'):
            delattr(mock_part_2, 'function_call')

        mock_candidate_2 = Mock()
        mock_candidate_2.content = Mock()
        mock_candidate_2.content.parts = [mock_part_2]

        mock_response_2 = Mock()
        mock_response_2.candidates = [mock_candidate_2]
        mock_response_2.text = "Based on the search, here is the answer"
        mock_response_2.usage_metadata = UsageMetadata(120, 30)

        mock_models.generate_content = Mock(side_effect=[mock_response_1, mock_response_2])
        mock_client.models = mock_models

        with patch.object(step2_module, 'execute_tool') as mock_execute_tool:
            mock_execute_tool.return_value = {"success": True, "results": []}

            result = step2_module.execute_agent_loop_gemini(
                client=mock_client,
                model_name="gemini-pro",
                system_prompt="You are helpful",
                user_message="Test question",
                chat_history=[],
                tools=[{"function": {"name": "search_knowledge_base"}}],
                chatbot_id="chatbot-123",
                temperature=0.7,
                google_api_key="fake_key",
                db_resource="f/development/db",
                fallback_message_error="Error",
                fallback_message_limit="Limit",
                max_iterations=5
            )

            # Should have executed tool and returned final answer
            assert result["reply_text"] == "Based on the search, here is the answer"
            assert len(result["tool_executions"]) == 1
            assert result["usage_info"]["tokens_input"] == 220  # 100 + 120
            assert result["usage_info"]["tokens_output"] == 50  # 20 + 30
            assert result["usage_info"]["iterations"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
