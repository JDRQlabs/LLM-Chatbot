-- Drop in reverse dependency order (or just use CASCADE)
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS contacts CASCADE;
DROP TABLE IF EXISTS knowledge_sources CASCADE;
DROP TABLE IF EXISTS chatbot_integrations CASCADE;
DROP TABLE IF EXISTS chatbots CASCADE;
DROP TABLE IF EXISTS org_integrations CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS organizations CASCADE;