/* 
====================================================================
  SEED DATA v2.0
  Run this AFTER create.sql to populate test data.
  
  Note: ${VARIABLES} are replaced by manage_db.sh from .env file
====================================================================
*/

-- 1. Create Organization with Usage Limits and Notification Settings
INSERT INTO organizations (
    id,
    name,
    slug,
    plan_tier,
    message_limit_monthly,
    token_limit_monthly,
    billing_period_start,
    billing_period_end,
    notification_method,
    slack_webhook_url,
    notification_email,
    max_knowledge_pdfs,
    max_knowledge_urls,
    max_knowledge_ingestions_per_day,
    max_knowledge_storage_mb,
    is_active
) VALUES (
    '11111111-1111-1111-1111-111111111111',
    'JD Labs Corporation',
    'jd-labs-corp',
    'pro', -- Pro plan
    1000, -- 1000 messages per month
    1000000, -- 1M tokens per month
    CURRENT_DATE,
    CURRENT_DATE + INTERVAL '1 month',
    'slack', -- Enable Slack notifications
    '${SLACK_WEBHOOK_URL}', -- Slack webhook URL from .env
    '${OWNER_EMAIL}', -- Fallback to owner email
    50, -- 50 PDFs for pro plan
    20, -- 20 URLs for pro plan
    100, -- 100 ingestions per day
    500, -- 500 MB storage limit
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
-- Pricing Calculator Tool
(
    '33333333-3333-3333-3333-333333333333',
    '11111111-1111-1111-1111-111111111111',
    'mcp',
    'calculate_pricing',
    '{
        "type": "mcp_server",
        "server_url": "http://mcp_pricing_calculator:3001",
        "description": "Calcula precios del chatbot de WhatsApp según volumen de mensajes y tier",
        "llm_instructions": "Usa esta herramienta cuando el cliente pregunte sobre precios o costos. Necesitas el volumen de mensajes estimado. Si no lo sabes, pregúntale al cliente primero.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_volume": {
                    "type": "number",
                    "description": "Número de mensajes al mes"
                },
                "tier": {
                    "type": "string",
                    "description": "Tier del plan: basic, professional, o enterprise",
                    "enum": ["basic", "professional", "enterprise"]
                }
            },
            "required": ["message_volume"]
        }
    }',
    TRUE
),
-- Lead Capture Tool
(
    '33333333-3333-3333-3333-333333333334',
    '11111111-1111-1111-1111-111111111111',
    'mcp',
    'capture_lead',
    '{
        "type": "mcp_server",
        "server_url": "http://mcp_lead_capture:3002",
        "description": "Guarda información de un cliente potencial interesado en el servicio",
        "llm_instructions": "Usa esta herramienta cuando el cliente muestre interés genuino en contratar el servicio. Asegúrate de tener al menos su nombre y teléfono. Pregunta por la información faltante antes de llamar esta herramienta.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nombre del cliente"
                },
                "phone": {
                    "type": "string",
                    "description": "Teléfono del cliente"
                },
                "email": {
                    "type": "string",
                    "description": "Email del cliente (opcional)"
                },
                "company": {
                    "type": "string",
                    "description": "Nombre de la empresa (opcional)"
                },
                "estimated_messages": {
                    "type": "number",
                    "description": "Volumen estimado de mensajes al mes (opcional)"
                }
            },
            "required": ["name", "phone"]
        }
    }',
    TRUE
),
-- Contact Owner Tool (Purpose-Agnostic Notifications)
(
    '33333333-3333-3333-3333-333333333336',
    '11111111-1111-1111-1111-111111111111',
    'mcp',
    'contact_owner',
    '{
        "type": "mcp_server",
        "server_url": "http://mcp_contact_owner:3003",
        "description": "Envía una notificación importante al dueño del chatbot con información relevante del contexto",
        "llm_instructions": "Usa esta herramienta cuando necesites notificar al dueño sobre algo importante: leads de alto valor, problemas urgentes, quejas críticas, oportunidades de negocio, o cualquier situación que requiera atención humana. Incluye un mensaje claro explicando la situación, y en contact_info añade CUALQUIER información relevante del cliente o situación (nombre, contacto, detalles específicos del caso, etc). Este campo es completamente flexible - incluye lo que sea importante para el contexto.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Mensaje claro para el dueño explicando la situación y por qué requiere atención"
                },
                "contact_info": {
                    "type": "object",
                    "description": "Objeto genérico con CUALQUIER información relevante del cliente/situación. Puede incluir: nombre, teléfono, email, empresa, detalles del problema, presupuesto, timeline, o cualquier otro dato importante para el contexto. Completamente flexible.",
                    "additionalProperties": true
                },
                "urgency": {
                    "type": "string",
                    "description": "Nivel de urgencia: low (informativo), medium (importante), high (urgente/crítico)",
                    "enum": ["low", "medium", "high"]
                }
            },
            "required": ["message"]
        }
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
    'JD-labs-WABA-ID',
    '${WHATSAPP_ACCESS_TOKEN}',
    'gemini-3-flash-preview',
    'Eres un representante de ventas y servicio al cliente para JD Labs, empresa en Guadalajara, México. Vendes "Chatbot de WhatsApp" - una solución SaaS para automatizar conversaciones por WhatsApp.

PLANES DISPONIBLES:
- Gratis: 100 mensajes/mes
- Básico: $499 MXN/mes (1,000 mensajes)
- Profesional: $999 MXN/mes (3,000 mensajes, acceso a bases de datos (PDFs, URLs))
- Empresarial: $2,999 MXN/mes (15,000 mensajes, API personalizada)
- Contáctanos para planes a medida y volúmenes mayores.

IMPORTANTE:
- Responde en español, sé breve y directo
- Mantén tono profesional pero amigable',
    'Hablas con tono cálido y profesional. Usas emojis ocasionalmente. Eres conciso - máximo 2-3 frases por respuesta a menos que lo amerite.',
    0.7,
    TRUE, -- RAG disabled for now
    TRUE
);

-- 5. Enable Integrations for this Bot
INSERT INTO chatbot_integrations (chatbot_id, integration_id, is_enabled, settings_override) VALUES
-- Enable Pricing Calculator
(
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333333',
    TRUE,
    '{}'
),
-- Enable Lead Capture
(
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333334',
    TRUE,
    '{}'
),
-- Enable Contact Owner
(
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333336',
    TRUE,
    '{}'
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