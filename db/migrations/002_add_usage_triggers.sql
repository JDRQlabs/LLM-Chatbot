-- Migration: Add usage quota enforcement triggers
-- Purpose: Automatically disable chatbots when usage limits are exceeded
-- Date: 2025-12-29

-- =====================================================================
-- Function: Check and enforce usage limits
-- =====================================================================
-- This function is triggered whenever usage_summary is updated
-- It checks if the organization has exceeded their monthly limits
-- If limits are exceeded, it:
-- 1. Disables all chatbots for that organization
-- 2. Creates a system alert
-- 3. Logs the event

CREATE OR REPLACE FUNCTION check_usage_limits()
RETURNS TRIGGER AS $$
DECLARE
    org_record RECORD;
    chatbots_disabled INT;
BEGIN
    -- Get organization limits
    SELECT
        id,
        name,
        message_limit_monthly,
        token_limit_monthly
    INTO org_record
    FROM organizations
    WHERE id = NEW.organization_id;

    IF NOT FOUND THEN
        RETURN NEW;
    END IF;

    -- Check message limit
    IF NEW.current_period_messages >= org_record.message_limit_monthly THEN

        -- Disable all chatbots for this organization
        UPDATE chatbots
        SET is_active = FALSE
        WHERE organization_id = NEW.organization_id
          AND is_active = TRUE
        RETURNING NULL INTO chatbots_disabled;

        GET DIAGNOSTICS chatbots_disabled = ROW_COUNT;

        -- Create alert
        INSERT INTO system_alerts (
            organization_id,
            type,
            severity,
            message,
            metadata,
            created_at
        ) VALUES (
            NEW.organization_id,
            'QUOTA_EXCEEDED',
            'critical',
            format('Message limit reached (%s/%s). %s chatbots disabled.',
                   NEW.current_period_messages,
                   org_record.message_limit_monthly,
                   chatbots_disabled
            ),
            json_build_object(
                'limit_type', 'messages',
                'current', NEW.current_period_messages,
                'limit', org_record.message_limit_monthly,
                'chatbots_disabled', chatbots_disabled,
                'organization_name', org_record.name
            ),
            NOW()
        );

        RAISE NOTICE 'Organization % exceeded message limit. % chatbots disabled.',
                     org_record.name, chatbots_disabled;

    END IF;

    -- Check token limit
    IF NEW.current_period_tokens >= org_record.token_limit_monthly THEN

        -- Disable all chatbots for this organization (if not already disabled)
        UPDATE chatbots
        SET is_active = FALSE
        WHERE organization_id = NEW.organization_id
          AND is_active = TRUE
        RETURNING NULL INTO chatbots_disabled;

        GET DIAGNOSTICS chatbots_disabled = ROW_COUNT;

        IF chatbots_disabled > 0 THEN
            -- Create alert
            INSERT INTO system_alerts (
                organization_id,
                type,
                severity,
                message,
                metadata,
                created_at
            ) VALUES (
                NEW.organization_id,
                'QUOTA_EXCEEDED',
                'critical',
                format('Token limit reached (%s/%s). %s chatbots disabled.',
                       NEW.current_period_tokens,
                       org_record.token_limit_monthly,
                       chatbots_disabled
                ),
                json_build_object(
                    'limit_type', 'tokens',
                    'current', NEW.current_period_tokens,
                    'limit', org_record.token_limit_monthly,
                    'chatbots_disabled', chatbots_disabled,
                    'organization_name', org_record.name
                ),
                NOW()
            );

            RAISE NOTICE 'Organization % exceeded token limit. % chatbots disabled.',
                         org_record.name, chatbots_disabled;
        END IF;

    END IF;

    -- Check for warning thresholds (80% of limit)
    IF NEW.current_period_messages >= (org_record.message_limit_monthly * 0.8)
       AND NEW.current_period_messages < org_record.message_limit_monthly THEN

        -- Create warning alert
        INSERT INTO system_alerts (
            organization_id,
            type,
            severity,
            message,
            metadata,
            created_at
        ) VALUES (
            NEW.organization_id,
            'QUOTA_EXCEEDED',
            'warning',
            format('Approaching message limit: %s/%s (%.0f%%)',
                   NEW.current_period_messages,
                   org_record.message_limit_monthly,
                   (NEW.current_period_messages::float / org_record.message_limit_monthly) * 100
            ),
            json_build_object(
                'limit_type', 'messages',
                'current', NEW.current_period_messages,
                'limit', org_record.message_limit_monthly,
                'percentage', (NEW.current_period_messages::float / org_record.message_limit_monthly) * 100,
                'threshold', 80
            ),
            NOW()
        )
        ON CONFLICT DO NOTHING;  -- Avoid duplicate warnings

    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- Trigger: Enforce usage limits on usage_summary updates
-- =====================================================================

DROP TRIGGER IF EXISTS trigger_check_usage_limits ON usage_summary;

CREATE TRIGGER trigger_check_usage_limits
AFTER UPDATE ON usage_summary
FOR EACH ROW
WHEN (
    -- Only trigger if counts actually changed
    NEW.current_period_messages > OLD.current_period_messages OR
    NEW.current_period_tokens > OLD.current_period_tokens
)
EXECUTE FUNCTION check_usage_limits();

-- =====================================================================
-- Function: Re-enable chatbots when new billing period starts
-- =====================================================================
-- This should be called via a scheduled job or manually
-- It resets usage counters and re-enables chatbots for orgs that were disabled

CREATE OR REPLACE FUNCTION reset_billing_period()
RETURNS TABLE (
    organization_id UUID,
    organization_name TEXT,
    chatbots_enabled INT,
    old_message_count BIGINT,
    old_token_count BIGINT
) AS $$
DECLARE
    org RECORD;
    chatbots_count INT;
BEGIN
    -- Loop through all organizations
    FOR org IN
        SELECT o.id, o.name, o.billing_period_start, o.billing_period_end,
               us.current_period_messages, us.current_period_tokens
        FROM organizations o
        LEFT JOIN usage_summary us ON o.id = us.organization_id
        WHERE o.billing_period_end < NOW()
    LOOP
        -- Re-enable chatbots that were disabled due to quota
        UPDATE chatbots
        SET is_active = TRUE
        WHERE organization_id = org.id
          AND is_active = FALSE;

        GET DIAGNOSTICS chatbots_count = ROW_COUNT;

        -- Reset usage counters
        UPDATE usage_summary
        SET
            current_period_messages = 0,
            current_period_tokens = 0,
            period_start = NOW(),
            period_end = NOW() + INTERVAL '1 month'
        WHERE organization_id = org.id;

        -- Update organization billing period
        UPDATE organizations
        SET
            billing_period_start = NOW(),
            billing_period_end = NOW() + INTERVAL '1 month'
        WHERE id = org.id;

        -- Create info alert about reset
        INSERT INTO system_alerts (
            organization_id,
            type,
            severity,
            message,
            metadata,
            created_at
        ) VALUES (
            org.id,
            'OTHER',
            'info',
            format('Billing period reset. Previous usage: %s messages, %s tokens. %s chatbots re-enabled.',
                   org.current_period_messages,
                   org.current_period_tokens,
                   chatbots_count
            ),
            json_build_object(
                'previous_messages', org.current_period_messages,
                'previous_tokens', org.current_period_tokens,
                'chatbots_enabled', chatbots_count,
                'new_period_start', NOW(),
                'new_period_end', NOW() + INTERVAL '1 month'
            ),
            NOW()
        );

        -- Return results
        organization_id := org.id;
        organization_name := org.name;
        chatbots_enabled := chatbots_count;
        old_message_count := org.current_period_messages;
        old_token_count := org.current_period_tokens;

        RETURN NEXT;
    END LOOP;

    RETURN;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- Comments
-- =====================================================================

COMMENT ON FUNCTION check_usage_limits() IS 'Automatically enforces message and token limits by disabling chatbots when quotas are exceeded';
COMMENT ON FUNCTION reset_billing_period() IS 'Resets usage counters and re-enables chatbots when billing period ends (should be run monthly via cron)';
COMMENT ON TRIGGER trigger_check_usage_limits ON usage_summary IS 'Enforces usage quotas in real-time as messages are processed';

-- =====================================================================
-- Usage Examples
-- =====================================================================

-- To manually reset billing period for all organizations:
-- SELECT * FROM reset_billing_period();

-- To check current usage for an organization:
-- SELECT
--     o.name,
--     us.current_period_messages,
--     o.message_limit_monthly,
--     us.current_period_tokens,
--     o.token_limit_monthly,
--     (us.current_period_messages::float / o.message_limit_monthly) * 100 as message_usage_percent,
--     (us.current_period_tokens::float / o.token_limit_monthly) * 100 as token_usage_percent
-- FROM organizations o
-- JOIN usage_summary us ON o.id = us.organization_id
-- WHERE o.id = 'your-org-id';
