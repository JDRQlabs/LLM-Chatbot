/* 
====================================================================
  FINAL MVP SCHEMA
  Database: PostgreSQL
====================================================================
*/

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. ORGANIZATIONS (The Tenant)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(50) UNIQUE, 
    
    -- Billing & Status
    stripe_customer_id VARCHAR(100),
    plan_tier VARCHAR(20) DEFAULT 'free', 
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. USERS (Dashboard Access)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255), 
    full_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'member', -- owner, admin, member
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. ORG INTEGRATIONS (The "Vault" for Credentials)
CREATE TABLE org_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    
    provider VARCHAR(50) NOT NULL, -- 'mcp', 'hubspot', 'slack'
    name VARCHAR(100),
    
    -- Encrypted credentials go here
    credentials JSONB DEFAULT '{}',
    config JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. CHATBOTS (The Agents)
CREATE TABLE chatbots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    
    -- Meta / WhatsApp Connection (The Routing Key)
    whatsapp_phone_number_id VARCHAR(50) UNIQUE NOT NULL, 
    whatsapp_business_account_id VARCHAR(50),
    whatsapp_access_token TEXT,
    
    -- AI Config
    model_name VARCHAR(50) DEFAULT 'gemini-3-flash-preview',
    system_prompt TEXT DEFAULT 'You are a helpful assistant.',
    persona TEXT DEFAULT '', -- Tone/Style instructions
    
    -- RAG Config
    pinecone_index_name VARCHAR(100),
    pinecone_namespace VARCHAR(100),
    
    -- Toggles & UI Settings
    settings JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_chatbots_wa_phone ON chatbots(whatsapp_phone_number_id);

-- 5. CHATBOT INTEGRATIONS (The "Switch")
CREATE TABLE chatbot_integrations (
    chatbot_id UUID REFERENCES chatbots(id) ON DELETE CASCADE,
    integration_id UUID REFERENCES org_integrations(id) ON DELETE CASCADE,
    
    is_enabled BOOLEAN DEFAULT TRUE,
    settings_override JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (chatbot_id, integration_id)
);

-- 6. KNOWLEDGE SOURCES (Uploaded Files)
CREATE TABLE knowledge_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chatbot_id UUID REFERENCES chatbots(id) ON DELETE CASCADE,
    
    source_type VARCHAR(20) NOT NULL, -- pdf, url, text
    name VARCHAR(255),
    
    file_path TEXT, 
    content_hash VARCHAR(64),
    
    sync_status VARCHAR(20) DEFAULT 'pending', 
    last_synced_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. CONTACTS (End Users)
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chatbot_id UUID REFERENCES chatbots(id) ON DELETE CASCADE,
    
    phone_number VARCHAR(20) NOT NULL,
    name VARCHAR(255),
    
    -- "Human Takeover" State
    conversation_mode VARCHAR(20) DEFAULT 'auto', -- 'auto' or 'manual'
    unread_count INT DEFAULT 0,
    
    -- CRM Data (Email, Tags, Extracted Info)
    variables JSONB DEFAULT '{}',
    tags TEXT[],
    
    last_message_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(chatbot_id, phone_number)
);

-- 8. MESSAGES (Chat History)
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
    
    role VARCHAR(20) NOT NULL, -- user, assistant, system, tool
    content TEXT,
    
    tool_calls JSONB, -- Stores raw tool call data if used
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_messages_contact_date ON messages(contact_id, created_at DESC);