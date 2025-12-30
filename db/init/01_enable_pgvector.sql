-- Enable pgvector extension for vector similarity search
-- This script runs automatically when the database container is first created

\c business_logic_app;

-- Create pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Display pgvector version
SELECT vector_version();

-- Note: HNSW indexes will be created automatically by create.sql
-- when the document_chunks table is created with the embedding column
