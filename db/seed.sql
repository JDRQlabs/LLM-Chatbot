/* 
====================================================================
  SEED DATA
  Run this AFTER schema.sql to populate test data.
====================================================================
*/

-- 1. Create Organization
INSERT INTO organizations (id, name, slug) VALUES 
('11111111-1111-1111-1111-111111111111', 'Dev Corp', 'dev-corp');

-- 2. Create User
INSERT INTO users (id, organization_id, email, full_name, role) VALUES 
('99999999-9999-9999-9999-999999999999', '11111111-1111-1111-1111-111111111111', '${OWNER_EMAIL}', 'Admin User', 'owner');

-- 3. Create an Integration (e.g. A Calculator Tool)
INSERT INTO org_integrations (id, organization_id, provider, name, config) VALUES 
('33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', 'mcp_tool', 'Math Tools', '{"base_url": "http://math-mcp"}');

-- 4. Create Chatbot
-- REPLACE the phone number ID and tokens with your actual ones!
INSERT INTO chatbots (
    id, 
    organization_id, 
    name, 
    whatsapp_phone_number_id, 
    whatsapp_access_token, 
    system_prompt,
    pinecone_namespace
) VALUES 
(
    '22222222-2222-2222-2222-222222222222',
    '11111111-1111-1111-1111-111111111111',
    'MVP Test Bot',
    '${WHATSAPP_PHONE_NUMBER_ID}',     -- <--- FROM .env file
    '${WHATSAPP_ACCESS_TOKEN}',        -- <--- FROM .env file
    'You are a helpful assistant. If you need to calculate something, use the tool.',
    'dev_namespace_01'
);

-- 5. Enable the Integration for this Bot
INSERT INTO chatbot_integrations (chatbot_id, integration_id, is_enabled) VALUES 
('22222222-2222-2222-2222-222222222222', '33333333-3333-3333-3333-333333333333', true);

-- 6. (Optional) Pre-create a Contact 
-- You don't strictly need this (the code handles new users), but good for verifying queries.
/*
INSERT INTO contacts (id, chatbot_id, phone_number, name, conversation_mode) VALUES 
('44444444-4444-4444-4444-444444444444', '22222222-2222-2222-2222-222222222222', '15550001234', 'Alice Test', 'auto');
*/