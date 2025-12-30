"""
Mock LLM providers for testing.

This module mocks:
- OpenAI API
- Google Gemini API
"""

from typing import Dict, Any, List, Optional
from unittest.mock import Mock
from dataclasses import dataclass


@dataclass
class MockLLMResponse:
    """Mock LLM response structure."""
    text: str
    tokens_input: int
    tokens_output: int
    model: str
    provider: str


class LLMMock:
    """Mock for LLM providers (OpenAI, Google Gemini)."""
    
    def __init__(self):
        self.responses = []
        self.call_history = []
        self.default_response = MockLLMResponse(
            text="This is a test response from the AI assistant.",
            tokens_input=100,
            tokens_output=50,
            model="test-model",
            provider="test"
        )
    
    def add_response(
        self,
        text: str,
        tokens_input: int = 100,
        tokens_output: int = 50,
        model: str = "test-model",
        provider: str = "test"
    ):
        """
        Add a response to the queue.
        Responses are returned in FIFO order.
        
        Args:
            text: Response text
            tokens_input: Input token count
            tokens_output: Output token count
            model: Model name
            provider: Provider name
        """
        self.responses.append(MockLLMResponse(
            text=text,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            model=model,
            provider=provider
        ))
    
    def get_next_response(self) -> MockLLMResponse:
        """Get next response from queue, or default if queue is empty."""
        if self.responses:
            return self.responses.pop(0)
        return self.default_response
    
    def get_openai_client(self, api_key: str):
        """
        Mock OpenAI client.
        
        Returns:
            Mock OpenAI client object
        """
        mock_client = Mock()
        
        def create_completion(**kwargs):
            # Record the call
            self.call_history.append({
                "provider": "openai",
                "kwargs": kwargs
            })
            
            # Get response
            response = self.get_next_response()
            
            # Create mock response object
            mock_response = Mock()
            mock_message = Mock()
            mock_message.content = response.text
            mock_choice = Mock()
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            
            # Add usage info
            mock_usage = Mock()
            mock_usage.prompt_tokens = response.tokens_input
            mock_usage.completion_tokens = response.tokens_output
            mock_usage.total_tokens = response.tokens_input + response.tokens_output
            mock_response.usage = mock_usage
            
            return mock_response
        
        mock_client.chat.completions.create = create_completion
        return mock_client
    
    def get_google_client(self, model_name: str):
        """
        Mock Google Gemini client.
        
        Returns:
            Mock Google GenerativeModel object
        """
        mock_model = Mock()
        
        def start_chat(**kwargs):
            mock_chat = Mock()
            
            def send_message(content: str):
                # Record the call
                self.call_history.append({
                    "provider": "google",
                    "model": model_name,
                    "content": content
                })
                
                # Get response
                response = self.get_next_response()
                
                # Create mock response
                mock_response = Mock()
                mock_response.text = response.text
                
                # Add usage metadata if available
                mock_metadata = Mock()
                mock_metadata.prompt_token_count = response.tokens_input
                mock_metadata.candidates_token_count = response.tokens_output
                mock_metadata.total_token_count = response.tokens_input + response.tokens_output
                mock_response.usage_metadata = mock_metadata
                
                return mock_response
            
            mock_chat.send_message = send_message
            return mock_chat
        
        mock_model.start_chat = start_chat
        return mock_model
    
    def get_call_count(self, provider: Optional[str] = None) -> int:
        """
        Get number of LLM calls made.
        
        Args:
            provider: Filter by provider (openai, google), or None for all
        
        Returns:
            Number of calls
        """
        if provider:
            return sum(1 for call in self.call_history if call.get("provider") == provider)
        return len(self.call_history)
    
    def get_last_call(self) -> Optional[Dict[str, Any]]:
        """Get the last LLM call made."""
        return self.call_history[-1] if self.call_history else None
    
    def clear_history(self):
        """Clear call history."""
        self.call_history.clear()
    
    def reset(self):
        """Reset all responses and history."""
        self.responses.clear()
        self.call_history.clear()


class LLMResponseBuilder:
    """Builder for creating complex mock LLM responses."""
    
    def __init__(self):
        self.response = {
            "text": "",
            "tokens_input": 100,
            "tokens_output": 50,
            "model": "test-model",
            "provider": "test",
            "tool_calls": None,
        }
    
    def with_text(self, text: str):
        """Set response text."""
        self.response["text"] = text
        return self
    
    def with_tokens(self, input_tokens: int, output_tokens: int):
        """Set token counts."""
        self.response["tokens_input"] = input_tokens
        self.response["tokens_output"] = output_tokens
        return self
    
    def with_model(self, model: str, provider: str):
        """Set model and provider."""
        self.response["model"] = model
        self.response["provider"] = provider
        return self
    
    def with_tool_call(self, tool_name: str, arguments: Dict[str, Any]):
        """Add a tool call."""
        if self.response["tool_calls"] is None:
            self.response["tool_calls"] = []
        
        self.response["tool_calls"].append({
            "name": tool_name,
            "arguments": arguments
        })
        return self
    
    def build(self) -> MockLLMResponse:
        """Build the response object."""
        return MockLLMResponse(**{
            k: v for k, v in self.response.items()
            if k in ["text", "tokens_input", "tokens_output", "model", "provider"]
        })