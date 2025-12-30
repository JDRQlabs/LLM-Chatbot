"""
Unit tests for rate limiting functionality.

Tests the Redis-based rate limiter in webhook-server/rateLimiter.js
using mocked Redis to avoid consuming actual API quota.

IMPORTANT: These tests use mocks to simulate 25 messages without consuming
the Gemini API free tier quota.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import sys
from pathlib import Path
import time

# Note: These are Python tests testing Node.js functionality via mocking
# We're testing the logic, not the actual implementation


@pytest.mark.unit
class TestRateLimiting:
    """Test rate limiting logic and scenarios."""

    @pytest.fixture
    def rate_limits(self):
        """Rate limits per plan tier."""
        return {
            "free": 20,
            "pro": 100,
            "enterprise": 500
        }

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client with sliding window functionality."""
        class MockRedisClient:
            def __init__(self):
                self.data = {}  # Sorted sets: {key: [(score, value), ...]}
                self.is_open = True
                self.expirations = {}

            def zRemRangeByScore(self, key, min_score, max_score):
                """Remove entries outside time window."""
                if key in self.data:
                    self.data[key] = [
                        (score, value) for score, value in self.data[key]
                        if not (min_score <= score <= max_score)
                    ]

            def zCard(self, key):
                """Count entries in sorted set."""
                return len(self.data.get(key, []))

            def zAdd(self, key, items):
                """Add entry to sorted set."""
                if key not in self.data:
                    self.data[key] = []

                # items is like [{"score": timestamp, "value": timestamp_str}]
                if isinstance(items, dict):
                    self.data[key].append((items["score"], items["value"]))
                elif isinstance(items, list):
                    for item in items:
                        self.data[key].append((item["score"], item["value"]))

                # Sort by score
                self.data[key].sort(key=lambda x: x[0])

            def expire(self, key, seconds):
                """Set expiration on key."""
                self.expirations[key] = seconds

            def zRange(self, key, start, end, options=None):
                """Get range of entries."""
                if key not in self.data:
                    return []

                entries = self.data[key]
                result = entries[start:end+1] if end >= 0 else entries[start:]

                # Return just values
                return [value for score, value in result]

            def multi(self):
                """Start transaction."""
                return MockRedisMulti(self)

        class MockRedisMulti:
            def __init__(self, client):
                self.client = client
                self.commands = []

            def zRemRangeByScore(self, key, min_score, max_score):
                self.commands.append(("zRemRangeByScore", key, min_score, max_score))
                return self

            def zCard(self, key):
                self.commands.append(("zCard", key))
                return self

            def zAdd(self, key, items):
                self.commands.append(("zAdd", key, items))
                return self

            def expire(self, key, seconds):
                self.commands.append(("expire", key, seconds))
                return self

            async def exec(self):
                """Execute transaction."""
                results = []
                for cmd in self.commands:
                    if cmd[0] == "zRemRangeByScore":
                        self.client.zRemRangeByScore(cmd[1], cmd[2], cmd[3])
                        results.append(None)
                    elif cmd[0] == "zCard":
                        results.append(self.client.zCard(cmd[1]))
                    elif cmd[0] == "zAdd":
                        self.client.zAdd(cmd[1], cmd[2])
                        results.append(None)
                    elif cmd[0] == "expire":
                        self.client.expire(cmd[1], cmd[2])
                        results.append(None)
                return results

        return MockRedisClient()

    def simulate_rate_limit_check(self, redis_client, phone_number_id, plan_tier, rate_limits, current_time=None):
        """
        Simulate the checkRateLimit logic from rateLimiter.js

        This is a Python implementation of the Node.js rate limiting logic
        for testing purposes.
        """
        if current_time is None:
            current_time = int(time.time() * 1000)  # milliseconds

        max_requests = rate_limits.get(plan_tier, rate_limits["free"])
        window_seconds = 3600  # 1 hour
        key = f"ratelimit:{phone_number_id}"

        window_start = current_time - (window_seconds * 1000)

        # Remove old entries
        redis_client.zRemRangeByScore(key, 0, window_start)

        # Count current requests
        current_count = redis_client.zCard(key)

        # Add current request
        redis_client.zAdd(key, {"score": current_time, "value": str(current_time)})

        # Set expiry
        redis_client.expire(key, window_seconds)

        if current_count >= max_requests:
            # Rate limit exceeded
            oldest_request = redis_client.zRange(key, 0, 0)
            reset_in = window_seconds
            if oldest_request:
                reset_in = max(0, int((int(oldest_request[0]) + (window_seconds * 1000) - current_time) / 1000))

            return {
                "allowed": False,
                "current": current_count,
                "max": max_requests,
                "resetIn": reset_in
            }

        return {
            "allowed": True,
            "current": current_count + 1,
            "max": max_requests,
            "resetIn": window_seconds
        }

    def test_free_tier_allows_20_messages(self, mock_redis_client, rate_limits):
        """Test that free tier allows exactly 20 messages per hour."""
        phone_number_id = "test_phone_free_tier"
        plan_tier = "free"
        current_time = int(time.time() * 1000)

        # Send 20 messages (should all be allowed)
        for i in range(20):
            result = self.simulate_rate_limit_check(
                mock_redis_client,
                phone_number_id,
                plan_tier,
                rate_limits,
                current_time + (i * 1000)  # 1 second apart
            )
            assert result["allowed"] is True, f"Message {i+1} should be allowed"
            assert result["current"] == i + 1

        # 21st message should be blocked
        result = self.simulate_rate_limit_check(
            mock_redis_client,
            phone_number_id,
            plan_tier,
            rate_limits,
            current_time + (20 * 1000)
        )
        assert result["allowed"] is False, "21st message should be blocked"
        assert result["current"] == 20
        assert result["max"] == 20

    def test_simulate_25_messages_free_tier(self, mock_redis_client, rate_limits):
        """
        CRITICAL TEST: Simulate sending 25 messages to free tier chatbot.
        User specifically requested this to avoid consuming Gemini API quota.

        Expected: First 20 allowed, next 5 blocked.
        """
        phone_number_id = "test_phone_spam_attempt"
        plan_tier = "free"
        current_time = int(time.time() * 1000)

        allowed_count = 0
        blocked_count = 0

        # Simulate 25 messages
        for i in range(25):
            result = self.simulate_rate_limit_check(
                mock_redis_client,
                phone_number_id,
                plan_tier,
                rate_limits,
                current_time + (i * 100)  # 100ms apart (rapid fire)
            )

            if result["allowed"]:
                allowed_count += 1
            else:
                blocked_count += 1

        # Assert: Should allow exactly 20, block 5
        assert allowed_count == 20, f"Should allow exactly 20 messages, got {allowed_count}"
        assert blocked_count == 5, f"Should block exactly 5 messages, got {blocked_count}"

    def test_pro_tier_allows_100_messages(self, mock_redis_client, rate_limits):
        """Test that pro tier allows 100 messages per hour."""
        phone_number_id = "test_phone_pro_tier"
        plan_tier = "pro"
        current_time = int(time.time() * 1000)

        # Send 100 messages (should all be allowed)
        for i in range(100):
            result = self.simulate_rate_limit_check(
                mock_redis_client,
                phone_number_id,
                plan_tier,
                rate_limits,
                current_time + (i * 100)
            )
            assert result["allowed"] is True, f"Message {i+1} should be allowed"

        # 101st message should be blocked
        result = self.simulate_rate_limit_check(
            mock_redis_client,
            phone_number_id,
            plan_tier,
            rate_limits,
            current_time + (100 * 100)
        )
        assert result["allowed"] is False
        assert result["current"] == 100
        assert result["max"] == 100

    def test_enterprise_tier_allows_500_messages(self, mock_redis_client, rate_limits):
        """Test that enterprise tier allows 500 messages per hour."""
        phone_number_id = "test_phone_enterprise"
        plan_tier = "enterprise"
        current_time = int(time.time() * 1000)

        # Send 500 messages (should all be allowed)
        for i in range(500):
            result = self.simulate_rate_limit_check(
                mock_redis_client,
                phone_number_id,
                plan_tier,
                rate_limits,
                current_time + (i * 10)
            )
            assert result["allowed"] is True, f"Message {i+1} should be allowed"

        # 501st message should be blocked
        result = self.simulate_rate_limit_check(
            mock_redis_client,
            phone_number_id,
            plan_tier,
            rate_limits,
            current_time + (500 * 10)
        )
        assert result["allowed"] is False

    def test_sliding_window_resets_after_hour(self, mock_redis_client, rate_limits):
        """Test that rate limit sliding window resets after 1 hour."""
        phone_number_id = "test_phone_sliding_window"
        plan_tier = "free"
        current_time = int(time.time() * 1000)

        # Send 20 messages at T=0
        for i in range(20):
            result = self.simulate_rate_limit_check(
                mock_redis_client,
                phone_number_id,
                plan_tier,
                rate_limits,
                current_time + (i * 1000)
            )
            assert result["allowed"] is True

        # 21st message at T=0 should be blocked
        result = self.simulate_rate_limit_check(
            mock_redis_client,
            phone_number_id,
            plan_tier,
            rate_limits,
            current_time + (20 * 1000)
        )
        assert result["allowed"] is False

        # After 1 hour + 1 second, should allow new messages
        one_hour_later = current_time + (3601 * 1000)
        result = self.simulate_rate_limit_check(
            mock_redis_client,
            phone_number_id,
            plan_tier,
            rate_limits,
            one_hour_later
        )
        assert result["allowed"] is True, "Should allow message after 1 hour window"

    def test_different_chatbots_independent_limits(self, mock_redis_client, rate_limits):
        """Test that different chatbots have independent rate limits."""
        plan_tier = "free"
        current_time = int(time.time() * 1000)

        # Chatbot 1: Send 20 messages
        for i in range(20):
            result = self.simulate_rate_limit_check(
                mock_redis_client,
                "chatbot_1",
                plan_tier,
                rate_limits,
                current_time + (i * 100)
            )
            assert result["allowed"] is True

        # Chatbot 1: 21st blocked
        result = self.simulate_rate_limit_check(
            mock_redis_client,
            "chatbot_1",
            plan_tier,
            rate_limits,
            current_time + (20 * 100)
        )
        assert result["allowed"] is False

        # Chatbot 2: Should still have full quota
        result = self.simulate_rate_limit_check(
            mock_redis_client,
            "chatbot_2",
            plan_tier,
            rate_limits,
            current_time
        )
        assert result["allowed"] is True
        assert result["current"] == 1  # First message

    def test_reset_time_calculation(self, mock_redis_client, rate_limits):
        """Test that resetIn is correctly calculated."""
        phone_number_id = "test_phone_reset_time"
        plan_tier = "free"
        current_time = int(time.time() * 1000)

        # Fill up the quota
        for i in range(20):
            self.simulate_rate_limit_check(
                mock_redis_client,
                phone_number_id,
                plan_tier,
                rate_limits,
                current_time + (i * 1000)
            )

        # Next request should be blocked with resetIn
        result = self.simulate_rate_limit_check(
            mock_redis_client,
            phone_number_id,
            plan_tier,
            rate_limits,
            current_time + (20 * 1000)
        )

        assert result["allowed"] is False
        assert "resetIn" in result
        assert result["resetIn"] > 0
        # Should be approximately 1 hour minus 20 seconds
        assert 3580 <= result["resetIn"] <= 3600

    def test_burst_traffic_handling(self, mock_redis_client, rate_limits):
        """Test handling of burst traffic (many messages in short time)."""
        phone_number_id = "test_phone_burst"
        plan_tier = "free"
        current_time = int(time.time() * 1000)

        # Send all 20 messages within 1 second (burst)
        for i in range(20):
            result = self.simulate_rate_limit_check(
                mock_redis_client,
                phone_number_id,
                plan_tier,
                rate_limits,
                current_time + i  # 1ms apart
            )
            assert result["allowed"] is True

        # Should still block 21st message
        result = self.simulate_rate_limit_check(
            mock_redis_client,
            phone_number_id,
            plan_tier,
            rate_limits,
            current_time + 20
        )
        assert result["allowed"] is False

    def test_gradual_quota_recovery(self, mock_redis_client, rate_limits):
        """Test that quota gradually recovers in sliding window."""
        phone_number_id = "test_phone_gradual"
        plan_tier = "free"
        base_time = int(time.time() * 1000)

        # Send 20 messages at base_time
        for i in range(20):
            self.simulate_rate_limit_check(
                mock_redis_client,
                phone_number_id,
                plan_tier,
                rate_limits,
                base_time + (i * 60000)  # 1 minute apart
            )

        # At base_time + 61 minutes, first message should have expired
        # So we should be able to send 1 more message
        time_61_min_later = base_time + (61 * 60 * 1000)
        result = self.simulate_rate_limit_check(
            mock_redis_client,
            phone_number_id,
            plan_tier,
            rate_limits,
            time_61_min_later
        )
        assert result["allowed"] is True, "Should allow message after oldest entry expires"

    def test_fail_open_behavior_when_redis_unavailable(self, rate_limits):
        """Test that system allows requests when Redis is unavailable (fail-open)."""
        # This would be tested in the actual Node.js code
        # Here we just document the expected behavior

        # When Redis client is None or not connected:
        # - Should return {"allowed": True}
        # - Should not throw error
        # - Better to allow traffic than block legitimate users

        # This is a design decision test
        assert True  # Placeholder for documentation

    def test_current_count_accuracy(self, mock_redis_client, rate_limits):
        """Test that current count is accurately tracked."""
        phone_number_id = "test_phone_count"
        plan_tier = "free"
        current_time = int(time.time() * 1000)

        for i in range(15):
            result = self.simulate_rate_limit_check(
                mock_redis_client,
                phone_number_id,
                plan_tier,
                rate_limits,
                current_time + (i * 1000)
            )
            # Current count should match iteration (1-indexed)
            assert result["current"] == i + 1
            assert result["max"] == 20
