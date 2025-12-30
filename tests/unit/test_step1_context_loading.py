"""
Unit tests for Step 1: Context Loading

Tests cover:
- Idempotency (duplicate message detection)
- Usage limit checking
- Chatbot configuration loading
- Contact management
- Tool/integration loading
- Chat history retrieval
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "f" / "development"))

# Import the script under test
import importlib.util
spec = importlib.util.spec_from_file_location(
    "step1",
    PROJECT_ROOT / "f" / "development" / "1_whatsapp_context_loading.py"
)
step1 = importlib.util.module_from_spec(spec)


class TestIdempotency:
    """Test idempotency checks (duplicate message handling)."""
    
    @pytest.mark.db
    def test_first_message_creates_webhook_event(
        self,
        db_with_data,
        mock_wmill,
        query_helper
    ):
        """Test that processing a new message creates a webhook event."""
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            result = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15551234567",
                message_id="wamid.new.message.001",
                user_name="New User"
            )
        
        # Should proceed
        assert result["proceed"] is True
        
        # Webhook event should be created
        event = query_helper.get_webhook_event("wamid.new.message.001")
        assert event is not None
        assert event["status"] == "processing"
    
    @pytest.mark.db
    def test_duplicate_message_blocked(
        self,
        db_with_data,
        mock_wmill,
        query_helper
    ):
        """Test that duplicate messages are blocked."""
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            # Process message first time
            result1 = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15551234567",
                message_id="wamid.duplicate.test.001",
                user_name="Test User"
            )
            
            # Mark as completed
            db_with_data.execute(
                "UPDATE webhook_events SET status = 'completed', processed_at = NOW() WHERE whatsapp_message_id = %s",
                ("wamid.duplicate.test.001",)
            )
            db_with_data.connection.commit()
            
            # Try to process same message again
            result2 = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15551234567",
                message_id="wamid.duplicate.test.001",
                user_name="Test User"
            )
        
        # First should proceed
        assert result1["proceed"] is True
        
        # Second should be blocked
        assert result2["proceed"] is False
        assert result2["reason"] == "Duplicate - Already Processed"
    
    @pytest.mark.db
    def test_failed_message_can_be_retried(
        self,
        db_with_data,
        mock_wmill
    ):
        """Test that failed messages can be retried."""
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            # Process message first time
            result1 = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15551234567",
                message_id="wamid.retry.test.001",
                user_name="Test User"
            )
            
            # Mark as failed
            db_with_data.execute(
                """UPDATE webhook_events 
                   SET status = 'failed', 
                       error_message = 'Test failure',
                       processed_at = NOW() 
                   WHERE whatsapp_message_id = %s""",
                ("wamid.retry.test.001",)
            )
            db_with_data.connection.commit()
            
            # Try again
            result2 = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15551234567",
                message_id="wamid.retry.test.001",
                user_name="Test User"
            )
        
        # Both should proceed
        assert result1["proceed"] is True
        assert result2["proceed"] is True
        
        # Status should be updated to processing
        db_with_data.execute(
            "SELECT status FROM webhook_events WHERE whatsapp_message_id = %s",
            ("wamid.retry.test.001",)
        )
        event = db_with_data.fetchone()
        assert event["status"] == "processing"


class TestUsageLimits:
    """Test usage limit checking."""
    
    @pytest.mark.db
    def test_within_limits_proceeds(
        self,
        db_with_data,
        mock_wmill
    ):
        """Test that requests within limits proceed normally."""
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            result = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15551234567",
                message_id="wamid.limits.test.001",
                user_name="Test User"
            )
        
        assert result["proceed"] is True
        assert result["usage_info"]["has_quota"] is True
        assert result["usage_info"]["messages_remaining"] > 0
    
    @pytest.mark.db
    def test_message_limit_exceeded(
        self,
        db_with_data,
        mock_wmill
    ):
        """Test that exceeding message limit blocks processing."""
        # Set organization to have exceeded message limit
        org_id = "11111111-1111-1111-1111-111111111111"
        db_with_data.execute(
            """UPDATE usage_summary 
               SET current_period_messages = 1001,
                   current_period_tokens = 500000
               WHERE organization_id = %s""",
            (org_id,)
        )
        db_with_data.connection.commit()
        
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            result = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15551234567",
                message_id="wamid.limit.exceeded.001",
                user_name="Test User"
            )
        
        assert result["proceed"] is False
        assert result["reason"] == "Usage Limit Exceeded"
        assert result["notify_admin"] is True
        assert result["usage_info"]["has_quota"] is False
        assert result["usage_info"]["limit_type"] == "messages"
    
    @pytest.mark.db
    def test_token_limit_exceeded(
        self,
        db_with_data,
        mock_wmill
    ):
        """Test that exceeding token limit blocks processing."""
        # Set organization to have exceeded token limit
        org_id = "11111111-1111-1111-1111-111111111111"
        db_with_data.execute(
            """UPDATE usage_summary 
               SET current_period_messages = 500,
                   current_period_tokens = 1000001
               WHERE organization_id = %s""",
            (org_id,)
        )
        db_with_data.connection.commit()
        
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            result = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15551234567",
                message_id="wamid.token.limit.001",
                user_name="Test User"
            )
        
        assert result["proceed"] is False
        assert result["usage_info"]["limit_type"] == "tokens"


class TestChatbotConfiguration:
    """Test chatbot configuration loading."""
    
    @pytest.mark.db
    def test_chatbot_not_found(
        self,
        db_with_data,
        mock_wmill
    ):
        """Test handling of non-existent chatbot."""
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            result = step1.main(
                whatsapp_phone_id="nonexistent_phone_id",
                user_phone="15551234567",
                message_id="wamid.notfound.001",
                user_name="Test User"
            )
        
        assert result["proceed"] is False
        assert result["reason"] == "Chatbot not found"
        assert result["notify_admin"] is True
    
    @pytest.mark.db
    def test_chatbot_configuration_loaded(
        self,
        db_with_data,
        mock_wmill,
        query_helper
    ):
        """Test that chatbot configuration is properly loaded."""
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            result = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15551234567",
                message_id="wamid.config.test.001",
                user_name="Test User"
            )
        
        assert result["proceed"] is True
        
        chatbot = result["chatbot"]
        assert chatbot["name"] == "MVP Test Bot"
        assert chatbot["model_name"] == "gemini-3-flash-preview"
        assert chatbot["temperature"] == 0.7
        assert "system_prompt" in chatbot
        assert "wa_token" in chatbot
    
    @pytest.mark.db
    def test_inactive_chatbot_blocked(
        self,
        db_with_data,
        mock_wmill
    ):
        """Test that inactive chatbots are blocked."""
        # Deactivate the chatbot
        db_with_data.execute(
            "UPDATE chatbots SET is_active = FALSE WHERE whatsapp_phone_number_id = %s",
            ("test_phone_123",)
        )
        db_with_data.connection.commit()
        
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            result = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15551234567",
                message_id="wamid.inactive.001",
                user_name="Test User"
            )
        
        assert result["proceed"] is False
        assert result["reason"] == "Service Inactive"


class TestContactManagement:
    """Test contact creation and updates."""
    
    @pytest.mark.db
    def test_new_contact_created(
        self,
        db_with_data,
        mock_wmill,
        query_helper
    ):
        """Test that new contacts are created."""
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            result = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15559999999",  # New phone number
                message_id="wamid.newcontact.001",
                user_name="Brand New User"
            )
        
        assert result["proceed"] is True
        
        user = result["user"]
        assert user["phone"] == "15559999999"
        assert user["name"] == "Brand New User"
        
        # Verify in database
        db_with_data.execute(
            """SELECT * FROM contacts 
               WHERE phone_number = %s 
               AND chatbot_id = %s""",
            ("15559999999", "22222222-2222-2222-2222-222222222222")
        )
        contact = db_with_data.fetchone()
        assert contact is not None
        assert contact["name"] == "Brand New User"
    
    @pytest.mark.db
    def test_existing_contact_updated(
        self,
        db_with_data,
        mock_wmill
    ):
        """Test that existing contacts are updated."""
        # Use existing contact from seed data
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            result = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15550001234",  # Alice from seed data
                message_id="wamid.update.001",
                user_name="Alice Updated Name"
            )
        
        assert result["proceed"] is True
        assert result["user"]["name"] == "Alice Updated Name"
    
    @pytest.mark.db
    def test_manual_mode_blocked(
        self,
        db_with_data,
        mock_wmill
    ):
        """Test that contacts in manual mode are blocked."""
        # Set Alice to manual mode
        db_with_data.execute(
            """UPDATE contacts 
               SET conversation_mode = 'manual' 
               WHERE phone_number = %s""",
            ("15550001234",)
        )
        db_with_data.connection.commit()
        
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            result = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15550001234",
                message_id="wamid.manual.001",
                user_name="Alice Test"
            )
        
        assert result["proceed"] is False
        assert "Manual Mode" in result["reason"]


class TestToolsAndIntegrations:
    """Test tool/integration loading."""
    
    @pytest.mark.db
    def test_active_tools_loaded(
        self,
        db_with_data,
        mock_wmill
    ):
        """Test that active tools are loaded correctly."""
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            result = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15551234567",
                message_id="wamid.tools.001",
                user_name="Test User"
            )
        
        assert result["proceed"] is True
        
        tools = result["tools"]
        assert len(tools) >= 2  # Should have Calculator and Weather
        
        tool_names = [t["name"] for t in tools]
        assert "Math Calculator" in tool_names
        assert "Weather API" in tool_names
    
    @pytest.mark.db
    def test_disabled_tools_excluded(
        self,
        db_with_data,
        mock_wmill
    ):
        """Test that disabled tools are not loaded."""
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            result = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15551234567",
                message_id="wamid.disabled.001",
                user_name="Test User"
            )
        
        tools = result["tools"]
        tool_names = [t["name"] for t in tools]
        
        # "Order Lookup" is disabled in seed data
        assert "Order Lookup" not in tool_names


class TestChatHistory:
    """Test chat history retrieval."""
    
    @pytest.mark.db
    def test_history_loaded_for_existing_user(
        self,
        db_with_data,
        mock_wmill
    ):
        """Test that chat history is loaded for existing users."""
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            result = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15550001234",  # Alice, has history
                message_id="wamid.history.001",
                user_name="Alice Test"
            )
        
        assert result["proceed"] is True
        
        history = result["history"]
        assert len(history) > 0
        
        # Check history structure
        assert "role" in history[0]
        assert "content" in history[0]
    
    @pytest.mark.db
    def test_empty_history_for_new_user(
        self,
        db_with_data,
        mock_wmill
    ):
        """Test that new users have empty history."""
        with patch('wmill.get_resource', mock_wmill.get_resource):
            spec.loader.exec_module(step1)
            
            result = step1.main(
                whatsapp_phone_id="test_phone_123",
                user_phone="15559999999",  # New user
                message_id="wamid.newuser.001",
                user_name="New User"
            )
        
        assert result["proceed"] is True
        assert len(result["history"]) == 0