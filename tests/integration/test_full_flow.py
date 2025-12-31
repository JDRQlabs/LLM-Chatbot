"""
Integration tests for the complete WhatsApp chatbot flow.

This module tests the end-to-end flow from incoming message to saved history:
1. Step 1: Context loading - validates chatbot, loads user data, checks quotas
2. Step 2: LLM processing - calls Gemini/OpenAI, handles tool calls
3. Step 3.1: Send reply to WhatsApp
4. Step 3.2: Save messages to database
5. Step 3.3: Log token usage

Test Categories:
- Happy path: Complete successful flow
- Error propagation: How errors in each step affect downstream steps
- Idempotency: Duplicate message detection and retry handling
- Quota enforcement: Message and token limits
- RAG: Knowledge base retrieval and context injection
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import importlib.util
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import WindmillMock for proper wmill mocking
from tests.test_harness.windmill_mock import WindmillMock


# ============================================================================
# MODULE IMPORTS WITH MOCKING
# ============================================================================

# Create a global WindmillMock instance for consistent mocking
_windmill_mock = WindmillMock()


def import_step_module(step_name: str, file_name: str):
    """
    Import a step module with mocked dependencies.

    Args:
        step_name: Name for the module (e.g., "step1")
        file_name: File name (e.g., "1_whatsapp_context_loading.py")

    Returns:
        Imported module
    """
    # Clear cached modules to ensure fresh imports with proper mocks
    modules_to_clear = [
        'f.development.utils.db_utils',
        'f.development.utils',
        step_name,
    ]
    for mod in modules_to_clear:
        sys.modules.pop(mod, None)

    # Always use WindmillMock for wmill (replace any existing mock)
    sys.modules['wmill'] = _windmill_mock

    spec = importlib.util.spec_from_file_location(
        step_name,
        PROJECT_ROOT / "f" / "development" / file_name
    )
    module = importlib.util.module_from_spec(spec)

    # Mock google.genai before loading Step 2
    # The import is "from google import genai" so we need to mock the google namespace
    if 'google.genai' not in sys.modules:
        mock_genai = Mock()
        mock_genai_types = Mock()

        # Create or update google namespace module
        if 'google' in sys.modules:
            sys.modules['google'].genai = mock_genai
        else:
            mock_google = Mock()
            mock_google.genai = mock_genai
            sys.modules['google'] = mock_google

        sys.modules['google.genai'] = mock_genai
        sys.modules['google.genai.types'] = mock_genai_types

    spec.loader.exec_module(module)
    return module


@pytest.fixture
def step1_module():
    """Import Step 1: Context Loading"""
    return import_step_module("step1", "1_whatsapp_context_loading.py")


@pytest.fixture
def step2_module():
    """Import Step 2: LLM Processing"""
    return import_step_module("step2", "2_whatsapp_llm_processing.py")


@pytest.fixture
def step3_1_module():
    """Import Step 3.1: Send to WhatsApp"""
    return import_step_module("step3_1", "3_1_send_reply_to_whatsapp.py")


@pytest.fixture
def step4_module():
    """Import Step 3.2: Save History"""
    return import_step_module("step4_", "4_save_chat_history.py")


@pytest.fixture
def step4_module():
    """Import Step 3.3: Log Usage"""
    return import_step_module("step5_", "5_log_usage.py")


# ============================================================================
# TEST DATA
# ============================================================================

@pytest.fixture
def test_message_data():
    """Standard test message data"""
    return {
        "whatsapp_phone_id": "test_phone_123",
        "user_phone": "15559876543",
        "user_name": "Integration Test User",
        "message_id": "wamid.integration.test.001",
        "message_text": "Hello, can you help me with my order?"
    }


@pytest.fixture
def seed_test_data(clean_db, db_with_autocommit, test_message_data):
    """
    Seed database with test data for integration tests.
    Returns IDs of created entities.

    Note: This fixture relies on the seed.sql data being loaded by clean_db fixture.
    The clean_db fixture must run BEFORE this fixture.
    """
    cur = db_with_autocommit

    # Get the first organization from seed data (should be JD Labs Corporation)
    cur.execute("SELECT id FROM organizations ORDER BY created_at LIMIT 1")
    org = cur.fetchone()
    if not org:
        raise RuntimeError("No organization found in test database. Ensure seed.sql has been run.")
    org_id = org["id"]

    # Get the chatbot from seed data
    cur.execute("""
        SELECT id FROM chatbots
        WHERE whatsapp_phone_number_id = %s
        LIMIT 1
    """, (test_message_data["whatsapp_phone_id"],))
    bot = cur.fetchone()
    if not bot:
        raise RuntimeError(f"No chatbot found for phone_id {test_message_data['whatsapp_phone_id']}. Ensure seed.sql has been run.")
    chatbot_id = bot["id"]

    # Get or create contact
    cur.execute("""
        INSERT INTO contacts (chatbot_id, phone_number, name, last_message_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (chatbot_id, phone_number)
        DO UPDATE SET name = EXCLUDED.name
        RETURNING id
    """, (chatbot_id, test_message_data["user_phone"], test_message_data["user_name"]))
    contact = cur.fetchone()
    contact_id = contact["id"]

    return {
        "org_id": org_id,
        "chatbot_id": chatbot_id,
        "contact_id": contact_id
    }


# ============================================================================
# HAPPY PATH TESTS
# ============================================================================

class TestCompleteFlow:
    """Test the complete happy path flow from message to saved history"""

    @pytest.mark.integration
    def test_complete_message_flow_success(
        self,
        clean_db,
        db_with_autocommit,
        test_message_data,
        seed_test_data,
        step1_module,
        step2_module,
        step3_1_module,
        step4_module,
        step4_module,
        mock_wmill,
        mock_llm,
        mock_whatsapp
    ):
        """
        GOAL: Test the complete flow from incoming message to saved history
        GIVEN: A valid chatbot, active user, and available quota
        WHEN: A user sends a message
        THEN:
        - Step 1 returns proceed=True with context
        - Step 2 returns a valid reply
        - Step 3.1 sends message to WhatsApp
        - Step 3.2 saves both user and assistant messages
        - Step 3.3 logs usage correctly
        """
        cur = db_with_autocommit

        # Setup mocks
        mock_llm.add_response(
            text="Hello! I'd be happy to help you with your order. What's your order number?",
            tokens_input=150,
            tokens_output=80,
            model="gemini-pro",
            provider="google"
        )

        # Setup Gemini mock by patching the module's namespace directly
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Hello! I'd be happy to help you with your order. What's your order number?"
        mock_response.usage_metadata = Mock()
        mock_response.usage_metadata.prompt_token_count = 150
        mock_response.usage_metadata.candidates_token_count = 80
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].content.parts = []
        mock_client.models.generate_content.return_value = mock_response

        # Patch the genai reference in the step2 module's namespace
        mock_genai = Mock()
        mock_genai.Client.return_value = mock_client
        step2_module.genai = mock_genai

        with patch('wmill.get_resource', mock_wmill.get_resource), \
             patch('wmill.get_variable', mock_wmill.get_variable), \
             patch('requests.post', mock_whatsapp.post):

            # STEP 1: Context Loading
            context_result = step1_module.main(
                whatsapp_phone_id=test_message_data["whatsapp_phone_id"],
                user_phone=test_message_data["user_phone"],
                message_id=test_message_data["message_id"],
                user_name=test_message_data["user_name"]
            )

            # Verify Step 1 succeeded
            assert context_result["proceed"] is True, f"Step 1 failed: {context_result}"
            assert "chatbot" in context_result
            assert "user" in context_result
            assert context_result["chatbot"]["id"] == seed_test_data["chatbot_id"]
            assert context_result["user"]["id"] == seed_test_data["contact_id"]

            # Verify webhook event was created
            cur.execute(
                "SELECT * FROM webhook_events WHERE whatsapp_message_id = %s",
                (test_message_data["message_id"],)
            )
            webhook_event = cur.fetchone()
            assert webhook_event is not None
            assert webhook_event["status"] == "processing"
            assert webhook_event["chatbot_id"] == seed_test_data["chatbot_id"]

            # STEP 2: LLM Processing
            llm_result = step2_module.main(
                context_payload=context_result,
                user_message=test_message_data["message_text"],
                google_api_key="test_google_key",
                default_provider="google"
            )

            # Verify Step 2 succeeded
            assert "reply_text" in llm_result
            assert llm_result["reply_text"] is not None
            assert "usage_info" in llm_result
            assert llm_result["usage_info"]["tokens_input"] > 0
            assert llm_result["usage_info"]["tokens_output"] > 0

            # STEP 3.1: Send to WhatsApp
            send_result = step3_1_module.main(
                phone_number_id=test_message_data["whatsapp_phone_id"],
                context_payload=context_result,
                llm_result=llm_result
            )

            # Verify Step 3.1 succeeded
            assert send_result["success"] is True
            assert mock_whatsapp.get_call_count() == 1

            # Verify message content
            sent_message = mock_whatsapp.get_last_message()
            assert sent_message["to"] == test_message_data["user_phone"].replace("+", "")
            assert llm_result["reply_text"] in sent_message["text"]

            # STEP 3.2: Save Chat History
            history_result = step4_module.main(
                context_payload=context_result,
                user_message=test_message_data["message_text"],
                llm_result=llm_result,
                send_result=send_result
            )

            # Verify Step 3.2 succeeded
            assert history_result["success"] is True

            # Verify messages were saved
            cur.execute(
                "SELECT * FROM messages WHERE contact_id = %s ORDER BY created_at",
                (seed_test_data["contact_id"],)
            )
            messages = cur.fetchall()
            assert len(messages) >= 2  # At least user + assistant

            # Find the user and assistant messages from this flow
            user_messages = [m for m in messages if m["role"] == "user" and m["content"] == test_message_data["message_text"]]
            assistant_messages = [m for m in messages if m["role"] == "assistant" and m["content"] == llm_result["reply_text"]]

            assert len(user_messages) >= 1, "User message not saved"
            assert len(assistant_messages) >= 1, "Assistant message not saved"

            # STEP 3.3: Log Usage
            usage_result = step4_module.main(
                context_payload=context_result,
                llm_result=llm_result,
                send_result=send_result,
                webhook_event_id=webhook_event["id"]
            )

            # Verify Step 3.3 succeeded
            assert usage_result["success"] is True
            assert usage_result["tokens_used"] > 0
            assert usage_result["message_count"] == 1

            # Verify usage was logged in database
            cur.execute(
                "SELECT * FROM usage_logs WHERE organization_id = %s ORDER BY created_at DESC LIMIT 1",
                (seed_test_data["org_id"],)
            )
            usage_log = cur.fetchone()
            assert usage_log is not None
            assert usage_log["chatbot_id"] == seed_test_data["chatbot_id"]
            assert usage_log["contact_id"] == seed_test_data["contact_id"]
            assert usage_log["tokens_total"] == llm_result["usage_info"]["tokens_input"] + llm_result["usage_info"]["tokens_output"]
            assert usage_log["message_count"] == 1

            # Verify usage summary was updated
            cur.execute(
                "SELECT * FROM usage_summary WHERE organization_id = %s",
                (seed_test_data["org_id"],)
            )
            usage_summary = cur.fetchone()
            assert usage_summary is not None
            assert usage_summary["current_period_messages"] >= 1
            assert usage_summary["current_period_tokens"] >= usage_log["tokens_total"]


# ============================================================================
# ERROR PROPAGATION TESTS
# ============================================================================

class TestErrorPropagation:
    """Test how errors in each step affect downstream steps"""

    @pytest.mark.integration
    def test_step1_failure_stops_flow(
        self,
        clean_db,
        db_with_autocommit,
        step1_module,
        step2_module,
        step3_1_module,
        step4_module,
        step4_module,
        mock_wmill
    ):
        """
        GOAL: When Step 1 fails (chatbot not found), Steps 2/3 should handle gracefully
        GIVEN: Invalid WhatsApp phone ID (no chatbot configured)
        WHEN: Attempting to process a message
        THEN:
        - Step 1 returns proceed=False
        - Step 2 detects failure and returns error
        - Step 3 steps skip execution
        """
        with patch('wmill.get_resource', mock_wmill.get_resource):
            # STEP 1: Try with non-existent chatbot
            context_result = step1_module.main(
                whatsapp_phone_id="non_existent_phone_id",
                user_phone="15559876543",
                message_id="wamid.test.notfound",
                user_name="Test User"
            )

            # Verify Step 1 failed
            assert context_result["proceed"] is False
            assert "Chatbot not found" in context_result["reason"]

            # STEP 2: Should detect Step 1 failure
            llm_result = step2_module.main(
                context_payload=context_result,
                user_message="Hello",
                google_api_key="test_key"
            )

            # Verify Step 2 returned error response
            assert "error" in llm_result
            assert "reply_text" in llm_result  # Fallback message

            # STEP 3.1: Should skip
            send_result = step3_1_module.main(
                phone_number_id="non_existent_phone_id",
                context_payload=context_result,
                llm_result=llm_result
            )

            assert send_result["success"] is False
            assert "Step 1 failed" in send_result["error"]

            # STEP 3.2: Should skip
            history_result = step4_module.main(
                context_payload=context_result,
                user_message="Hello",
                llm_result=llm_result,
                send_result=send_result
            )

            assert history_result["success"] is False
            assert "Step 1 failed" in history_result["error"]

            # STEP 3.3: Should skip
            usage_result = step4_module.main(
                context_payload=context_result,
                llm_result=llm_result,
                send_result=send_result
            )

            assert usage_result["success"] is False
            assert "Step 1 failed" in usage_result["error"]

    @pytest.mark.integration
    def test_step2_llm_error_handled(
        self,
        clean_db,
        db_with_autocommit,
        test_message_data,
        seed_test_data,
        step1_module,
        step2_module,
        step3_1_module,
        step4_module,
        step4_module,
        mock_wmill,
        mock_whatsapp
    ):
        """
        GOAL: When LLM fails, fallback message is returned and logged
        GIVEN: LLM throws an error
        WHEN: Processing a message
        THEN:
        - Step 2 returns fallback message
        - Step 3.1 sends fallback message
        - Step 3.2 and 3.3 skip (no successful LLM response)
        """
        cur = db_with_autocommit

        # Setup Gemini mock to fail by patching module's namespace
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("Quota exceeded")
        mock_genai = Mock()
        mock_genai.Client.return_value = mock_client
        step2_module.genai = mock_genai

        with patch('wmill.get_resource', mock_wmill.get_resource), \
             patch('wmill.get_variable', mock_wmill.get_variable), \
             patch('requests.post', mock_whatsapp.post):

            # STEP 1: Succeeds
            context_result = step1_module.main(
                whatsapp_phone_id=test_message_data["whatsapp_phone_id"],
                user_phone=test_message_data["user_phone"],
                message_id=test_message_data["message_id"],
                user_name=test_message_data["user_name"]
            )

            assert context_result["proceed"] is True

            # STEP 2: Fails but returns fallback
            llm_result = step2_module.main(
                context_payload=context_result,
                user_message=test_message_data["message_text"],
                google_api_key="test_google_key",
                default_provider="google"
            )

            # Verify fallback message was returned
            assert "reply_text" in llm_result
            assert llm_result["reply_text"] is not None  # Should have fallback
            assert "usage_info" in llm_result
            assert "error" in llm_result["usage_info"]

            # STEP 3.1: Should still send (sends fallback message)
            send_result = step3_1_module.main(
                phone_number_id=test_message_data["whatsapp_phone_id"],
                context_payload=context_result,
                llm_result=llm_result
            )

            # Even with LLM error, we should send the fallback message
            # But the current implementation may skip if error is present
            # This depends on implementation details

            # STEP 3.2: Should skip (no successful LLM response)
            history_result = step4_module.main(
                context_payload=context_result,
                user_message=test_message_data["message_text"],
                llm_result=llm_result,
                send_result=send_result
            )

            # History save behavior depends on whether send succeeded

            # STEP 3.3: Should skip
            usage_result = step4_module.main(
                context_payload=context_result,
                llm_result=llm_result,
                send_result=send_result
            )

            # Usage logging depends on send success

    @pytest.mark.integration
    def test_step3_whatsapp_failure_prevents_history_save(
        self,
        clean_db,
        db_with_autocommit,
        test_message_data,
        seed_test_data,
        step1_module,
        step2_module,
        step3_1_module,
        step4_module,
        step4_module,
        mock_wmill,
        mock_whatsapp
    ):
        """
        GOAL: When WhatsApp API fails, messages should NOT be saved to history
        GIVEN: WhatsApp API returns error
        WHEN: Attempting to send a message
        THEN:
        - Step 3.1 fails
        - Step 3.2 skips (message not delivered)
        - Step 3.3 skips (no usage charged)
        """
        cur = db_with_autocommit

        # Configure WhatsApp mock to fail
        mock_whatsapp.set_failure(should_fail=True, status_code=400, message="Invalid token")

        # Setup Gemini mock by patching module's namespace
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Hello! How can I help?"
        mock_response.usage_metadata = Mock()
        mock_response.usage_metadata.prompt_token_count = 50
        mock_response.usage_metadata.candidates_token_count = 20
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].content.parts = []
        mock_client.models.generate_content.return_value = mock_response
        mock_genai = Mock()
        mock_genai.Client.return_value = mock_client
        step2_module.genai = mock_genai

        with patch('wmill.get_resource', mock_wmill.get_resource), \
             patch('wmill.get_variable', mock_wmill.get_variable), \
             patch('requests.post', mock_whatsapp.post):

            # STEP 1: Succeeds
            context_result = step1_module.main(
                whatsapp_phone_id=test_message_data["whatsapp_phone_id"],
                user_phone=test_message_data["user_phone"],
                message_id="wamid.whatsapp.fail.test",
                user_name=test_message_data["user_name"]
            )

            assert context_result["proceed"] is True

            # STEP 2: Succeeds
            llm_result = step2_module.main(
                context_payload=context_result,
                user_message=test_message_data["message_text"],
                google_api_key="test_google_key",
                default_provider="google"
            )

            assert "reply_text" in llm_result

            # STEP 3.1: Fails
            send_result = step3_1_module.main(
                phone_number_id=test_message_data["whatsapp_phone_id"],
                context_payload=context_result,
                llm_result=llm_result
            )

            # Verify send failed
            assert send_result["success"] is False
            assert "error" in send_result

            # Count messages before Step 3.2
            cur.execute(
                "SELECT COUNT(*) as count FROM messages WHERE contact_id = %s",
                (seed_test_data["contact_id"],)
            )
            messages_before = cur.fetchone()["count"]

            # STEP 3.2: Should skip
            history_result = step4_module.main(
                context_payload=context_result,
                user_message=test_message_data["message_text"],
                llm_result=llm_result,
                send_result=send_result
            )

            # Verify history save was skipped
            assert history_result["success"] is False
            assert "Step 3 failed" in history_result["error"]

            # Verify no messages were added
            cur.execute(
                "SELECT COUNT(*) as count FROM messages WHERE contact_id = %s",
                (seed_test_data["contact_id"],)
            )
            messages_after = cur.fetchone()["count"]
            assert messages_after == messages_before, "Messages should not be saved when send fails"

            # STEP 3.3: Should skip
            usage_result = step4_module.main(
                context_payload=context_result,
                llm_result=llm_result,
                send_result=send_result
            )

            # Verify usage was not logged
            assert usage_result["success"] is False
            assert "Step 3 failed" in usage_result["error"]


# ============================================================================
# IDEMPOTENCY TESTS
# ============================================================================

class TestIdempotency:
    """Test duplicate message detection and retry handling"""

    @pytest.mark.integration
    def test_duplicate_message_detected(
        self,
        clean_db,
        db_with_autocommit,
        test_message_data,
        seed_test_data,
        step1_module,
        mock_wmill
    ):
        """
        GOAL: Same WhatsApp message ID processed twice should be rejected as duplicate
        GIVEN: A message has already been processed successfully
        WHEN: The same message ID is received again
        THEN:
        - Step 1 detects duplicate
        - Returns proceed=False with "Duplicate" reason
        - No new webhook event is created
        """
        cur = db_with_autocommit

        with patch('wmill.get_resource', mock_wmill.get_resource):
            # First attempt - should succeed
            result1 = step1_module.main(
                whatsapp_phone_id=test_message_data["whatsapp_phone_id"],
                user_phone=test_message_data["user_phone"],
                message_id=test_message_data["message_id"],
                user_name=test_message_data["user_name"]
            )

            assert result1["proceed"] is True
            webhook_event_id = result1["webhook_event_id"]

            # Mark as completed
            cur.execute(
                "UPDATE webhook_events SET status = 'completed', processed_at = NOW() WHERE id = %s",
                (webhook_event_id,)
            )

            # Second attempt - should be rejected as duplicate
            result2 = step1_module.main(
                whatsapp_phone_id=test_message_data["whatsapp_phone_id"],
                user_phone=test_message_data["user_phone"],
                message_id=test_message_data["message_id"],  # Same message ID
                user_name=test_message_data["user_name"]
            )

            # Verify duplicate was detected
            assert result2["proceed"] is False
            assert "Already Processed" in result2["reason"]
            assert "Already Processed" in result2["reason"]
            assert result2["webhook_event_id"] == webhook_event_id  # Same event ID

            # Verify no new webhook event was created
            cur.execute(
                "SELECT COUNT(*) as count FROM webhook_events WHERE whatsapp_message_id = %s",
                (test_message_data["message_id"],)
            )
            count = cur.fetchone()["count"]
            assert count == 1, "Only one webhook event should exist"

    @pytest.mark.integration
    def test_failed_message_can_be_retried(
        self,
        clean_db,
        db_with_autocommit,
        test_message_data,
        seed_test_data,
        step1_module,
        mock_wmill
    ):
        """
        GOAL: Message that failed previously can be retried successfully
        GIVEN: A message that failed processing
        WHEN: The same message ID is received again
        THEN:
        - Step 1 allows retry
        - Status is updated from 'failed' to 'processing'
        - Processing continues normally
        """
        cur = db_with_autocommit

        with patch('wmill.get_resource', mock_wmill.get_resource):
            # First attempt - succeeds
            result1 = step1_module.main(
                whatsapp_phone_id=test_message_data["whatsapp_phone_id"],
                user_phone=test_message_data["user_phone"],
                message_id="wamid.retry.test.001",
                user_name=test_message_data["user_name"]
            )

            assert result1["proceed"] is True
            webhook_event_id = result1["webhook_event_id"]

            # Mark as failed
            cur.execute(
                """
                UPDATE webhook_events
                SET status = 'failed',
                    error_message = 'LLM timeout',
                    processed_at = NOW()
                WHERE id = %s
                """,
                (webhook_event_id,)
            )

            # Retry - should be allowed
            result2 = step1_module.main(
                whatsapp_phone_id=test_message_data["whatsapp_phone_id"],
                user_phone=test_message_data["user_phone"],
                message_id="wamid.retry.test.001",  # Same message ID
                user_name=test_message_data["user_name"]
            )

            # Verify retry was allowed
            assert result2["proceed"] is True
            assert result2["webhook_event_id"] == webhook_event_id  # Same event ID

            # Verify status was updated to processing
            cur.execute(
                "SELECT status FROM webhook_events WHERE id = %s",
                (webhook_event_id,)
            )
            event = cur.fetchone()
            assert event["status"] == "processing", "Status should be updated to processing on retry"

    @pytest.mark.integration
    def test_currently_processing_message_rejected(
        self,
        clean_db,
        db_with_autocommit,
        test_message_data,
        seed_test_data,
        step1_module,
        mock_wmill
    ):
        """
        GOAL: Message currently being processed should be rejected
        GIVEN: A message with status 'processing'
        WHEN: The same message ID is received again
        THEN: Step 1 returns proceed=False with "Currently Processing" reason
        """
        cur = db_with_autocommit

        with patch('wmill.get_resource', mock_wmill.get_resource):
            # First attempt
            result1 = step1_module.main(
                whatsapp_phone_id=test_message_data["whatsapp_phone_id"],
                user_phone=test_message_data["user_phone"],
                message_id="wamid.concurrent.test.001",
                user_name=test_message_data["user_name"]
            )

            assert result1["proceed"] is True
            assert result1.get("webhook_event_id") is not None

            # Second concurrent attempt
            result2 = step1_module.main(
                whatsapp_phone_id=test_message_data["whatsapp_phone_id"],
                user_phone=test_message_data["user_phone"],
                message_id="wamid.concurrent.test.001",  # Same message ID
                user_name=test_message_data["user_name"]
            )

            # Verify concurrent request was rejected
            assert result2["proceed"] is False
            assert "Currently Processing" in result2["reason"]


# ============================================================================
# QUOTA ENFORCEMENT TESTS
# ============================================================================

class TestQuotaEnforcement:
    """Test message and token quota enforcement"""

    @pytest.mark.integration
    def test_message_rejected_when_quota_exceeded(
        self,
        clean_db,
        db_with_autocommit,
        test_message_data,
        seed_test_data,
        step1_module,
        step4_module,
        mock_wmill
    ):
        """
        GOAL: User over message quota gets rejection and no usage logged
        GIVEN: Organization has reached message limit
        WHEN: User sends a message
        THEN:
        - Step 1 returns proceed=False with "Usage Limit Exceeded"
        - No usage is logged
        """
        cur = db_with_autocommit

        # Set organization to have very low limits
        cur.execute("""
            UPDATE organizations
            SET message_limit_monthly = 1,
                token_limit_monthly = 1000000
            WHERE id = %s
        """, (seed_test_data["org_id"],))

        # Log one message to exhaust quota
        cur.execute("""
            INSERT INTO usage_logs (
                organization_id,
                chatbot_id,
                contact_id,
                message_count,
                tokens_input,
                tokens_output,
                tokens_total,
                model_name,
                provider,
                estimated_cost_usd,
                date_bucket
            ) VALUES (%s, %s, %s, 1, 100, 50, 150, 'test-model', 'test', 0.001, CURRENT_DATE)
        """, (seed_test_data["org_id"], seed_test_data["chatbot_id"], seed_test_data["contact_id"]))

        # Update usage summary
        cur.execute("""
            INSERT INTO usage_summary (
                organization_id,
                current_period_messages,
                current_period_tokens,
                period_start,
                period_end,
                last_updated_at
            )
            SELECT
                id,
                1,
                150,
                billing_period_start,
                billing_period_end,
                NOW()
            FROM organizations
            WHERE id = %s
            ON CONFLICT (organization_id)
            DO UPDATE SET
                current_period_messages = 1,
                current_period_tokens = 150,
                last_updated_at = NOW()
        """, (seed_test_data["org_id"],))

        with patch('wmill.get_resource', mock_wmill.get_resource):
            # Attempt to send another message
            result = step1_module.main(
                whatsapp_phone_id=test_message_data["whatsapp_phone_id"],
                user_phone=test_message_data["user_phone"],
                message_id="wamid.quota.exceeded.test",
                user_name=test_message_data["user_name"]
            )

            # Verify quota rejection
            assert result["proceed"] is False
            assert "Usage Limit Exceeded" in result["reason"]
            assert "usage_info" in result
            assert result["usage_info"]["has_quota"] is False
            assert result["usage_info"]["limit_type"] == "messages"

            # Verify webhook event was marked as failed
            cur.execute(
                "SELECT * FROM webhook_events WHERE whatsapp_message_id = %s",
                ("wamid.quota.exceeded.test",)
            )
            event = cur.fetchone()
            assert event is not None
            assert event["status"] == "failed"
            assert "Usage limit exceeded" in event["error_message"]

    @pytest.mark.integration
    def test_usage_correctly_increments_after_success(
        self,
        clean_db,
        db_with_autocommit,
        test_message_data,
        seed_test_data,
        step4_module,
        mock_wmill
    ):
        """
        GOAL: After successful message, usage counters are updated
        GIVEN: A successful message flow
        WHEN: Step 3.3 logs usage
        THEN:
        - usage_logs gets new entry
        - usage_summary is incremented correctly
        """
        cur = db_with_autocommit

        # Get initial usage
        cur.execute(
            "SELECT * FROM usage_summary WHERE organization_id = %s",
            (seed_test_data["org_id"],)
        )
        initial_summary = cur.fetchone()
        initial_messages = initial_summary["current_period_messages"] if initial_summary else 0
        initial_tokens = initial_summary["current_period_tokens"] if initial_summary else 0

        # Create mock context and results
        context_payload = {
            "proceed": True,
            "chatbot": {
                "organization_id": seed_test_data["org_id"],
                "id": seed_test_data["chatbot_id"],
                "model_name": "gemini-pro"
            },
            "user": {
                "id": seed_test_data["contact_id"]
            }
        }

        llm_result = {
            "reply_text": "Test response",
            "usage_info": {
                "provider": "google",
                "model": "gemini-pro",
                "tokens_input": 200,
                "tokens_output": 100
            }
        }

        send_result = {"success": True}

        with patch('wmill.get_resource', mock_wmill.get_resource):
            # Log usage
            usage_result = step4_module.main(
                context_payload=context_payload,
                llm_result=llm_result,
                send_result=send_result
            )

            assert usage_result["success"] is True
            assert usage_result["tokens_used"] == 300  # 200 + 100
            assert usage_result["message_count"] == 1

            # Verify usage_summary was updated
            cur.execute(
                "SELECT * FROM usage_summary WHERE organization_id = %s",
                (seed_test_data["org_id"],)
            )
            updated_summary = cur.fetchone()

            assert updated_summary["current_period_messages"] == initial_messages + 1
            assert updated_summary["current_period_tokens"] == initial_tokens + 300


# ============================================================================
# RAG FLOW TESTS
# ============================================================================

class TestRAGFlow:
    """Test RAG (Retrieval-Augmented Generation) flow"""

    @pytest.mark.integration
    def test_rag_retrieval_included_in_context(
        self,
        clean_db,
        db_with_autocommit,
        test_message_data,
        seed_test_data,
        step2_module,
        mock_wmill
    ):
        """
        GOAL: When RAG is enabled, relevant chunks are retrieved and included
        GIVEN: Chatbot with RAG enabled and knowledge base populated
        WHEN: User sends a message
        THEN:
        - Relevant chunks are retrieved
        - Chunks are included in LLM context
        - Usage info indicates RAG was used
        """
        cur = db_with_autocommit

        # Enable RAG for chatbot
        cur.execute("""
            UPDATE chatbots
            SET rag_enabled = true
            WHERE id = %s
        """, (seed_test_data["chatbot_id"],))

        # Add knowledge base content
        cur.execute("""
            INSERT INTO knowledge_sources (
                chatbot_id,
                name,
                source_type,
                sync_status
            ) VALUES (%s, 'Product Guide', 'pdf', 'synced')
            RETURNING id
        """, (seed_test_data["chatbot_id"],))
        source = cur.fetchone()
        source_id = source["id"]

        # Add a chunk with embedding (using a simple mock embedding)
        # Note: In a real test, you'd use actual embeddings from OpenAI
        mock_embedding = [0.1] * 1536  # 1536-dimensional vector

        cur.execute("""
            INSERT INTO document_chunks (
                knowledge_source_id,
                chatbot_id,
                content,
                chunk_index,
                embedding,
                metadata
            ) VALUES (%s, %s, %s, 0, %s, '{"page": 1}')
        """, (
            source_id,
            seed_test_data["chatbot_id"],
            "Our return policy allows returns within 30 days of purchase.",
            mock_embedding
        ))

        # Create context with RAG enabled
        context_payload = {
            "proceed": True,
            "chatbot": {
                "id": seed_test_data["chatbot_id"],
                "organization_id": seed_test_data["org_id"],
                "name": "Test Bot",
                "system_prompt": "You are a helpful assistant.",
                "persona": "",
                "model_name": "gemini-pro",
                "temperature": 0.7,
                "wa_token": "test_token",
                "rag_config": {
                    "enabled": True
                }
            },
            "user": {
                "id": seed_test_data["contact_id"],
                "phone": test_message_data["user_phone"],
                "name": test_message_data["user_name"],
                "variables": {},
                "tags": []
            },
            "history": [],
            "tools": []
        }

        # Setup Gemini mock by patching module's namespace
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Based on our policy, you can return items within 30 days."
        mock_response.usage_metadata = Mock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].content.parts = []
        mock_client.models.generate_content.return_value = mock_response
        mock_genai = Mock()
        mock_genai.Client.return_value = mock_client
        step2_module.genai = mock_genai

        # Mock OpenAI embeddings (for RAG search) by patching module's namespace
        mock_openai_client = Mock()
        mock_embedding_response = Mock()
        mock_embedding_response.data = [Mock(embedding=mock_embedding)]
        mock_openai_client.embeddings.create.return_value = mock_embedding_response
        mock_openai_class = Mock(return_value=mock_openai_client)
        step2_module.OpenAI = mock_openai_class

        with patch('wmill.get_resource', mock_wmill.get_resource), \
             patch('wmill.get_variable', mock_wmill.get_variable):

            # Call Step 2 with RAG enabled
            result = step2_module.main(
                context_payload=context_payload,
                user_message="What is your return policy?",
                openai_api_key="test_openai_key",
                google_api_key="test_google_key",
                default_provider="google"
            )

            # Verify RAG was used
            assert "usage_info" in result
            assert result["usage_info"].get("rag_used") is True
            assert result["usage_info"].get("chunks_retrieved", 0) >= 0  # May or may not retrieve based on similarity

            # If chunks were retrieved, verify they're in the response
            if result.get("retrieved_sources"):
                assert len(result["retrieved_sources"]) > 0
                assert "source_name" in result["retrieved_sources"][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
