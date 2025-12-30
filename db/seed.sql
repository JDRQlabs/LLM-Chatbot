/* 
====================================================================
  SEED DATA v2.0
  Run this AFTER create.sql to populate test data.
  
  Note: ${VARIABLES} are replaced by manage_db.sh from .env file
====================================================================
*/

-- 1. Create Organization with Usage Limits
INSERT INTO organizations (
    id, 
    name, 
    slug, 
    plan_tier,
    message_limit_monthly,
    token_limit_monthly,
    billing_period_start,
    billing_period_end,
    is_active
) VALUES (
    '11111111-1111-1111-1111-111111111111',
    'Dev Corp',
    'dev-corp',
    'pro', -- Pro plan
    1000, -- 1000 messages per month
    1000000, -- 1M tokens per month
    CURRENT_DATE,
    CURRENT_DATE + INTERVAL '1 month',
    TRUE
);

-- 2. Create Users
INSERT INTO users (id, organization_id, email, full_name, role) VALUES 
(
    '99999999-9999-9999-9999-999999999999',
    '11111111-1111-1111-1111-111111111111',
    '${OWNER_EMAIL}',
    'Admin User',
    'owner'
),
(
    '88888888-8888-8888-8888-888888888888',
    '11111111-1111-1111-1111-111111111111',
    'member@devcorp.com',
    'Team Member',
    'member'
);

-- 3. Create Integrations (MCP Tools)
INSERT INTO org_integrations (id, organization_id, provider, name, config, is_active) VALUES 
-- Calculator Tool
(
    '33333333-3333-3333-3333-333333333333',
    '11111111-1111-1111-1111-111111111111',
    'mcp_tool',
    'Math Calculator',
    '{
        "type": "mcp_server",
        "server_url": "http://mcp-math:8080",
        "tools": ["calculate", "solve_equation"],
        "description": "Mathematical calculations and equation solving"
    }',
    TRUE
),
-- Weather Tool
(
    '33333333-3333-3333-3333-333333333334',
    '11111111-1111-1111-1111-111111111111',
    'mcp_tool',
    'Weather API',
    '{
        "type": "mcp_server",
        "server_url": "http://mcp-weather:8080",
        "tools": ["get_weather", "get_forecast"],
        "description": "Current weather and forecasts"
    }',
    TRUE
),
-- Custom Business Tool
(
    '33333333-3333-3333-3333-333333333335',
    '11111111-1111-1111-1111-111111111111',
    'custom',
    'Order Lookup',
    '{
        "type": "custom_api",
        "base_url": "https://api.devcorp.com/orders",
        "auth_type": "bearer",
        "tools": ["get_order", "track_shipment"]
    }',
    FALSE -- Disabled by default
);

-- 4. Create Chatbot
INSERT INTO chatbots (
    id, 
    organization_id, 
    name, 
    whatsapp_phone_number_id, 
    whatsapp_business_account_id,
    whatsapp_access_token, 
    model_name,
    system_prompt,
    persona,
    temperature,
    rag_enabled,
    is_active
) VALUES (
    '22222222-2222-2222-2222-222222222222',
    '11111111-1111-1111-1111-111111111111',
    'MVP Test Bot',
    '${WHATSAPP_PHONE_NUMBER_ID}',
    'test_business_account_123',
    '${WHATSAPP_ACCESS_TOKEN}',
    'gemini-3-flash-preview',
    'You are a helpful customer service assistant for Dev Corp. You can help with calculations, check weather, and answer questions about our products. Always be friendly and professional.',
    'You speak in a warm, professional tone. You use emojis occasionally to be friendly. You are knowledgeable but not overly technical.',
    0.7,
    FALSE, -- RAG disabled for now
    TRUE
);

-- 5. Enable Integrations for this Bot
INSERT INTO chatbot_integrations (chatbot_id, integration_id, is_enabled, settings_override) VALUES 
(
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333333',
    TRUE,
    '{}'
),
(
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333334',
    TRUE,
    '{"default_location": "San Francisco, CA"}'
);

-- 6. Create Sample Contacts
INSERT INTO contacts (id, chatbot_id, phone_number, name, conversation_mode, variables, tags) VALUES 
(
    '44444444-4444-4444-4444-444444444444',
    '22222222-2222-2222-2222-222222222222',
    '15550001234',
    'Alice Test',
    'auto',
    '{"email": "alice@example.com", "preferred_language": "en", "timezone": "America/New_York"}',
    ARRAY['vip', 'test_user']
),
(
    '44444444-4444-4444-4444-444444444445',
    '22222222-2222-2222-2222-222222222222',
    '15550005678',
    'Bob Demo',
    'auto',
    '{"company": "Demo Inc", "role": "CTO"}',
    ARRAY['demo']
);

-- 7. Create Sample Message History
INSERT INTO messages (contact_id, role, content, whatsapp_message_id, created_at) VALUES 
-- Alice's conversation
(
    '44444444-4444-4444-4444-444444444444',
    'user',
    'Hello! Can you help me with something?',
    'wamid.test.alice.001',
    NOW() - INTERVAL '2 days'
),
(
    '44444444-4444-4444-4444-444444444444',
    'assistant',
    'Hello Alice! Of course, I''d be happy to help you. What can I assist you with today? 😊',
    NULL,
    NOW() - INTERVAL '2 days' + INTERVAL '2 seconds'
),
(
    '44444444-4444-4444-4444-444444444444',
    'user',
    'What is 15% of 250?',
    'wamid.test.alice.002',
    NOW() - INTERVAL '1 day'
),
(
    '44444444-4444-4444-4444-444444444444',
    'assistant',
    '15% of 250 is 37.5. Is there anything else you''d like to calculate?',
    NULL,
    NOW() - INTERVAL '1 day' + INTERVAL '3 seconds'
),

-- Bob's conversation
(
    '44444444-4444-4444-4444-444444444445',
    'user',
    'Hey, what''s the weather like?',
    'wamid.test.bob.001',
    NOW() - INTERVAL '6 hours'
),
(
    '44444444-4444-4444-4444-444444444445',
    'assistant',
    'Let me check the weather for you! ⛅ In San Francisco, it''s currently 68°F and partly cloudy. Perfect weather for a walk!',
    NULL,
    NOW() - INTERVAL '6 hours' + INTERVAL '4 seconds'
);

-- 8. Create Webhook Events (for testing idempotency)
INSERT INTO webhook_events (
    whatsapp_message_id,
    phone_number_id,
    chatbot_id,
    status,
    raw_payload,
    received_at,
    processed_at,
    processing_time_ms
) VALUES 
(
    'wamid.test.alice.001',
    '${WHATSAPP_PHONE_NUMBER_ID}',
    '22222222-2222-2222-2222-222222222222',
    'completed',
    '{"object": "whatsapp_business_account", "entry": []}',
    NOW() - INTERVAL '2 days',
    NOW() - INTERVAL '2 days' + INTERVAL '1.5 seconds',
    1500
),
(
    'wamid.test.alice.002',
    '${WHATSAPP_PHONE_NUMBER_ID}',
    '22222222-2222-2222-2222-222222222222',
    'completed',
    '{"object": "whatsapp_business_account", "entry": []}',
    NOW() - INTERVAL '1 day',
    NOW() - INTERVAL '1 day' + INTERVAL '2 seconds',
    2000
),
(
    'wamid.test.bob.001',
    '${WHATSAPP_PHONE_NUMBER_ID}',
    '22222222-2222-2222-2222-222222222222',
    'completed',
    '{"object": "whatsapp_business_account", "entry": []}',
    NOW() - INTERVAL '6 hours',
    NOW() - INTERVAL '6 hours' + INTERVAL '2.5 seconds',
    2500
);

-- 9. Create Usage Logs
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
    created_at,
    date_bucket
) VALUES 
-- Alice's first conversation
(
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '44444444-4444-4444-4444-444444444444',
    1,
    150,
    80,
    230,
    'gemini-3-flash-preview',
    'google',
    0.000230,
    NOW() - INTERVAL '2 days',
    (NOW() - INTERVAL '2 days')::DATE
),
-- Alice's second conversation (with tool use)
(
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '44444444-4444-4444-4444-444444444444',
    1,
    200,
    120,
    320,
    'gemini-3-flash-preview',
    'google',
    0.000320,
    NOW() - INTERVAL '1 day',
    (NOW() - INTERVAL '1 day')::DATE
),
-- Bob's conversation
(
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '44444444-4444-4444-4444-444444444445',
    1,
    180,
    150,
    330,
    'gemini-3-flash-preview',
    'google',
    0.000330,
    NOW() - INTERVAL '6 hours',
    (NOW() - INTERVAL '6 hours')::DATE
);

-- 10. Initialize Usage Summary
INSERT INTO usage_summary (
    organization_id,
    current_period_messages,
    current_period_tokens,
    period_start,
    period_end,
    last_updated_at
) VALUES (
    '11111111-1111-1111-1111-111111111111',
    3, -- Total messages so far
    880, -- Total tokens so far (230 + 320 + 330)
    CURRENT_DATE,
    CURRENT_DATE + INTERVAL '1 month',
    NOW()
);

-- 11. Create a second org for testing multi-tenancy
INSERT INTO organizations (
    id, 
    name, 
    slug, 
    plan_tier,
    message_limit_monthly,
    token_limit_monthly,
    is_active
) VALUES (
    '11111111-1111-1111-1111-111111111112',
    'Test Corp (Free Plan)',
    'test-corp-free',
    'free',
    100, -- Limited messages
    50000, -- Limited tokens
    TRUE
);

-- Add a chatbot for the second org (without real WhatsApp credentials)
INSERT INTO chatbots (
    id, 
    organization_id, 
    name, 
    whatsapp_phone_number_id, 
    whatsapp_access_token, 
    model_name,
    system_prompt,
    is_active
) VALUES (
    '22222222-2222-2222-2222-222222222223',
    '11111111-1111-1111-1111-111111111112',
    'Free Plan Test Bot',
    'test_phone_id_free_plan',
    'test_token_free_plan',
    'gemini-3-flash-preview',
    'You are a basic assistant for Test Corp.',
    FALSE -- Inactive until configured
);

-- Verify seed data
DO $$
DECLARE
    org_count INT;
    chatbot_count INT;
    message_count INT;
BEGIN
    SELECT COUNT(*) INTO org_count FROM organizations;
    SELECT COUNT(*) INTO chatbot_count FROM chatbots;
    SELECT COUNT(*) INTO message_count FROM messages;
    
    RAISE NOTICE '=== SEED DATA SUMMARY ===';
    RAISE NOTICE 'Organizations: %', org_count;
    RAISE NOTICE 'Chatbots: %', chatbot_count;
    RAISE NOTICE 'Messages: %', message_count;
    RAISE NOTICE '========================';
END $$;