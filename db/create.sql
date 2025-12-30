/* 
====================================================================
  REFINED MVP SCHEMA v2.0
  Database: PostgreSQL
  
  Key Features:
  - Idempotency via webhook_events table
  - Usage tracking and limits
  - Proper indexes for performance
  - Multi-tenant SaaS structure
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
    plan_tier VARCHAR(20) DEFAULT 'free', -- free, starter, pro, enterprise
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Usage Limits (per billing period)
    message_limit_monthly INT DEFAULT 100, -- Messages per month
    token_limit_monthly BIGINT DEFAULT 100000, -- Tokens per month
    billing_period_start DATE DEFAULT CURRENT_DATE, -- When current period started
    billing_period_end DATE DEFAULT (CURRENT_DATE + INTERVAL '1 month'), -- When it ends

    -- Notification Settings (for contact_owner MCP)
    notification_method VARCHAR(20) DEFAULT 'disabled', -- 'disabled', 'slack', 'email', 'whatsapp'
    slack_webhook_url TEXT, -- Slack webhook URL for notifications
    notification_email VARCHAR(255), -- Email address for notifications

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. USERS (Dashboard Access)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255), 
    full_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'member', -- owner, admin, member
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_users_org ON users(organization_id);
CREATE INDEX idx_users_email ON users(email);

-- 3. ORG INTEGRATIONS (The "Vault" for Credentials)
CREATE TABLE org_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    
    provider VARCHAR(50) NOT NULL, -- 'mcp', 'hubspot', 'slack', 'custom'
    name VARCHAR(100),
    
    -- Encrypted credentials go here
    credentials JSONB DEFAULT '{}',
    config JSONB DEFAULT '{}',
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_org_integrations_org ON org_integrations(organization_id);
CREATE INDEX idx_org_integrations_provider ON org_integrations(organization_id, provider);

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
    temperature DECIMAL(3,2) DEFAULT 0.7,
    
    -- RAG Config
    rag_enabled BOOLEAN DEFAULT FALSE,

    -- Fallback Messages (Customizable per chatbot)
    fallback_message_error TEXT DEFAULT 'Lo siento, estoy teniendo problemas técnicos. Por favor intenta de nuevo más tarde.',
    fallback_message_limit TEXT DEFAULT 'Lo siento, he alcanzado mi límite de uso. El administrador ha sido notificado.',

    -- Toggles & UI Settings
    is_active BOOLEAN DEFAULT TRUE,
    settings JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_chatbots_org ON chatbots(organization_id);
CREATE INDEX idx_chatbots_wa_phone ON chatbots(whatsapp_phone_number_id);
CREATE INDEX idx_chatbots_active ON chatbots(organization_id, is_active);

-- 5. CHATBOT INTEGRATIONS (The "Switch")
CREATE TABLE chatbot_integrations (
    chatbot_id UUID REFERENCES chatbots(id) ON DELETE CASCADE,
    integration_id UUID REFERENCES org_integrations(id) ON DELETE CASCADE,
    
    is_enabled BOOLEAN DEFAULT TRUE,
    settings_override JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (chatbot_id, integration_id)
);

CREATE INDEX idx_chatbot_integrations_enabled ON chatbot_integrations(chatbot_id, is_enabled);

-- 6. KNOWLEDGE SOURCES (Uploaded Files)
CREATE TABLE knowledge_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chatbot_id UUID REFERENCES chatbots(id) ON DELETE CASCADE,
    
    source_type VARCHAR(20) NOT NULL, -- pdf, url, text, doc
    name VARCHAR(255),
    
    file_path TEXT, 
    content_hash VARCHAR(64),
    file_size_bytes BIGINT,
    
    sync_status VARCHAR(20) DEFAULT 'pending', -- pending, processing, synced, failed
    last_synced_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_knowledge_sources_chatbot ON knowledge_sources(chatbot_id);
CREATE INDEX idx_knowledge_sources_status ON knowledge_sources(chatbot_id, sync_status);

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
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(chatbot_id, phone_number)
);

CREATE INDEX idx_contacts_chatbot ON contacts(chatbot_id);
CREATE INDEX idx_contacts_phone ON contacts(chatbot_id, phone_number);
CREATE INDEX idx_contacts_last_message ON contacts(chatbot_id, last_message_at DESC);

-- 8. MESSAGES (Chat History)
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
    
    role VARCHAR(20) NOT NULL, -- user, assistant, system, tool
    content TEXT,
    
    -- Idempotency & Tracking
    whatsapp_message_id VARCHAR(255), -- From Meta, nullable for assistant messages
    
    -- Tool Usage
    tool_calls JSONB, -- Stores raw tool call data if used
    tool_results JSONB, -- Stores tool execution results
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_messages_contact_date ON messages(contact_id, created_at DESC);
CREATE INDEX idx_messages_wa_id ON messages(whatsapp_message_id) WHERE whatsapp_message_id IS NOT NULL;
CREATE INDEX idx_messages_role ON messages(contact_id, role);

-- 9. WEBHOOK EVENTS (Idempotency & Deduplication)
CREATE TABLE webhook_events (
    id BIGSERIAL PRIMARY KEY,
    
    -- Identification
    whatsapp_message_id VARCHAR(255) UNIQUE NOT NULL,
    phone_number_id VARCHAR(50) NOT NULL,
    chatbot_id UUID REFERENCES chatbots(id) ON DELETE SET NULL,
    
    -- Processing Status
    status VARCHAR(20) DEFAULT 'received', -- received, processing, completed, failed, duplicate
    
    -- Payload & Response
    raw_payload JSONB, -- Store original webhook payload for debugging
    error_message TEXT,
    
    -- Timestamps
    received_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '7 days',
    
    -- Metadata
    processing_time_ms INT, -- How long it took to process
    retry_count INT DEFAULT 0
);

CREATE INDEX idx_webhook_events_lookup ON webhook_events(whatsapp_message_id, status);
CREATE INDEX idx_webhook_events_chatbot ON webhook_events(chatbot_id, status);
CREATE INDEX idx_webhook_events_expiry ON webhook_events(expires_at) WHERE status IN ('completed', 'failed');

-- 10. USAGE LOGS (Token & Message Tracking)
CREATE TABLE usage_logs (
    id BIGSERIAL PRIMARY KEY,
    
    -- Relationships
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    chatbot_id UUID REFERENCES chatbots(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    message_id BIGINT REFERENCES messages(id) ON DELETE SET NULL,
    webhook_event_id BIGINT REFERENCES webhook_events(id) ON DELETE SET NULL,
    
    -- Usage Metrics
    message_count INT DEFAULT 1,
    tokens_input INT DEFAULT 0,
    tokens_output INT DEFAULT 0,
    tokens_total INT DEFAULT 0,
    
    -- Provider Info
    model_name VARCHAR(50),
    provider VARCHAR(50), -- 'openai', 'google', 'anthropic'
    
    -- Cost Tracking
    estimated_cost_usd DECIMAL(10, 6),
    
    -- Timestamps & Bucketing
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    date_bucket DATE DEFAULT CURRENT_DATE -- For easy daily aggregation
);}


-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Document chunks table (for RAG)
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationships
    knowledge_source_id UUID REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    chatbot_id UUID REFERENCES chatbots(id) ON DELETE CASCADE,
    
    -- Content
    content TEXT NOT NULL,
    chunk_index INT NOT NULL, -- Which chunk # in the document (0, 1, 2...)
    
    -- Embeddings (using OpenAI's ada-002: 1536 dimensions, or your chosen model)
    embedding vector(1536), -- Change dimension based on your embedding model
    
    -- Metadata (for filtering and display)
    metadata JSONB DEFAULT '{}', -- Store page numbers, headers, etc.
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Composite key to ensure unique chunks per source
    UNIQUE(knowledge_source_id, chunk_index)
);

-- Critical indexes for performance
CREATE INDEX idx_document_chunks_chatbot ON document_chunks(chatbot_id);
CREATE INDEX idx_document_chunks_source ON document_chunks(knowledge_source_id);

-- Vector similarity search index (HNSW is faster than IVFFlat for most cases)
-- HNSW: Better for high-dimensional vectors, faster queries, more memory
CREATE INDEX idx_document_chunks_embedding_hnsw 
ON document_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Alternative: IVFFlat (use if HNSW is too memory-intensive)
-- CREATE INDEX idx_document_chunks_embedding_ivfflat 
-- ON document_chunks 
-- USING ivfflat (embedding vector_cosine_ops)
-- WITH (lists = 100);

-- Partial index for fast tenant-specific searches
CREATE INDEX idx_document_chunks_chatbot_embedding 
ON document_chunks(chatbot_id) 
WHERE embedding IS NOT NULL;

-- Update knowledge_sources table to track embedding status
ALTER TABLE knowledge_sources 
ADD COLUMN IF NOT EXISTS chunks_count INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(50) DEFAULT 'text-embedding-ada-002',
ADD COLUMN IF NOT EXISTS embedding_dimensions INT DEFAULT 1536;

-- Function to search similar chunks for a chatbot
CREATE OR REPLACE FUNCTION search_knowledge_base(
    p_chatbot_id UUID,
    p_query_embedding vector(1536),
    p_limit INT DEFAULT 5,
    p_similarity_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    chunk_id UUID,
    content TEXT,
    similarity FLOAT,
    source_name VARCHAR(255),
    source_type VARCHAR(20),
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        dc.id as chunk_id,
        dc.content,
        1 - (dc.embedding <=> p_query_embedding) as similarity,
        ks.name as source_name,
        ks.source_type,
        dc.metadata
    FROM document_chunks dc
    JOIN knowledge_sources ks ON dc.knowledge_source_id = ks.id
    WHERE dc.chatbot_id = p_chatbot_id
      AND dc.embedding IS NOT NULL
      AND (1 - (dc.embedding <=> p_query_embedding)) >= p_similarity_threshold
    ORDER BY dc.embedding <=> p_query_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to get embedding statistics for a chatbot
CREATE OR REPLACE FUNCTION get_embedding_stats(p_chatbot_id UUID)
RETURNS TABLE (
    total_chunks BIGINT,
    total_sources INT,
    avg_chunk_size FLOAT,
    embedding_coverage FLOAT -- % of chunks with embeddings
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(dc.id) as total_chunks,
        COUNT(DISTINCT dc.knowledge_source_id) as total_sources,
        AVG(LENGTH(dc.content)) as avg_chunk_size,
        (COUNT(*) FILTER (WHERE dc.embedding IS NOT NULL)::FLOAT / 
         NULLIF(COUNT(*)::FLOAT, 0) * 100) as embedding_coverage
    FROM document_chunks dc
    WHERE dc.chatbot_id = p_chatbot_id;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update chunks_count when chunks are added/removed
CREATE OR REPLACE FUNCTION update_knowledge_source_chunks_count()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'DELETE') THEN
        UPDATE knowledge_sources 
        SET chunks_count = chunks_count - 1
        WHERE id = OLD.knowledge_source_id;
        RETURN OLD;
    ELSIF (TG_OP = 'INSERT') THEN
        UPDATE knowledge_sources 
        SET chunks_count = chunks_count + 1
        WHERE id = NEW.knowledge_source_id;
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_chunks_count
AFTER INSERT OR DELETE ON document_chunks
FOR EACH ROW
EXECUTE FUNCTION update_knowledge_source_chunks_count();

CREATE INDEX idx_usage_logs_org_date ON usage_logs(organization_id, date_bucket);
CREATE INDEX idx_usage_logs_chatbot_date ON usage_logs(chatbot_id, date_bucket);
CREATE INDEX idx_usage_logs_org_period ON usage_logs(organization_id, created_at) WHERE created_at >= CURRENT_DATE - INTERVAL '31 days';

-- 11. USAGE SUMMARY (Cached Aggregates for Performance)
-- This is a materialized view alternative - stores current billing period usage
CREATE TABLE usage_summary (
    organization_id UUID PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Current Period Usage
    current_period_messages INT DEFAULT 0,
    current_period_tokens BIGINT DEFAULT 0,
    
    -- Billing Period Reference
    period_start DATE,
    period_end DATE,
    
    -- Metadata
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_usage_summary_period ON usage_summary(period_start, period_end);

-- Helper function to get current usage for an org
CREATE OR REPLACE FUNCTION get_current_usage(org_id UUID)
RETURNS TABLE(messages_used INT, tokens_used BIGINT) AS $$
DECLARE
    org_record RECORD;
BEGIN
    -- Get org billing period
    SELECT billing_period_start, billing_period_end 
    INTO org_record
    FROM organizations 
    WHERE id = org_id;
    
    -- Return aggregated usage for current period
    RETURN QUERY
    SELECT 
        COALESCE(SUM(message_count), 0)::INT as messages_used,
        COALESCE(SUM(tokens_total), 0)::BIGINT as tokens_used
    FROM usage_logs
    WHERE organization_id = org_id
      AND created_at >= org_record.billing_period_start
      AND created_at < org_record.billing_period_end;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply the trigger to relevant tables
CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chatbots_updated_at BEFORE UPDATE ON chatbots
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON contacts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create a cleanup job for old webhook events (you'd run this periodically)
-- This is just the function - you'd need to schedule it with pg_cron or external scheduler
CREATE OR REPLACE FUNCTION cleanup_old_webhook_events()
RETURNS INT AS $$
DECLARE
    deleted_count INT;
BEGIN
    DELETE FROM webhook_events
    WHERE expires_at < NOW()
      AND status IN ('completed', 'failed');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;