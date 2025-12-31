# Quick Reference - Developer Cheat Sheet

## Database Operations

### Reset Database
```bash
cd db
./manage_db.sh reset
```

### Check Database State
```bash
./manage_db.sh verify
```

### Common Queries
```sql
-- Check usage for an org
SELECT * FROM get_current_usage('org-uuid');

-- Find duplicate webhook events
SELECT whatsapp_message_id, COUNT(*) 
FROM webhook_events 
GROUP BY whatsapp_message_id 
HAVING COUNT(*) > 1;

-- Recent messages for a contact
SELECT * FROM messages 
WHERE contact_id = 'contact-uuid' 
ORDER BY created_at DESC LIMIT 10;

-- Current usage by org
SELECT 
  o.name,
  us.current_period_messages,
  us.current_period_tokens,
  o.message_limit_monthly,
  o.token_limit_monthly
FROM usage_summary us
JOIN organizations o ON us.organization_id = o.id;
```

## Testing

### Run All Tests
```bash
pytest
```

### Run Specific Tests
```bash
# By file
pytest tests/unit/test_step1_context_loading.py

# By marker
pytest -m unit
pytest -m integration
pytest -m db

# By keyword
pytest -k "idempotency"
pytest -k "usage_limits"
```

Refer to pytest.ini:
markers =
    unit: Unit tests that test individual functions in isolation
    integration: Integration tests that test multiple components together
    slow: Tests that take a long time to run
    db: Tests that require database access
    external: Tests that make real external API calls (should be rarely used)
    live_llm: Tests that make real LLM API calls (OpenAI, Gemini). Run with -m live_llm
    live_embeddings: Tests that generate real embeddings via OpenAI. Run with -m live_embeddings
    live: All live tests that use real external APIs. Run with -m live

### Coverage
```bash
pytest --cov=f/development --cov-report=html
open htmlcov/index.html
```

### Debug Mode
```bash
# Drop into debugger on failure
pytest --pdb

# Verbose output
pytest -vv
```

## Docker Commands

### Main Services
```bash
# Start all
docker-compose up -d

# View logs
docker-compose logs -f webhook-ingress
docker-compose logs -f windmill_worker

# Restart service
docker-compose restart webhook-ingress

# Stop all
docker-compose down
```

### Test Database
```bash
# Start test DB
docker-compose -f docker-compose.test.yml up -d

# Connect to test DB
docker exec -it test_business_logic_db psql -U test_user -d test_business_logic

# Reset test DB
use ./db/manage_db.sh --test reset
```

## Windmill Flows

### Trigger Flow Manually
```bash
# Using curl_windmill_endpoint.sh
cd utils
./curl_windmill_endpoint.sh
```

### Flow Structure
```
1. Context Loading
   ├─ Check idempotency
   ├─ Check usage limits
   ├─ Load chatbot config
   ├─ Fetch tools
   └─ Get history

2. LLM Processing
   ├─ Build prompt
   ├─ Call LLM
   └─ (Future: Tool use)

3. Parallel Execution
   ├─ Send WhatsApp reply
   ├─ Save chat history
   └─ Log usage
```

## Common Debugging

### No Response Sent?

**Check:**
```sql
-- Webhook event status
SELECT * FROM webhook_events ORDER BY created_at DESC LIMIT 5;

-- Recent messages
SELECT * FROM messages ORDER BY created_at DESC LIMIT 10;
```

**Logs:**
```bash
docker-compose logs webhook-ingress | grep -i error
docker-compose logs windmill_worker | grep -i error
```

### Duplicate Messages?

**Check:**
```sql
-- Find duplicates
SELECT whatsapp_message_id, status, COUNT(*) as count
FROM webhook_events
GROUP BY whatsapp_message_id, status
HAVING COUNT(*) > 1;
```

### Usage Limits Not Working?

**Check:**
```sql
-- Org limits
SELECT * FROM organizations WHERE id = 'org-uuid';

-- Current usage
SELECT * FROM usage_summary WHERE organization_id = 'org-uuid';

-- Recent logs
SELECT * FROM usage_logs 
WHERE organization_id = 'org-uuid' 
ORDER BY created_at DESC LIMIT 10;
```

## Environment Variables

### Required in .env
```bash
# Windmill DB
WINDMILL_DATABASE_URL=postgres://postgres:changeme@db/windmill?sslmode=disable
WINDMILL_DB_PASSWORD=changeme
WINDMILL_DB_NAME=windmill

# Business Logic DB
BUSINESS_LOGIC_DB_USER=business_logic_user
BUSINESS_LOGIC_DB_PASSWORD=business_logic_password
BUSINESS_LOGIC_DB_NAME=business_logic_app

# WhatsApp (for seed data)
WHATSAPP_PHONE_NUMBER_ID=your_phone_id
WHATSAPP_ACCESS_TOKEN=your_token
OWNER_EMAIL=your_email

# Webhook Server
WEBHOOK_VERIFY_TOKEN=your_verify_token
WINDMILL_TOKEN=your_windmill_api_token
WINDMILL_MESSAGE_PROCESSING_ENDPOINT=http://windmill_server:8000/api/w/development/jobs/run/f/development/whatsapp_webhook_processor
```

### Test Environment
```bash
# Test DB (in .env or .env.test)
TEST_DB_HOST=localhost
TEST_DB_PORT=5434
TEST_DB_USER=test_user
TEST_DB_PASSWORD=test_password
TEST_DB_NAME=test_business_logic
```

## File Locations

### Key Files
```
Configuration
├── .env                    # Environment variables
├── docker-compose.yml      # Main services
├── docker-compose.test.yml # Test database
└── pytest.ini              # Test configuration

Database
├── db/create.sql          # Schema definition
├── db/drop.sql            # Reset script
├── db/seed.sql            # Test data
└── db/manage_db.sh        # Helper script

Windmill Scripts
├── f/development/1_whatsapp_context_loading.py
├── f/development/2_whatsapp_llm_processing.py
├── f/development/3_1_send_reply_to_whatsapp.py
├── f/development/4_save_chat_history.py
└── f/development/5_log_usage.py

Testing
├── tests/conftest.py              # Fixtures
├── tests/test_harness/            # Mocks
└── tests/unit/                    # Unit tests
```

## API Endpoints

### WhatsApp Webhook
```bash
# Verification (GET)
GET http://localhost:3000/?hub.mode=subscribe&hub.verify_token=TOKEN&hub.challenge=CHALLENGE

# Message webhook (POST)
POST http://localhost:3000/
Content-Type: application/json

{
  "object": "whatsapp_business_account",
  "entry": [{
    "changes": [{
      "value": {
        "messages": [{
          "from": "phone",
          "id": "msg_id",
          "text": {"body": "Hello"}
        }]
      }
    }]
  }]
}
```

### Windmill Flow
```bash
# Direct trigger
POST http://localhost:8081/api/w/development/jobs/run/f/development/whatsapp_webhook_processor
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "phone_number_id": "123",
  "user_phone": "15551234567",
  "user_name": "Test",
  "message_body": "Hello",
  "message_id": "wamid.unique.001"
}
```

## Schema Reference

### Key Tables

**organizations**
- `id` - UUID primary key
- `message_limit_monthly` - Messages allowed
- `token_limit_monthly` - Tokens allowed
- `billing_period_start/end` - Current period

**chatbots**
- `id` - UUID primary key
- `whatsapp_phone_number_id` - Routing key
- `organization_id` - Owner
- `is_active` - Enable/disable

**webhook_events**
- `whatsapp_message_id` - Unique (idempotency)
- `status` - received/processing/completed/failed
- `chatbot_id` - Which bot

**usage_logs**
- `organization_id` - Who used it
- `tokens_input/output/total` - Usage
- `estimated_cost_usd` - Cost estimate

**usage_summary**
- `organization_id` - Cached usage
- `current_period_messages/tokens` - Quick check

## Common Tasks

### Add New Organization
```sql
INSERT INTO organizations (name, slug, plan_tier, message_limit_monthly, token_limit_monthly)
VALUES ('New Corp', 'new-corp', 'pro', 1000, 1000000);
```

### Add New Chatbot
```sql
INSERT INTO chatbots (
  organization_id, 
  name, 
  whatsapp_phone_number_id, 
  whatsapp_access_token,
  system_prompt
) VALUES (
  'org-uuid',
  'New Bot',
  'phone_id_123',
  'token_xyz',
  'You are a helpful assistant'
);
```

### Reset Usage for Testing
```sql
-- Reset usage summary
UPDATE usage_summary 
SET current_period_messages = 0, 
    current_period_tokens = 0
WHERE organization_id = 'org-uuid';

-- Delete usage logs (optional)
DELETE FROM usage_logs 
WHERE organization_id = 'org-uuid';
```

### Clear Old Webhook Events
```sql
-- Delete completed events older than 24 hours
DELETE FROM webhook_events
WHERE status = 'completed'
  AND processed_at < NOW() - INTERVAL '24 hours';

-- Or use the function
SELECT cleanup_old_webhook_events();
```

## Performance Tips

### Slow Queries?
```sql
-- Check query plan
EXPLAIN ANALYZE 
SELECT * FROM get_current_usage('org-uuid');

-- Check missing indexes
SELECT 
  schemaname,
  tablename,
  indexname
FROM pg_indexes
WHERE schemaname = 'public';
```

### Database Maintenance
```bash
# Connect to DB
docker exec -it business_logic_db psql -U business_logic_user -d business_logic_app

# Vacuum and analyze
VACUUM ANALYZE;

# Check table sizes
SELECT 
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Error Messages

| Error | Meaning | Fix |
|-------|---------|-----|
| "DB Connection Failed" | Can't reach database | Check docker-compose ps |
| "Chatbot not found" | Invalid phone_number_id | Check chatbots table |
| "Duplicate - Already Processed" | Message seen before | Normal, idempotency working |
| "Usage Limit Exceeded" | Out of quota | Check usage_summary, increase limits |
| "Service Inactive" | Chatbot/Org disabled | Check is_active flags |
