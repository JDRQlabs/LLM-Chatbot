/*
====================================================================
  SEED DATA v2.1 (Production-Ready)
  Run this AFTER create.sql to populate essential data.

  Note: ${VARIABLES} are replaced by manage_db.sh or Makefile from .env file

  Required .env variables:
    - OWNER_EMAIL
    - WHATSAPP_PHONE_NUMBER_ID
    - WHATSAPP_ACCESS_TOKEN
    - SLACK_WEBHOOK_URL (optional)
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
    'pro',
    1000,
    1000000,
    CURRENT_DATE,
    CURRENT_DATE + INTERVAL '1 month',
    'slack',
    '${SLACK_WEBHOOK_URL}',
    '${OWNER_EMAIL}',
    50,
    20,
    100,
    500,
    TRUE
);

-- 2. Create Admin User
INSERT INTO users (id, organization_id, email, full_name, role) VALUES
(
    '99999999-9999-9999-9999-999999999999',
    '11111111-1111-1111-1111-111111111111',
    '${OWNER_EMAIL}',
    'Admin User',
    'owner'
);

-- 3. Create MCP Tool Integrations
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
                "name": {"type": "string", "description": "Nombre del cliente"},
                "phone": {"type": "string", "description": "Teléfono del cliente"},
                "email": {"type": "string", "description": "Email del cliente (opcional)"},
                "company": {"type": "string", "description": "Nombre de la empresa (opcional)"},
                "estimated_messages": {"type": "number", "description": "Volumen estimado de mensajes al mes (opcional)"}
            },
            "required": ["name", "phone"]
        }
    }',
    TRUE
),
-- Contact Owner Tool
(
    '33333333-3333-3333-3333-333333333336',
    '11111111-1111-1111-1111-111111111111',
    'mcp',
    'contact_owner',
    '{
        "type": "mcp_server",
        "server_url": "http://mcp_contact_owner:3003",
        "description": "Envía una notificación importante al dueño del chatbot con información relevante del contexto",
        "llm_instructions": "Usa esta herramienta cuando necesites notificar al dueño sobre algo importante: leads de alto valor, problemas urgentes, quejas críticas, oportunidades de negocio, o cualquier situación que requiera atención humana.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Mensaje claro para el dueño explicando la situación"},
                "contact_info": {"type": "object", "description": "Información relevante del cliente/situación", "additionalProperties": true},
                "urgency": {"type": "string", "description": "Nivel de urgencia", "enum": ["low", "medium", "high"]}
            },
            "required": ["message"]
        }
    }',
    TRUE
);

-- 4. Create Main Chatbot
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
    'JD Software Labs Chatbot',
    '${WHATSAPP_PHONE_NUMBER_ID}',
    'JD-labs-WABA-ID',
    '${WHATSAPP_ACCESS_TOKEN}',
    'gemini-3-flash-preview',
    'Eres un representante de ventas y servicio al cliente para JD Software Labs, empresa en Guadalajara, México. Vendes "Chatbot de WhatsApp" - una solución SaaS para automatizar conversaciones por WhatsApp.

PLANES DISPONIBLES:
- Gratis: 100 mensajes/mes
- Básico: $499 MXN/mes (1,000 mensajes por mes, instrucciones personalizadas) 
- Profesional: $1,499 MXN/mes (5,000 mensajes por mes, acceso a herramientas configurables (ejemplo: notificaciones al dueño, cálculo de precios, etc.)) (MCP)
- Empresarial: $3,999 MXN/mes (25,000 mensajes por mes, instrucciones, herramientas, y base de conocimientos personalizada (PDFs, URLs, etc.)) (MCP + RAG)
- Contáctanos para planes a medida y volúmenes mayores.

IMPORTANTE:
- Responde en español (a menos que el usuario te contacte en inglés!), sé breve y directo
- Mantén tono profesional pero amigable
- Tu objetivo es convertir al cliente en un cliente potencial
- Siempre expresa la cantidad de mensajes en mensajes por mes
- Tus respuestas serán enviadas por whatsapp, por lo que no uses emojis ni caracteres especiales que no sean compatibles con whatsapp.
- Puedes usar las siguientes opciones para dar formato:
    - Cursiva: Para escribir texto en cursiva, coloca un guión bajo antes y después del texto:
    _texto_
    - Negrita: Para escribir texto en negrita, coloca un asterisco antes y después del texto:
    *texto*
    - Tachado: Para escribir texto tachado, coloca una virgulilla antes y después del texto:
    ~texto~
    - Monoespaciado: Para escribir texto en monoespaciado, coloca tres comillas invertidas simples antes y después del texto:
    ```texto```
    - Lista con viñetas: Para añadir una lista con viñetas a tu mensaje, coloca un asterisco o un guion y un espacio antes de cada palabra u oración:
    * texto
    * texto
    - Lista numerada: Para añadir una lista numerada a tu mensaje, coloca un número, un punto y un espacio antes de cada línea de texto:
    1. texto
2. texto',
    'Hablas con tono cálido y profesional. Usas emojis ocasionalmente. Intenta ser conciso y en un inicio no uses terminología técnica o complicada a menos que el usuario demuestre interés en detalles técnicos.
    Trata de mantener las respuestas cortas y directas, con un máximo de 2 parrafos cortos.',
    0.7,
    TRUE,
    TRUE
);

-- 5. Enable Integrations for the Chatbot
INSERT INTO chatbot_integrations (chatbot_id, integration_id, is_enabled, settings_override) VALUES
('22222222-2222-2222-2222-222222222222', '33333333-3333-3333-3333-333333333333', TRUE, '{}'),
('22222222-2222-2222-2222-222222222222', '33333333-3333-3333-3333-333333333334', TRUE, '{}'),
('22222222-2222-2222-2222-222222222222', '33333333-3333-3333-3333-333333333336', TRUE, '{}');

-- 6. Initialize Usage Summary
INSERT INTO usage_summary (
    organization_id,
    current_period_messages,
    current_period_tokens,
    period_start,
    period_end,
    last_updated_at
) VALUES (
    '11111111-1111-1111-1111-111111111111',
    0,
    0,
    CURRENT_DATE,
    CURRENT_DATE + INTERVAL '1 month',
    NOW()
);

-- Verify seed data
DO $$
DECLARE
    org_count INT;
    chatbot_count INT;
    user_count INT;
BEGIN
    SELECT COUNT(*) INTO org_count FROM organizations;
    SELECT COUNT(*) INTO chatbot_count FROM chatbots;
    SELECT COUNT(*) INTO user_count FROM users;

    RAISE NOTICE '=== SEED DATA SUMMARY ===';
    RAISE NOTICE 'Organizations: %', org_count;
    RAISE NOTICE 'Chatbots: %', chatbot_count;
    RAISE NOTICE 'Users: %', user_count;
    RAISE NOTICE '========================';
END $$;
