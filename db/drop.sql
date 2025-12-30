/* 
====================================================================
  DROP ALL TABLES - CLEAN SLATE
  Run this to completely reset the database
====================================================================
*/

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS usage_summary CASCADE;
DROP TABLE IF EXISTS usage_logs CASCADE;
DROP TABLE IF EXISTS tool_executions CASCADE;
DROP TABLE IF EXISTS system_alerts CASCADE;
DROP TABLE IF EXISTS leads CASCADE;
DROP TABLE IF EXISTS webhook_events CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS contacts CASCADE;
DROP TABLE IF EXISTS document_chunks CASCADE;
DROP TABLE IF EXISTS knowledge_sources CASCADE;
DROP TABLE IF EXISTS daily_ingestion_counts CASCADE;
DROP TABLE IF EXISTS chatbot_integrations CASCADE;
DROP TABLE IF EXISTS chatbots CASCADE;
DROP TABLE IF EXISTS org_integrations CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS organizations CASCADE;

-- Drop functions
DROP FUNCTION IF EXISTS increment_knowledge_counters();
DROP FUNCTION IF EXISTS get_current_usage(UUID);
DROP FUNCTION IF EXISTS cleanup_old_webhook_events();
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Drop extensions (optional - comment out if shared database)
-- DROP EXTENSION IF EXISTS "pgcrypto";