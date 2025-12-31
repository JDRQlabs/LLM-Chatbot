"""
Live LLM Integration Tests

These tests make REAL API calls to OpenAI and Gemini.
They verify that:
1. Response parsing works with actual API responses
2. Token counting is accurate
3. Error handling works for real error scenarios

Run with: pytest tests/live/ -m live_llm
Cost: ~$0.01-0.05 per full run

IMPORTANT: Set OPENAI_API_KEY and/or GOOGLE_API_KEY environment variables.
"""

import pytest
import os
from pathlib import Path
import sys

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.mark.live
@pytest.mark.live_llm
class TestLiveOpenAI:
    """Live tests for OpenAI API integration."""

    def test_openai_simple_completion(self, openai_api_key, live_test_warning):
        """
        GOAL: Verify OpenAI API response parsing works correctly

        GIVEN: Valid OpenAI API key
        WHEN: Sending a simple completion request
        THEN:
        - Response contains expected fields
        - Token counts are non-zero
        - Content is parseable
        """
        from openai import OpenAI

        client = OpenAI(api_key=openai_api_key)

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Cheapest model
            messages=[
                {"role": "user", "content": "Say 'test' and nothing else."}
            ],
            max_tokens=10
        )

        # Verify response structure
        assert response.choices is not None
        assert len(response.choices) > 0
        assert response.choices[0].message.content is not None

        # Verify token counts
        assert response.usage.prompt_tokens > 0
        assert response.usage.completion_tokens > 0
        assert response.usage.total_tokens == (
            response.usage.prompt_tokens + response.usage.completion_tokens
        )

        print(f"\nOpenAI Response: {response.choices[0].message.content}")
        print(f"Tokens: prompt={response.usage.prompt_tokens}, "
              f"completion={response.usage.completion_tokens}")

    def test_openai_tool_calling(self, openai_api_key, live_test_warning):
        """
        GOAL: Verify OpenAI tool calling works correctly

        GIVEN: Valid OpenAI API key and tool definition
        WHEN: Sending a request that should trigger tool use
        THEN:
        - Response contains tool call
        - Tool call has correct structure
        - Arguments are parseable JSON
        """
        from openai import OpenAI
        import json

        client = OpenAI(api_key=openai_api_key)

        tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    },
                    "required": ["location"]
                }
            }
        }]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "What's the weather in Tokyo?"}
            ],
            tools=tools,
            tool_choice="auto",
            max_tokens=100
        )

        # Verify tool call
        message = response.choices[0].message
        assert message.tool_calls is not None, "Expected tool call but got none"
        assert len(message.tool_calls) > 0

        tool_call = message.tool_calls[0]
        assert tool_call.function.name == "get_weather"

        # Verify arguments are valid JSON
        args = json.loads(tool_call.function.arguments)
        assert "location" in args

        print(f"\nTool call: {tool_call.function.name}")
        print(f"Arguments: {args}")

    def test_openai_error_handling_invalid_key(self, live_test_warning):
        """
        GOAL: Verify error handling for invalid API key

        GIVEN: Invalid API key
        WHEN: Making an API request
        THEN: AuthenticationError is raised with proper message
        """
        from openai import OpenAI, AuthenticationError

        client = OpenAI(api_key="invalid-key-12345")

        with pytest.raises(AuthenticationError) as exc_info:
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )

        assert "Incorrect API key" in str(exc_info.value) or "invalid" in str(exc_info.value).lower()
        print(f"\nExpected error received: {exc_info.value}")


@pytest.mark.live
@pytest.mark.live_llm
class TestLiveGemini:
    """Live tests for Google Gemini API integration."""

    def test_gemini_simple_completion(self, google_api_key, live_test_warning):
        """
        GOAL: Verify Gemini API response parsing works correctly

        GIVEN: Valid Google API key
        WHEN: Sending a simple completion request
        THEN:
        - Response contains expected fields
        - Token counts are accessible
        - Content is parseable
        """
        from google import genai

        client = genai.Client(api_key=google_api_key)

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents="Say 'test' and nothing else."
        )

        # Verify response structure
        assert response.text is not None
        assert len(response.text) > 0

        # Verify token counts
        assert response.usage_metadata is not None
        assert response.usage_metadata.prompt_token_count > 0
        assert response.usage_metadata.candidates_token_count > 0

        print(f"\nGemini Response: {response.text}")
        print(f"Tokens: prompt={response.usage_metadata.prompt_token_count}, "
              f"completion={response.usage_metadata.candidates_token_count}")


@pytest.mark.live
@pytest.mark.live_embeddings
class TestLiveEmbeddings:
    """Live tests for OpenAI embeddings API."""

    def test_openai_embedding_generation(self, openai_api_key, live_test_warning):
        """
        GOAL: Verify embedding generation works correctly

        GIVEN: Valid OpenAI API key and sample text
        WHEN: Generating embeddings
        THEN:
        - Embedding is returned
        - Correct dimension (1536 for ada-002, 3072 for text-embedding-3-large)
        - Values are floats in expected range
        """
        from openai import OpenAI

        client = OpenAI(api_key=openai_api_key)

        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input="This is a test document for embedding generation."
        )

        # Verify response structure
        assert response.data is not None
        assert len(response.data) > 0

        embedding = response.data[0].embedding

        # Verify dimensions
        assert len(embedding) == 1536, f"Expected 1536 dimensions, got {len(embedding)}"

        # Verify values are floats
        assert all(isinstance(v, float) for v in embedding)

        # Verify values are in reasonable range
        assert all(-1 <= v <= 1 for v in embedding), "Embedding values out of expected range"

        print(f"\nEmbedding generated: {len(embedding)} dimensions")
        print(f"Sample values: {embedding[:5]}")

        # Return embedding for fixture generation
        return embedding

    def test_openai_batch_embedding(self, openai_api_key, live_test_warning):
        """
        GOAL: Verify batch embedding generation works correctly

        GIVEN: Valid OpenAI API key and multiple texts
        WHEN: Generating embeddings in batch
        THEN:
        - All embeddings are returned
        - Each has correct dimensions
        - Order is preserved
        """
        from openai import OpenAI

        client = OpenAI(api_key=openai_api_key)

        texts = [
            "First test document.",
            "Second test document.",
            "Third test document."
        ]

        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=texts
        )

        # Verify correct number of embeddings
        assert len(response.data) == len(texts)

        # Verify each embedding
        for i, data in enumerate(response.data):
            assert data.index == i, "Embeddings returned out of order"
            assert len(data.embedding) == 1536

        print(f"\nBatch embeddings generated: {len(response.data)} embeddings")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "live"])
