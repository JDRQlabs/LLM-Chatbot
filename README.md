# Multi-Tenant WhatsApp Chatbot Platform

A production-ready, multi-tenant SaaS platform for WhatsApp chatbots with RAG (Retrieval-Augmented Generation), agentic tool calling, and comprehensive monitoring.

## 🎯 Project Overview

This platform enables organizations to create and manage AI-powered WhatsApp chatbots with:
- **RAG Knowledge Base**: Upload PDFs, URLs, documents for context-aware responses
- **Agentic Capabilities**: Tool calling (MCP, Windmill scripts, built-in tools)
- **Multi-Tenancy**: Organizations with multiple admins and chatbots
- **Usage Tracking**: Token and message limits with automatic quota enforcement
- **Production Monitoring**: Slack alerts, database logging, failure handling

## 🏗️ Architecture

### Technology Stack
- **Orchestration**: Windmill (self-hosted, port 8081)
- **Database**: PostgreSQL with pgvector extension
- **Webhook Server**: Node.js Express (port 3000)
- **LLM Providers**: Google Gemini, OpenAI
- **Vector Search**: pgvector with HNSW indexing
- **Storage**: Windmill S3 integration

### Flow Architecture

```
WhatsApp → Node.js Webhook → Windmill Flow → PostgreSQL → LLM → Response
                                     ↓
                          [Step 1: Context Loading]
                                     ↓
                          [Step 2: Agent Loop + RAG]
                                     ↓
                       [Step 3: Parallel Actions]
                        ├─ 3a: Send WhatsApp Reply
                        ├─ 3b: Save Chat History
                        └─ 3c: Log Usage for Billing
```

## 📂 Project Structure

```
src/
├── docker-compose.yml              # Main services (Windmill, Postgres, Nginx)
├── docker-compose.test.yml         # Test database
├── webhook-server/                 # Node.js WhatsApp webhook handler
│   ├── app.js                      # Express server (Meta verification)
│   └── Dockerfile
├── db/
│   ├── create.sql                  # Complete database schema
│   ├── seed.sql                    # Sample data
│   └── migrations/                 # Database migrations
│       ├── 001_add_tool_tables.sql      # Tool execution tracking
│       └── 002_add_usage_triggers.sql   # Quota enforcement
├── f/development/                  # Windmill scripts
│   ├── 1_whatsapp_context_loading.py    # Step 1: Load context
│   ├── 2_whatsapp_llm_processing.py     # Step 2: Agent loop + RAG
│   ├── 3_1_send_reply_to_whatsapp.py    # Step 3a: Send reply
│   ├── 4__save_chat_history.py         # Step 3b: Save history
│   ├── 5__log_usage.py                 # Step 3c: Log usage
│   ├── RAG_process_documents.py         # Document processing
│   ├── upload_document.py               # Document upload flow
│   ├── whatsapp_webhook_processor__flow/
│   │   └── flow.yaml                    # Main flow definition
│   └── utils/
│       └── alert_on_failure.py          # Failure monitoring
├── tests/                          # Comprehensive test suite
│   ├── conftest.py                 # Pytest fixtures
│   ├── test_harness/               # Mock services
│   │   ├── windmill_mock.py
│   │   ├── llm_mock.py
│   │   └── whatsapp_mock.py
│   ├── unit/                       # Unit tests
│   └── integration/                # Integration tests
└── docs/                           # Documentation
    ├── ARCHITECTURE.md             # System design
    ├── QUICK_REFERENCE.md          # Developer guide
    └── RAG_IMPLEMENTATION_GUIDE.md # RAG setup guide
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for webhook server)
- PostgreSQL 16+ with pgvector extension
- OpenAI API key (for embeddings)
- Google Gemini API key (for LLM)
- WhatsApp Business Account & Meta App

### 1. Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Required environment variables: refer to .env.example
```

### 2. Start Services

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f

# Windmill will be available at http://localhost:8081
# Webhook server at http://localhost:3000
```

### 3. Initialize Database (FOR DEVELOPMENT ONLY)

For any database operations in development, use /db/manage_db.sh, refer to this extract from the script:
```bash
    echo "Usage: db/manage_db.sh [OPTIONS] <COMMAND>"
    echo ""
    echo "Options:"
    echo "  --test  - Target the test database (test_business_logic_db)"
    echo "  --dev   - Target the dev database (business_logic_db) [default]"
    echo ""
    echo "Commands:"
    echo "  create  - Create database schema"
    echo "  seed    - Insert seed data (requires WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN in .env for dev DB)"
    echo "  drop    - Drop all tables (with confirmation)"
    echo "  reset   - Drop, create, and seed database (full reset)"
    echo "  verify  - Show all tables, their structure, and sample data"
    echo ""
    echo "Examples:"
    echo "  ./manage_db.sh reset             # Reset dev database"
    echo "  ./manage_db.sh --test reset      # Reset test database"
```

### 4. Configure WhatsApp Webhook

1. In Meta Developer Console, set webhook URL: `https://your-domain.com/webhook`
2. Set verify token (must match `WHATSAPP_VERIFY_TOKEN`)
3. Subscribe to messages webhook

### 5. Test the Flow

```bash
# Send test webhook
curl -X POST http://localhost:3000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "+1234567890",
            "id": "test123",
            "text": {"body": "Hello!"},
            "type": "text"
          }],
          "metadata": {
            "phone_number_id": "your-phone-number-id"
          }
        }
      }]
    }]
  }'
```

## 🔧 Key Features Implementation

### 1. Agent Loop with Tool Calling

Located in `f/development/2_whatsapp_llm_processing.py`

**Features:**
- Max 5 iterations per message
- Support for 3 tool types:
  - **Built-in**: RAG search (search_knowledge_base)
  - **MCP**: External HTTP servers
  - **Windmill**: Internal scripts
- Automatic token tracking across iterations
- Graceful degradation on tool failures

**Usage:**
```python
# Tools are loaded from chatbot_integrations table
# Agent automatically decides when to use tools
# Example: Agent searches knowledge base, then calls custom tool
```

### 2. RAG Document Processing

**Upload Flow** (`f/development/upload_document.py`):
```python
# Upload PDF
result = upload_document(
    chatbot_id="uuid",
    source_type="pdf",
    name="Product Manual",
    file_content="base64_encoded_pdf"
)
# Returns: {"success": True, "source_id": "...", "processing_job_id": "..."}

# Upload URL
result = upload_document(
    chatbot_id="uuid",
    source_type="url",
    name="FAQ Page",
    url="https://example.com/faq"
)
```

**Processing Pipeline** (`RAG_process_documents.py`):
1. Extract content (PDF/URL/DOC)
2. Smart chunking (1000 chars, 200 overlap)
3. Generate embeddings (OpenAI ada-002)
4. Store in pgvector
5. Update status to 'synced'

**Search:**
```python
# Automatic via agent loop
# Or manual via retrieve_knowledge()
chunks = retrieve_knowledge(
    chatbot_id="uuid",
    query="What is your return policy?",
    openai_api_key="sk-...",
    top_k=5,
    similarity_threshold=0.7
)
```

### 3. Usage Quota Enforcement

**Automatic Enforcement:**
- Triggers on `usage_summary` updates
- Checks message and token limits
- Auto-disables chatbots when exceeded
- Sends Slack alerts
- Warning at 80% threshold

**Manual Reset:**
```sql
-- Reset billing period for all organizations
SELECT * FROM reset_billing_period();

-- Check usage for specific org
SELECT
    o.name,
    us.current_period_messages,
    o.message_limit_monthly,
    (us.current_period_messages::float / o.message_limit_monthly) * 100 as usage_percent
FROM organizations o
JOIN usage_summary us ON o.id = us.organization_id
WHERE o.id = 'your-org-id';
```

### 4. Failure Monitoring

**Slack Alerts** (`utils/alert_on_failure.py`):
- Color-coded by severity (critical/error/warning/info)
- Includes: flow ID, step ID, chatbot ID, error message
- Automatic severity detection
- Database logging in `system_alerts`

**Configure in flow.yaml:**
```yaml
failure_module:
  id: failure
  value:
    type: script
    path: f/development/utils/alert_on_failure
    input_transforms:
      error_message:
        type: javascript
        expr: error.message
      step_id:
        type: javascript
        expr: error.step_id
```

## 📊 Database Schema Highlights

### Core Tables
- **organizations**: Tenants with billing info and quotas
- **users**: Dashboard access (owner/admin/member roles)
- **chatbots**: AI agents with WhatsApp phone numbers
- **contacts**: End-users with conversation history
- **messages**: Chat history with tool calls
- **knowledge_sources**: Uploaded documents
- **document_chunks**: pgvector storage (1536 dims)
- **tool_executions**: Agent tool call tracking
- **usage_logs**: Billing data
- **system_alerts**: Monitoring events

### Key Functions
- `search_knowledge_base(chatbot_id, query_embedding, top_k, threshold)`: Vector search
- `get_current_usage(org_id)`: Current billing period usage
- `check_usage_limits()`: Quota enforcement trigger
- `reset_billing_period()`: Monthly billing reset

## 🧪 Testing

### Run Tests
```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Start test database
docker-compose -f docker-compose.test.yml up -d

# Run all tests
pytest tests/

# Run specific test suite
pytest tests/unit/test_step1_context_loading.py -v

# With coverage
pytest --cov=f/development --cov-report=html
```

### Test Structure
- **Unit Tests**: Individual script testing with mocks
- **Integration Tests**: End-to-end flow testing
- **Test Harness**: Mock Windmill, LLM, WhatsApp APIs

## 🛠️ Development

### Adding a New Tool

1. **Create tool in database:**
```sql
INSERT INTO org_integrations (
    organization_id,
    provider,
    name,
    description,
    credentials,
    settings
) VALUES (
    'org-uuid',
    'mcp',
    'hubspot_lookup',
    'Look up contact in HubSpot',
    '{"api_key": "encrypted_key"}',
    '{"mcp_server_url": "https://mcp-hubspot.example.com"}'
);

INSERT INTO chatbot_integrations (
    chatbot_id,
    integration_id,
    enabled,
    tool_config
) VALUES (
    'chatbot-uuid',
    integration_id,
    true,
    '{"parameters": {"type": "object", "properties": {"email": {"type": "string"}}}}'
);
```

2. **Tool is automatically available to agent** - no code changes needed!

### Adding a Document Type

1. **Add extraction function** in `RAG_process_documents.py`:
```python
def extract_new_type(file_path: str) -> str:
    # Your extraction logic
    return extracted_text
```

2. **Update `extract_content()` switch**:
```python
elif source_type == "new_type":
    return extract_new_type(source["file_path"])
```

3. **Update upload flow** to accept new type

## 📝 API Reference

### Windmill Scripts

**1_whatsapp_context_loading.py**
```python
main(
    whatsapp_phone_id: str,    # Meta phone number ID
    user_phone: str,           # User's WhatsApp number
    user_name: str,            # User's display name
    db_resource: str
) -> Dict
```

**2_whatsapp_llm_processing.py**
```python
main(
    context_payload: dict,     # From Step 1
    user_message: str,         # User's message
    openai_api_key: str,
    google_api_key: str,
    default_provider: str,
    db_resource: str
) -> Dict
```

**upload_document.py**
```python
main(
    chatbot_id: str,
    source_type: str,          # "pdf" | "url" | "text" | "doc"
    name: str,                 # Display name
    file_content: str = None,  # Base64 encoded
    url: str = None,           # For URL type
    openai_api_key: str,
    db_resource: str
) -> Dict
```

## 🔐 Security Considerations

### Implemented
- ✅ Webhook signature verification (Node.js server)
- ✅ Database row-level security via foreign keys
- ✅ API key storage in Windmill variables (encrypted)
- ✅ HTTPS for all external API calls
- ✅ SQL injection prevention (parameterized queries)
- ✅ File size limits (10MB)
- ✅ Tool execution timeouts (30s)
- ✅ Quota enforcement to prevent abuse

### Recommended for Production
- [ ] Encrypt credentials in org_integrations table
- [ ] Add rate limiting to webhook endpoint
- [ ] Implement audit logging for sensitive operations
- [ ] Add data retention/deletion policies
- [ ] Enable SSL/TLS for database connections
- [ ] Implement backup and disaster recovery
- [ ] Add WAF for webhook endpoint
- [ ] Implement secret rotation

## 📈 Monitoring & Maintenance

### Daily Tasks
- Check `system_alerts` table for critical alerts
- Monitor Slack channel for failure notifications
- Review `recent_tool_failures` view

### Weekly Tasks
- Analyze `tool_usage_stats` view
- Check database disk usage
- Review slow query logs

### Monthly Tasks
- Run `reset_billing_period()` (or schedule via cron)
- Backup database
- Review and archive old webhook_events (7+ days)
- Update dependencies

### Monitoring Queries

```sql
-- Today's failures
SELECT * FROM system_alerts
WHERE severity IN ('critical', 'error')
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;

-- Top chatbots by usage
SELECT
    c.name,
    COUNT(*) as message_count,
    SUM(tokens_total) as total_tokens
FROM usage_logs ul
JOIN chatbots c ON ul.chatbot_id = c.id
WHERE ul.created_at > NOW() - INTERVAL '7 days'
GROUP BY c.id, c.name
ORDER BY message_count DESC
LIMIT 10;

-- Tool failure rate
SELECT
    tool_name,
    tool_type,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE status = 'failed') as failures,
    (COUNT(*) FILTER (WHERE status = 'failed')::float / COUNT(*)) * 100 as failure_rate
FROM tool_executions
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY tool_name, tool_type
ORDER BY failure_rate DESC;
```

## 🚧 Roadmap

### Completed ✅
- [x] Multi-tenant database schema
- [x] WhatsApp webhook integration
- [x] 3-step processing flow
- [x] Agent loop with tool calling
- [x] RAG document processing (PDF, URL, DOC)
- [x] pgvector search
- [x] Usage tracking and quota enforcement
- [x] Slack alerting
- [x] Tool execution tracking
- [x] Comprehensive test harness

### In Progress 🚧
- [ ] Google Docs integration
- [ ] Advanced RAG (hybrid search, re-ranking)
- [ ] Dashboard UI for management
- [ ] Real-time WebSocket for live monitoring
- [ ] Multi-language support

### Future 🔮
- [ ] WhatsApp media handling (images, voice notes)
- [ ] Visual flow builder
- [ ] Custom embedding models
- [ ] A/B testing for prompts
- [ ] Analytics dashboard
- [ ] Multi-model support (Claude, Llama)
- [ ] Conversation flow templates

## 🤝 Contributing

This is a proprietary project. For internal development:

1. Create feature branch from `master`
2. Follow naming: `feature/short-description` or `fix/issue-description`
3. Write tests for new features
4. Update documentation
5. Create PR with detailed description

## 📄 License

Proprietary - All Rights Reserved

## 🆘 Support

For issues and questions:
1. Check documentation in `/docs`
2. Review `system_alerts` table
3. Check Slack alerts channel
4. Contact development team

---

**Built with ❤️ for scalable WhatsApp automation**
