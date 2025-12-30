"""
Mock WhatsApp API for testing.

This module mocks:
- requests.post() for WhatsApp API calls
- Webhook verification
- Message sending
"""

from typing import Dict, Any, List, Optional
from unittest.mock import Mock
import json


class WhatsAppMock:
    """Mock for WhatsApp Cloud API."""
    
    def __init__(self):
        self.sent_messages = []
        self.should_fail = False
        self.failure_status_code = 400
        self.failure_message = "Bad Request"
    
    def post(self, url: str, **kwargs) -> Mock:
        """
        Mock requests.post() for WhatsApp API calls.
        
        Args:
            url: API endpoint URL
            **kwargs: Request arguments (headers, json, data, etc.)
        
        Returns:
            Mock Response object
        """
        # Create mock response
        response = Mock()
        
        # Check if this is a WhatsApp API call
        if "graph.facebook.com" in url and "/messages" in url:
            return self._mock_send_message(url, response, **kwargs)
        
        # Default: successful response
        response.status_code = 200
        response.ok = True
        response.json.return_value = {"success": True}
        response.text = json.dumps({"success": True})
        return response
    
    def _mock_send_message(self, url: str, response: Mock, **kwargs) -> Mock:
        """Mock sending a WhatsApp message."""
        # Extract phone_number_id from URL
        # URL format: https://graph.facebook.com/v22.0/{phone_number_id}/messages
        parts = url.split("/")
        phone_number_id = parts[-2] if len(parts) >= 2 else "unknown"
        
        # Get message data
        message_data = kwargs.get("json", {})
        headers = kwargs.get("headers", {})
        
        # Record the message
        sent_message = {
            "url": url,
            "phone_number_id": phone_number_id,
            "to": message_data.get("to"),
            "text": message_data.get("text", {}).get("body"),
            "type": message_data.get("type"),
            "headers": headers,
            "full_payload": message_data,
        }
        self.sent_messages.append(sent_message)
        
        # Simulate failure if configured
        if self.should_fail:
            response.status_code = self.failure_status_code
            response.ok = False
            response.json.return_value = {
                "error": {
                    "message": self.failure_message,
                    "type": "OAuthException",
                    "code": self.failure_status_code
                }
            }
            response.text = json.dumps(response.json.return_value)
            response.raise_for_status.side_effect = Exception(self.failure_message)
            return response
        
        # Successful response
        response.status_code = 200
        response.ok = True
        response.json.return_value = {
            "messaging_product": "whatsapp",
            "contacts": [{
                "input": message_data.get("to"),
                "wa_id": message_data.get("to")
            }],
            "messages": [{
                "id": f"wamid.mock.{len(self.sent_messages)}"
            }]
        }
        response.text = json.dumps(response.json.return_value)
        
        return response
    
    def get_sent_messages(self, to_phone: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of sent messages.
        
        Args:
            to_phone: Filter by recipient phone number (optional)
        
        Returns:
            List of sent messages
        """
        if to_phone:
            return [msg for msg in self.sent_messages if msg["to"] == to_phone]
        return self.sent_messages.copy()
    
    def get_last_message(self, to_phone: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get the last sent message.
        
        Args:
            to_phone: Filter by recipient phone number (optional)
        
        Returns:
            Last message dict or None
        """
        messages = self.get_sent_messages(to_phone)
        return messages[-1] if messages else None
    
    def assert_message_sent(
        self,
        to_phone: str,
        expected_text: Optional[str] = None,
        contains: Optional[str] = None
    ):
        """
        Assert that a message was sent to a specific phone number.
        
        Args:
            to_phone: Expected recipient phone number
            expected_text: Exact text expected (optional)
            contains: Text that should be contained in message (optional)
        
        Raises:
            AssertionError: If message not found or doesn't match criteria
        """
        messages = self.get_sent_messages(to_phone)
        
        assert messages, f"No messages sent to {to_phone}"
        
        if expected_text is not None:
            texts = [msg["text"] for msg in messages]
            assert expected_text in texts, \
                f"Expected text '{expected_text}' not found in messages: {texts}"
        
        if contains is not None:
            last_text = messages[-1]["text"]
            assert contains in last_text, \
                f"Text '{contains}' not found in last message: {last_text}"
    
    def set_failure(self, should_fail: bool = True, status_code: int = 400, message: str = "Bad Request"):
        """
        Configure the mock to simulate API failures.
        
        Args:
            should_fail: Whether to fail requests
            status_code: HTTP status code to return
            message: Error message
        """
        self.should_fail = should_fail
        self.failure_status_code = status_code
        self.failure_message = message
    
    def clear(self):
        """Clear all sent messages."""
        self.sent_messages.clear()
    
    def reset(self):
        """Reset to default state."""
        self.sent_messages.clear()
        self.should_fail = False
        self.failure_status_code = 400
        self.failure_message = "Bad Request"
    
    def get_call_count(self) -> int:
        """Get number of messages sent."""
        return len(self.sent_messages)


class WhatsAppPayloadBuilder:
    """Builder for creating WhatsApp webhook payloads."""
    
    def __init__(self):
        self.payload = {
            "object": "whatsapp_business_account",
            "entry": []
        }
        self.current_entry = None
    
    def with_entry(self, entry_id: str = "test_entry_123"):
        """Start a new entry."""
        self.current_entry = {
            "id": entry_id,
            "changes": []
        }
        self.payload["entry"].append(self.current_entry)
        return self
    
    def with_message(
        self,
        phone_number_id: str,
        from_phone: str,
        message_id: str,
        text: str,
        user_name: str = "Test User"
    ):
        """Add a text message to the current entry."""
        if not self.current_entry:
            self.with_entry()
        
        change = {
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {
                    "display_phone_number": phone_number_id,
                    "phone_number_id": phone_number_id
                },
                "contacts": [{
                    "profile": {
                        "name": user_name
                    },
                    "wa_id": from_phone
                }],
                "messages": [{
                    "from": from_phone,
                    "id": message_id,
                    "timestamp": "1234567890",
                    "text": {
                        "body": text
                    },
                    "type": "text"
                }]
            },
            "field": "messages"
        }
        
        self.current_entry["changes"].append(change)
        return self
    
    def with_status_update(
        self,
        phone_number_id: str,
        message_id: str,
        status: str = "delivered"
    ):
        """Add a status update to the current entry."""
        if not self.current_entry:
            self.with_entry()
        
        change = {
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {
                    "phone_number_id": phone_number_id
                },
                "statuses": [{
                    "id": message_id,
                    "status": status,
                    "timestamp": "1234567890"
                }]
            },
            "field": "messages"
        }
        
        self.current_entry["changes"].append(change)
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build the webhook payload."""
        return self.payload.copy()