"""
Unit tests for Step 2: Gemini tool calling

Tests Step 2's ability to:
- Call Gemini with tools
- Parse tool call arguments from protobuf
- Execute MCP tools
- Return responses
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from google.protobuf.struct_pb2 import Struct
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


class TestGeminiToolCalling:
    """Test Gemini's tool calling functionality"""

    def test_gemini_tool_call_with_pricing_calculator(self):
        """Test that Gemini can call the pricing calculator tool"""

        # Create mock for function call arguments (protobuf Struct)
        mock_args = Struct()
        mock_args.update({
            "message_volume": 3000,
            "tier": "basic"
        })

        # Create mock function call
        mock_function_call = Mock()
        mock_function_call.name = "calculate_pricing"
        mock_function_call.args = mock_args

        # Create mock part with function call
        mock_part = Mock()
        mock_part.function_call = mock_function_call

        # Mock first response: model wants to call tool
        mock_response_1 = Mock()
        mock_candidate_1 = Mock()
        mock_candidate_1.content = Mock()
        mock_candidate_1.content.parts = [mock_part]
        mock_response_1.candidates = [mock_candidate_1]
        # Create usage metadata with real integers
        mock_response_1.usage_metadata = UsageMetadata(
            prompt_token_count=100,
            candidates_token_count=50
        )

        # Mock second response: final answer after tool execution
        mock_text_part = Mock(spec=['text'])
        mock_text_part.text = "Para 3,000 mensajes al mes con el plan Básico, el costo sería $899 MXN/mes."
        # Make sure hasattr(part, 'function_call') returns False
        delattr(mock_text_part, 'function_call') if hasattr(mock_text_part, 'function_call') else None

        mock_candidate_2 = Mock()
        mock_candidate_2.content = Mock()
        mock_candidate_2.content.parts = [mock_text_part]

        mock_response_2 = Mock()
        mock_response_2.text = "Para 3,000 mensajes al mes con el plan Básico, el costo sería $899 MXN/mes."
        mock_response_2.candidates = [mock_candidate_2]
        # Create usage metadata with real integers
        mock_response_2.usage_metadata = UsageMetadata(
            prompt_token_count=150,
            candidates_token_count=80
        )

        # Setup mock GenAI Client
        mock_client = Mock()
        mock_models = Mock()
        mock_models.generate_content = Mock(side_effect=[mock_response_1, mock_response_2])
        mock_client.models = mock_models

        # Patch genai.Client to return our mock client
        with patch.object(mock_genai, 'Client', return_value=mock_client), \
             patch('requests.post') as mock_post:
            mock_mcp_response = Mock()
            mock_mcp_response.ok = True
            mock_mcp_response.json.return_value = {
                "plan": "Básico",
                "precio_base": "$299.00 MXN/mes",
                "mensajes_incluidos": "1,000",
                "mensajes_solicitados": "3,000",
                "mensajes_extra": "2,000",
                "costo_extra": "$600.00 MXN",
                "costo_total": "$899.00 MXN/mes"
            }
            mock_post.return_value = mock_mcp_response

            # Call function with Gemini + tools (matching database format from Step 1)
            result = step2_main(
                context_payload={
                    "proceed": True,
                    "chatbot": {
                        "id": "test-chatbot-id",
                        "organization_id": "test-org-id",
                        "model_name": "gemini-3-flash-preview",
                        "system_prompt": "Eres un representante de ventas para JD Labs.",
                        "persona": "Hablas en español, eres conciso.",
                        "temperature": 0.7,
                        "rag_enabled": False
                    },
                    "user": {"id": "test-user-id"},
                    "history": [],
                    "tools": [{
                        "integration_id": "test-integration-id",
                        "provider": "mcp",  # Changed from mcp_tool to mcp to match prepare_tool_definitions
                        "name": "calculate_pricing",
                        "config": {
                            "type": "mcp_server",
                            "server_url": "http://mcp_pricing_calculator:3001",
                            "description": "Calcula precios del chatbot de WhatsApp según volumen de mensajes",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "message_volume": {"type": "number", "description": "Número de mensajes al mes"},
                                    "tier": {"type": "string", "description": "Tier del plan (basic, professional, enterprise)"}
                                },
                                "required": ["message_volume"]
                            }
                        },
                        "credentials": None
                    }]
                },
                user_message="Que tal, cuánto me costarian 3000 mensajes al mes?",
                google_api_key="fake_key",
                default_provider="google"
            )

            # Assertions
            assert "error" not in result, f"Expected no error, got: {result.get('error')}"
            assert result["reply_text"] == "Para 3,000 mensajes al mes con el plan Básico, el costo sería $899 MXN/mes."
            assert len(result["tool_executions"]) == 1
            assert result["tool_executions"][0]["tool_name"] == "calculate_pricing"
            assert result["tool_executions"][0]["arguments"]["message_volume"] == 3000
            assert result["usage_info"]["provider"] == "google"
            assert result["usage_info"]["tool_calls"] == 1

    def test_protobuf_struct_conversion(self):
        """Test that we can properly convert protobuf Struct to dict"""
        from google.protobuf.struct_pb2 import Struct
        from google.protobuf.json_format import MessageToDict

        # Create a protobuf Struct with various types
        mock_args = Struct()
        mock_args.update({
            "message_volume": 3000,
            "tier": "basic",
            "enabled": True,
            "tags": ["sales", "premium"]
        })

        # Convert to dict
        result = MessageToDict(mock_args)

        # Verify conversion
        assert result["message_volume"] == 3000
        assert result["tier"] == "basic"
        assert result["enabled"] is True
        assert result["tags"] == ["sales", "premium"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
