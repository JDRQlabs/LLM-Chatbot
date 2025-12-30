-- Migration: Add tool execution tracking tables
-- Purpose: Track agent tool calls for debugging, billing, and analytics
-- Date: 2025-12-29

-- =====================================================================
-- Tool Executions Table
-- =====================================================================
-- Tracks every tool call made by the agent during message processing

CREATE TABLE IF NOT EXISTS tool_executions (
    id BIGSERIAL PRIMARY KEY,

    -- Linkage
    message_id BIGINT REFERENCES messages(id) ON DELETE CASCADE,
    chatbot_id UUID NOT NULL REFERENCES chatbots(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Tool identification
    tool_name VARCHAR(100) NOT NULL,
    tool_type VARCHAR(20) NOT NULL CHECK (tool_type IN ('mcp', 'windmill', 'builtin')),
    integration_id UUID REFERENCES org_integrations(id) ON DELETE SET NULL,

    -- Execution details
    arguments JSONB NOT NULL DEFAULT '{}',
    result JSONB,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'success', 'failed', 'timeout')),
    error_message TEXT,

    -- Performance tracking
    execution_time_ms INT,
    iteration INT DEFAULT 1, -- Which agent loop iteration this was

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX idx_tool_executions_message ON tool_executions(message_id);
CREATE INDEX idx_tool_executions_chatbot ON tool_executions(chatbot_id);
CREATE INDEX idx_tool_executions_org ON tool_executions(organization_id);
CREATE INDEX idx_tool_executions_integration ON tool_executions(integration_id);
CREATE INDEX idx_tool_executions_created_at ON tool_executions(created_at DESC);
CREATE INDEX idx_tool_executions_status ON tool_executions(status) WHERE status != 'success';

-- Composite index for analytics queries
CREATE INDEX idx_tool_executions_analytics ON tool_executions(
    organization_id,
    tool_name,
    status,
    created_at DESC
);

-- =====================================================================
-- Trigger: Auto-update completed_at on status change
-- =====================================================================

CREATE OR REPLACE FUNCTION update_tool_execution_completed_at()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IN ('success', 'failed', 'timeout') AND OLD.status = 'pending' THEN
        NEW.completed_at = NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_tool_execution_completed_at
BEFORE UPDATE ON tool_executions
FOR EACH ROW
EXECUTE FUNCTION update_tool_execution_completed_at();

-- =====================================================================
-- System Alerts Table (if not exists)
-- =====================================================================
-- Used for quota alerts, tool failures, etc.

CREATE TABLE IF NOT EXISTS system_alerts (
    id BIGSERIAL PRIMARY KEY,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    chatbot_id UUID REFERENCES chatbots(id) ON DELETE CASCADE,

    type VARCHAR(50) NOT NULL CHECK (type IN (
        'QUOTA_EXCEEDED',
        'TOOL_FAILURE',
        'RAG_FAILURE',
        'WEBHOOK_FAILURE',
        'SECURITY_WARNING',
        'OTHER'
    )),

    severity VARCHAR(20) DEFAULT 'warning' CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    message TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',

    -- Alert state
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_system_alerts_org ON system_alerts(organization_id);
CREATE INDEX idx_system_alerts_chatbot ON system_alerts(chatbot_id);
CREATE INDEX idx_system_alerts_type ON system_alerts(type);
CREATE INDEX idx_system_alerts_unacknowledged ON system_alerts(acknowledged) WHERE acknowledged = FALSE;
CREATE INDEX idx_system_alerts_created_at ON system_alerts(created_at DESC);

-- =====================================================================
-- Helpful Views
-- =====================================================================

-- View: Tool usage statistics per organization
CREATE OR REPLACE VIEW tool_usage_stats AS
SELECT
    organization_id,
    tool_name,
    tool_type,
    COUNT(*) as total_executions,
    COUNT(*) FILTER (WHERE status = 'success') as successful_executions,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_executions,
    COUNT(*) FILTER (WHERE status = 'timeout') as timeout_executions,
    AVG(execution_time_ms) FILTER (WHERE execution_time_ms IS NOT NULL) as avg_execution_time_ms,
    MAX(created_at) as last_used
FROM tool_executions
GROUP BY organization_id, tool_name, tool_type;

-- View: Recent tool failures for monitoring
CREATE OR REPLACE VIEW recent_tool_failures AS
SELECT
    te.id,
    te.organization_id,
    o.name as organization_name,
    te.chatbot_id,
    c.name as chatbot_name,
    te.tool_name,
    te.tool_type,
    te.error_message,
    te.execution_time_ms,
    te.created_at
FROM tool_executions te
JOIN organizations o ON te.organization_id = o.id
JOIN chatbots c ON te.chatbot_id = c.id
WHERE te.status IN ('failed', 'timeout')
  AND te.created_at > NOW() - INTERVAL '24 hours'
ORDER BY te.created_at DESC;

-- =====================================================================
-- Comments
-- =====================================================================

COMMENT ON TABLE tool_executions IS 'Tracks all agent tool executions for debugging, analytics, and billing';
COMMENT ON COLUMN tool_executions.iteration IS 'Which iteration of the agent loop this tool was called in (1-5)';
COMMENT ON COLUMN tool_executions.execution_time_ms IS 'Time taken to execute the tool in milliseconds';

COMMENT ON TABLE system_alerts IS 'System-generated alerts for quota limits, failures, security warnings';

COMMENT ON VIEW tool_usage_stats IS 'Aggregated tool usage statistics per organization';
COMMENT ON VIEW recent_tool_failures IS 'Recent tool execution failures for monitoring dashboard';
