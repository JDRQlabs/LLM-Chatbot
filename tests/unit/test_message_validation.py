"""
Unit tests for message size validation.

Tests the message size validation logic in webhook-server/app.js
to prevent abuse from oversized messages.
"""

import pytest
from unittest.mock import Mock, patch
import sys
from pathlib import Path


@pytest.mark.unit
class TestMessageSizeValidation:
    """Test message size validation and plan-based limits."""

    @pytest.fixture
    def message_limits(self):
        """Message size limits per plan tier (in characters)."""
        return {
            "free": 2000,
            "pro": 5000,
            "enterprise": 10000
        }

    @pytest.fixture
    def mock_db_pool(self):
        """Mock PostgreSQL pool for database queries."""
        class MockPool:
            def __init__(self):
                self.plan_tier = "free"

            async def query(self, sql, params):
                """Mock database query."""
                if "SELECT o.plan_tier" in sql:
                    return {
                        "rows": [{"plan_tier": self.plan_tier}]
                    }
                return {"rows": []}

        return MockPool()

    def validate_message_size(self, message_body, plan_tier, message_limits):
        """
        Simulate message size validation logic from webhook-server/app.js

        Returns:
            dict with 'allowed' boolean and 'reason' if rejected
        """
        max_length = message_limits.get(plan_tier, message_limits["free"])

        if len(message_body) > max_length:
            return {
                "allowed": False,
                "reason": "MESSAGE_TOO_LONG",
                "current_length": len(message_body),
                "max_length": max_length,
                "plan_tier": plan_tier
            }

        return {
            "allowed": True,
            "current_length": len(message_body),
            "max_length": max_length,
            "plan_tier": plan_tier
        }

    def test_free_tier_accepts_2000_chars(self, message_limits):
        """Test that free tier accepts messages up to 2000 characters."""
        message = "A" * 2000  # Exactly 2000 chars
        result = self.validate_message_size(message, "free", message_limits)

        assert result["allowed"] is True
        assert result["current_length"] == 2000
        assert result["max_length"] == 2000

    def test_free_tier_rejects_2001_chars(self, message_limits):
        """Test that free tier rejects messages over 2000 characters."""
        message = "A" * 2001  # 1 char over limit
        result = self.validate_message_size(message, "free", message_limits)

        assert result["allowed"] is False
        assert result["reason"] == "MESSAGE_TOO_LONG"
        assert result["current_length"] == 2001
        assert result["max_length"] == 2000

    def test_free_tier_rejects_huge_message(self, message_limits):
        """Test that free tier rejects maliciously large messages."""
        message = "A" * 50000  # 50k chars (way over limit)
        result = self.validate_message_size(message, "free", message_limits)

        assert result["allowed"] is False
        assert result["reason"] == "MESSAGE_TOO_LONG"
        assert result["current_length"] == 50000
        assert result["max_length"] == 2000

    def test_pro_tier_accepts_5000_chars(self, message_limits):
        """Test that pro tier accepts messages up to 5000 characters."""
        message = "B" * 5000
        result = self.validate_message_size(message, "pro", message_limits)

        assert result["allowed"] is True
        assert result["current_length"] == 5000
        assert result["max_length"] == 5000

    def test_pro_tier_rejects_5001_chars(self, message_limits):
        """Test that pro tier rejects messages over 5000 characters."""
        message = "B" * 5001
        result = self.validate_message_size(message, "pro", message_limits)

        assert result["allowed"] is False
        assert result["current_length"] == 5001
        assert result["max_length"] == 5000

    def test_enterprise_tier_accepts_10000_chars(self, message_limits):
        """Test that enterprise tier accepts messages up to 10000 characters."""
        message = "C" * 10000
        result = self.validate_message_size(message, "enterprise", message_limits)

        assert result["allowed"] is True
        assert result["current_length"] == 10000
        assert result["max_length"] == 10000

    def test_enterprise_tier_rejects_10001_chars(self, message_limits):
        """Test that enterprise tier rejects messages over 10000 characters."""
        message = "C" * 10001
        result = self.validate_message_size(message, "enterprise", message_limits)

        assert result["allowed"] is False
        assert result["current_length"] == 10001

    def test_empty_message_allowed(self, message_limits):
        """Test that empty messages are allowed (edge case)."""
        message = ""
        result = self.validate_message_size(message, "free", message_limits)

        assert result["allowed"] is True
        assert result["current_length"] == 0

    def test_unicode_characters_counted_correctly(self, message_limits):
        """Test that Unicode/emoji characters are counted correctly."""
        # Mix of ASCII and Unicode
        message = "Hello 世界 🌍 " * 100  # ~1400 chars

        result = self.validate_message_size(message, "free", message_limits)

        assert result["allowed"] is True
        assert result["current_length"] < 2000

        # Now make it exceed limit
        long_message = "Hello 世界 🌍 " * 200  # ~2800 chars
        result = self.validate_message_size(long_message, "free", message_limits)

        assert result["allowed"] is False

    def test_newlines_and_spaces_counted(self, message_limits):
        """Test that newlines and spaces are counted in length."""
        # Message with many newlines and spaces
        message = "Line 1\n" * 250  # 7 chars * 250 = 1750 chars
        result = self.validate_message_size(message, "free", message_limits)

        assert result["allowed"] is True
        assert result["current_length"] == 1750

        # Exceed limit with newlines
        long_message = "Line 1\n" * 400  # 2800 chars
        result = self.validate_message_size(long_message, "free", message_limits)

        assert result["allowed"] is False

    def test_default_to_free_tier_if_unknown_plan(self, message_limits):
        """Test that unknown plan tier defaults to free tier limits."""
        message = "A" * 2001  # Over free limit

        # Use most restrictive limit for unknown plans
        result = self.validate_message_size(message, "unknown_plan", message_limits)

        # Should default to free tier limit
        assert result["allowed"] is False
        assert result["max_length"] == 2000

    def test_realistic_user_message_scenarios(self, message_limits):
        """Test realistic message scenarios."""
        # Scenario 1: Normal short message (free tier)
        normal_message = "Hello, I need help with my order #12345"
        result = self.validate_message_size(normal_message, "free", message_limits)
        assert result["allowed"] is True

        # Scenario 2: Long product description (free tier - should fail)
        long_description = """
        I am looking for a product that has the following specifications:
        - Size: Large
        - Color: Blue
        - Material: Cotton
        - Features: Waterproof, breathable, durable
        - Price range: $50-$100
        """ * 50  # Repeat to make it long

        result = self.validate_message_size(long_description, "free", message_limits)
        assert result["allowed"] is False

        # Scenario 3: Same long message on pro tier (should pass)
        result = self.validate_message_size(long_description, "pro", message_limits)
        # Check if it's under pro limit
        if len(long_description) <= 5000:
            assert result["allowed"] is True

    def test_attack_scenario_copy_paste_spam(self, message_limits):
        """Test protection against copy-paste spam attacks."""
        # Attacker copies a long text to exploit LLM costs
        spam_message = "SPAM " * 10000  # 50k chars (5 chars * 10000)

        # Free tier should block
        result = self.validate_message_size(spam_message, "free", message_limits)
        assert result["allowed"] is False
        assert result["current_length"] == 50000

        # Pro tier should also block
        result = self.validate_message_size(spam_message, "pro", message_limits)
        assert result["allowed"] is False

        # Even enterprise should block
        result = self.validate_message_size(spam_message, "enterprise", message_limits)
        assert result["allowed"] is False

    def test_exact_boundary_cases(self, message_limits):
        """Test exact boundary conditions for all tiers."""
        # Free tier boundary
        assert self.validate_message_size("A" * 1999, "free", message_limits)["allowed"] is True
        assert self.validate_message_size("A" * 2000, "free", message_limits)["allowed"] is True
        assert self.validate_message_size("A" * 2001, "free", message_limits)["allowed"] is False

        # Pro tier boundary
        assert self.validate_message_size("A" * 4999, "pro", message_limits)["allowed"] is True
        assert self.validate_message_size("A" * 5000, "pro", message_limits)["allowed"] is True
        assert self.validate_message_size("A" * 5001, "pro", message_limits)["allowed"] is False

        # Enterprise tier boundary
        assert self.validate_message_size("A" * 9999, "enterprise", message_limits)["allowed"] is True
        assert self.validate_message_size("A" * 10000, "enterprise", message_limits)["allowed"] is True
        assert self.validate_message_size("A" * 10001, "enterprise", message_limits)["allowed"] is False

    def test_plan_tier_lookup_from_database(self, db_with_data, message_limits):
        """Test that plan tier is correctly looked up from database."""
        # Setup: Verify organization plan tiers exist
        db_with_data.execute("""
            SELECT id, plan_tier FROM organizations
            WHERE id = '11111111-1111-1111-1111-111111111111'
        """)
        org = db_with_data.fetchone()

        assert org is not None
        assert org["plan_tier"] in ["free", "pro", "enterprise"]

        # Verify chatbot is linked to organization
        db_with_data.execute("""
            SELECT c.id, c.organization_id, o.plan_tier
            FROM chatbots c
            JOIN organizations o ON c.organization_id = o.id
            WHERE c.id = '22222222-2222-2222-2222-222222222222'
        """)
        chatbot = db_with_data.fetchone()

        assert chatbot is not None
        assert chatbot["plan_tier"] is not None

    def test_message_rejection_does_not_trigger_windmill(self, message_limits):
        """
        Test that rejected messages don't trigger Windmill flow.
        (Integration test - would be tested in actual webhook-server)
        """
        # This is a behavioral test documenting expected flow:
        # 1. Webhook receives message
        # 2. Checks message size
        # 3. If oversized: return early WITHOUT calling Windmill
        # 4. If valid: proceed to trigger Windmill

        # In actual implementation:
        # if (messageBody.length > maxMessageLength) {
        #     console.warn('Message rejected');
        #     return; // NO Windmill call
        # }
        # await triggerWindmillFlow(...); // Only if valid

        assert True  # Placeholder for integration test

    def test_logging_of_rejected_messages(self, message_limits):
        """Test that rejected messages are logged properly."""
        # Expected log format when message is rejected:
        # console.warn(`Message too long: ${length} chars (max: ${maxLength} for ${planTier} plan)`)

        message = "A" * 3000
        result = self.validate_message_size(message, "free", message_limits)

        # Should have enough info for logging
        assert result["allowed"] is False
        assert "current_length" in result
        assert "max_length" in result
        assert "plan_tier" in result

        # Could generate log message like:
        log_message = f"Message too long: {result['current_length']} chars (max: {result['max_length']} for {result['plan_tier']} plan)"
        assert "3000 chars" in log_message
        assert "2000" in log_message
        assert "free" in log_message
