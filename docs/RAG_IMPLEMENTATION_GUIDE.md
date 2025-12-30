# RAG Implementation Guide: pgvector Edition

## Executive Summary

**Recommendation: Use pgvector for long-term success**

### Why pgvector > Pinecone for Your SaaS

| Factor | pgvector | Pinecone |
|--------|----------|----------|
| **Cost at Scale** | ✅ $0 marginal cost | ❌ $70-200/month per index |
| **Multi-tenancy** | ✅ Natural with SQL | ⚠️ Complex namespace management |
| **Data Locality** | ✅ Everything in one DB | ❌ External service |
| **Setup Complexity** | ✅ Simple extension | ⚠️ Additional service |
| **Performance (< 1M vectors)** | ✅ < 100ms | ✅ < 50ms |
| **Vendor Lock-in** | ✅ Open source | ❌ Proprietary |
| **Maintenance** | ✅ Same as your DB | ⚠️ Another service to monitor |

### When to Use Each

**pgvector (Recommended):**
- ✅ Multi-tenant SaaS (your use case)
- ✅ Cost-sensitive business model
- ✅ < 1M vectors per tenant
- ✅ Want single database to manage

**Pinecone (Consider If):**
- ⚠️ > 5M vectors per tenant
- ⚠️ Need sub-10ms latency
- ⚠️ Don't want to manage infrastructure
- ⚠️ Budget for $500+/month in vector DB costs

## Architecture Overview

```
Document Upload Flow:
User uploads PDF/URL
    ↓
Windmill Job: Process Document
    ├─ Extract text (PyPDF2/trafilatura)
    ├─ Chunk text (1000 chars, 200 overlap)
    ├─ Generate embeddings (OpenAI ada-002)
    └─ Store in pgvector (document_chunks table)

Query Flow:
User sends message
    ↓
Step 1: Context Loading
    ↓
Step 2: LLM Processing
    ├─ Generate query embedding
    ├─ Search pgvector (top 5 similar chunks)
    ├─ Build prompt with context
    └─ Call LLM with enriched prompt
    ↓
Step 3: Send response
```

## Installation Steps

### 1. Install pgvector Extension

```bash
# In your PostgreSQL container
docker exec -it business_logic_db bash

# Inside container
apt-get update
apt-get install -y postgresql-16-pgvector

# Exit container
exit

# Or rebuild with pgvector in Dockerfile
```

**Alternative: Use postgres image with pgvector**
```yaml
# In docker-compose.yml
business_logic_db:
  image: pgvector/pgvector:pg16  # Instead of postgres:16
  # ... rest of config
```

### 2. Update Database Schema

```bash
cd db

# Add pgvector schema additions to create.sql
# (Already provided in artifacts above)

# Reset database
./manage_db.sh reset

# Verify pgvector is installed
docker exec business_logic_db psql -U business_logic_user -d business_logic_app -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

### 3. Install Python Dependencies

```bash
# Add to your requirements.txt or install directly
pip install pgvector psycopg2-binary

# For document processing
pip install PyPDF2        # PDF extraction
pip install trafilatura   # Web scraping
pip install python-docx   # Word docs
pip install openai        # Embeddings
```

### 4. Add Document Processing Script to Windmill

Create new script `f/development/4_process_documents.py` (already provided above)

### 5. Update Step 2 with RAG

Replace your existing `2_whatsapp_llm_processing.py` with the RAG-enabled version (provided above)

## Document Processing Workflow

### Upload API Endpoint (to be created)

```python
# f/development/upload_document.py
def main(
    chatbot_id: str,
    file_upload: str,  # Base64 encoded file or URL
    source_type: str,  # "pdf", "url", "text"
    name: str,
    db_resource: str = "f/development/business_layer_db_postgreSQL"
):
    """
    Handle document upload.
    
    Steps:
    1. Validate user owns this chatbot
    2. Save file to storage
    3. Create knowledge_source record
    4. Trigger async processing job
    """
    # ... validation logic
    
    # Create knowledge source
    source_id = create_knowledge_source(chatbot_id, name, source_type, file_path)
    
    # Trigger async processing
    trigger_document_processing(source_id, chatbot_id)
    
    return {"success": True, "source_id": source_id}
```

### Processing Job

Triggered automatically after upload:

```python
# This runs in background
result = process_document(
    knowledge_source_id=source_id,
    chatbot_id=chatbot_id,
    chunk_size=1000,
    chunk_overlap=200
)

# Updates knowledge_sources.sync_status to:
# - "processing" (in progress)
# - "synced" (success)
# - "failed" (error)
```

## Configuration Options

### Chunking Strategy

```python
# Conservative (better context, more chunks)
chunk_size = 500
chunk_overlap = 100

# Balanced (recommended)
chunk_size = 1000
chunk_overlap = 200

# Aggressive (fewer chunks, may lose context)
chunk_size = 2000
chunk_overlap = 300
```

### Embedding Models

```python
# OpenAI (recommended for quality)
model = "text-embedding-ada-002"
dimensions = 1536
cost_per_1k_tokens = $0.0001

# OpenAI (cheaper, slightly lower quality)
model = "text-embedding-3-small"
dimensions = 1536
cost_per_1k_tokens = $0.00002

# OpenAI (best quality, pricier)
model = "text-embedding-3-large"
dimensions = 3072
cost_per_1k_tokens = $0.00013
```

**Important**: If you change embedding dimensions, update:
```sql
-- In create.sql
CREATE TABLE document_chunks (
    embedding vector(3072),  -- Update this
    ...
);

-- And the search function
CREATE OR REPLACE FUNCTION search_knowledge_base(
    p_query_embedding vector(3072),  -- Update this
    ...
)
```

### Retrieval Settings

```python
# In Step 2 (LLM Processing)

# Conservative (most relevant only)
top_k = 3
similarity_threshold = 0.8

# Balanced (recommended)
top_k = 5
similarity_threshold = 0.7

# Aggressive (more context, may include noise)
top_k = 10
similarity_threshold = 0.6
```

## Performance Optimization

### Index Types

**HNSW (Recommended):**
```sql
CREATE INDEX idx_document_chunks_embedding_hnsw 
ON document_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```
- **Pros**: Fast queries (10-50ms), good recall
- **Cons**: Higher memory usage, slower inserts
- **Use when**: < 10M vectors

**IVFFlat (Alternative):**
```sql
CREATE INDEX idx_document_chunks_embedding_ivfflat 
ON document_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```
- **Pros**: Lower memory, faster inserts
- **Cons**: Slower queries, needs VACUUM ANALYZE
- **Use when**: Memory constrained

### Query Optimization

```sql
-- Add partial index for active chatbots only
CREATE INDEX idx_active_chunks 
ON document_chunks(chatbot_id, embedding)
WHERE embedding IS NOT NULL;

-- Create materialized view for frequently accessed stats
CREATE MATERIALIZED VIEW chatbot_knowledge_stats AS
SELECT 
    chatbot_id,
    COUNT(*) as total_chunks,
    COUNT(DISTINCT knowledge_source_id) as total_sources,
    MAX(created_at) as last_updated
FROM document_chunks
GROUP BY chatbot_id;

-- Refresh periodically
REFRESH MATERIALIZED VIEW chatbot_knowledge_stats;
```

### Monitoring Queries

```sql
-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read
FROM pg_stat_user_indexes
WHERE tablename = 'document_chunks';

-- Check slow queries
SELECT 
    query,
    calls,
    mean_exec_time,
    max_exec_time
FROM pg_stat_statements
WHERE query LIKE '%document_chunks%'
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check table size
SELECT 
    pg_size_pretty(pg_total_relation_size('document_chunks')) as total_size,
    pg_size_pretty(pg_relation_size('document_chunks')) as table_size,
    pg_size_pretty(pg_indexes_size('document_chunks')) as indexes_size;
```

## Cost Analysis

### pgvector Costs

**Storage:**
- Vector: 1536 dimensions × 4 bytes = 6KB per vector
- Text: ~1KB average per chunk
- Total: ~7KB per chunk

**Example: 1000 tenants, 100 documents each**
- Documents: 100,000 total
- Chunks: 100,000 × 10 = 1,000,000 chunks
- Storage: 1M × 7KB = 7GB
- **Cost: ~$0-10/month** (part of your existing PostgreSQL)

**Processing:**
- Embeddings: 1M chunks × $0.0001/1K tokens = $100 one-time
- Ongoing: Only new documents

### Pinecone Costs (Comparison)

**For same workload:**
- 1M vectors in Pinecone
- Need: p1.x1 pod (~$70/month) or p2.x1 pod (~$200/month)
- Plus: API usage fees
- **Cost: $70-200/month recurring**

### Break-even Analysis

```
Year 1:
pgvector: $100 (embeddings) + $120 (storage) = $220
Pinecone: $840-2400

Savings: $620-2180 in first year
```

## Testing Your RAG Implementation

### Unit Test: Document Processing

```python
def test_document_processing(db_with_data, mock_wmill):
    """Test document chunking and embedding."""
    
    # Create test knowledge source
    source_id = create_test_source(db_with_data)
    
    # Process it
    result = process_document(
        knowledge_source_id=source_id,
        chatbot_id="test-bot-id",
        openai_api_key="test-key"
    )
    
    # Verify chunks created
    assert result["success"] is True
    assert result["chunks_created"] > 0
    
    # Check database
    chunks = get_chunks_for_source(db_with_data, source_id)
    assert len(chunks) == result["chunks_created"]
    assert chunks[0]["embedding"] is not None
```

### Integration Test: RAG Retrieval

```python
def test_rag_retrieval(db_with_data, mock_llm):
    """Test end-to-end RAG flow."""
    
    # Setup: Create document with known content
    create_test_document(
        db_with_data,
        content="The capital of France is Paris."
    )
    
    # Query
    result = step2.main(
        context_payload={...},
        user_message="What is the capital of France?"
    )
    
    # Verify RAG was used
    assert result["usage_info"]["rag_used"] is True
    assert result["usage_info"]["chunks_retrieved"] > 0
    assert "Paris" in result["reply_text"]
```

### Manual Testing

```bash
# 1. Upload a test document
curl -X POST http://localhost:8081/api/w/development/jobs/run/f/development/upload_document \
  -H "Authorization: Bearer $WINDMILL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "chatbot_id": "your-bot-id",
    "source_type": "text",
    "name": "Test Document",
    "content": "This is test content about machine learning."
  }'

# 2. Wait for processing (check logs)
docker-compose logs -f windmill_worker

# 3. Query the chatbot
curl -X POST http://localhost:3000/ \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{
      "from": "test-user",
      "text": {"body": "Tell me about machine learning"}
    }]
  }'

# 4. Check if RAG was used (check Step 2 logs)
```

## Common Issues & Solutions

### Issue: Embeddings Not Generating

**Symptoms:**
- `document_chunks.embedding` is NULL
- Search returns no results

**Check:**
```sql
SELECT COUNT(*) as total, 
       COUNT(embedding) as with_embeddings 
FROM document_chunks 
WHERE chatbot_id = 'your-bot-id';
```

**Solutions:**
1. Check OpenAI API key is set
2. Check rate limits (OpenAI: 3,000 RPM for tier 1)
3. Check error logs: `SELECT error_message FROM knowledge_sources WHERE sync_status = 'failed'`

### Issue: Slow Queries

**Symptoms:**
- RAG retrieval takes > 500ms
- Database CPU high

**Check:**
```sql
EXPLAIN ANALYZE
SELECT * FROM search_knowledge_base(
    'chatbot-id',
    '[0.1, 0.2, ...]',  -- Sample embedding
    5,
    0.7
);
```

**Solutions:**
1. Ensure HNSW index exists: `\d document_chunks`
2. Run VACUUM ANALYZE: `VACUUM ANALYZE document_chunks;`
3. Increase shared_buffers in postgresql.conf
4. Consider reducing `top_k` or increasing `similarity_threshold`

### Issue: Low Quality Results

**Symptoms:**
- Retrieved chunks not relevant
- LLM response doesn't use context

**Check:**
```sql
-- See what's actually being retrieved
SELECT 
    content,
    1 - (embedding <=> query_embedding) as similarity
FROM document_chunks
WHERE chatbot_id = 'your-bot-id'
ORDER BY embedding <=> query_embedding
LIMIT 5;
```

**Solutions:**
1. Lower `similarity_threshold` (try 0.6)
2. Increase `top_k` (try 7-10)
3. Improve chunking (smaller chunks = more precise)
4. Add more context in system prompt about how to use retrieved information

### Issue: Out of Memory

**Symptoms:**
- PostgreSQL OOM kills
- Slow index builds

**Check:**
```sql
SELECT 
    pg_size_pretty(pg_total_relation_size('document_chunks')),
    COUNT(*) 
FROM document_chunks;
```

**Solutions:**
1. Switch from HNSW to IVFFlat (less memory)
2. Increase PostgreSQL memory settings
3. Archive old/unused documents
4. Use read replica for search queries


**Questions?** Check the test files in `tests/unit/` for examples of how to test RAG functionality.