-- Migration 001: Add leads table for MCP lead capture
-- This table stores potential customers captured by the sales chatbot

CREATE TABLE IF NOT EXISTS leads (
    id BIGSERIAL PRIMARY KEY,
    chatbot_id UUID REFERENCES chatbots(id) ON DELETE SET NULL,

    -- Contact information
    phone VARCHAR(50) NOT NULL,
    name VARCHAR(255),
    email VARCHAR(255),
    company VARCHAR(255),

    -- Sales information
    estimated_messages INTEGER,
    notes TEXT,

    -- Tracking
    contact_count INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes for performance
    CONSTRAINT leads_phone_check CHECK (phone IS NOT NULL AND phone != '')
);

-- Index for fast lookup by phone
CREATE INDEX idx_leads_phone ON leads(phone);

-- Index for filtering by chatbot
CREATE INDEX idx_leads_chatbot_id ON leads(chatbot_id);

-- Index for sorting by creation date
CREATE INDEX idx_leads_created_at ON leads(created_at DESC);

-- Comment on table
COMMENT ON TABLE leads IS 'Stores potential customers captured through chatbot interactions';
COMMENT ON COLUMN leads.contact_count IS 'Number of times this lead has interacted with the chatbot';
COMMENT ON COLUMN leads.estimated_messages IS 'Estimated monthly message volume provided by the lead';
