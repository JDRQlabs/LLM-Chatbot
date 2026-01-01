# Hetzner Deployment

Deployment tooling for the WhatsApp Chatbot platform on Hetzner Cloud.

## Prerequisites (one-time)

### 1. Install and authenticate `hcloud`

```bash
hcloud context list
hcloud server list
```

### 2. Create a dedicated SSH key

```bash
ssh-keygen -t ed25519 -f ~/.ssh/hetzner-proto -C "hetzner-proto"
hcloud ssh-key create --name hetzner-proto --public-key-from-file ~/.ssh/hetzner-proto.pub
```

### 3. Configure .env

```bash
cp ../.env.example ../.env
```

Required variables for production:
- `WHATSAPP_PHONE_NUMBER_ID` - Your WhatsApp Business API phone number ID
- `WHATSAPP_ACCESS_TOKEN` - Your WhatsApp API access token
- `OWNER_EMAIL` - Admin email for notifications
- `GOOGLE_API_KEY` - For Gemini LLM processing
- `SLACK_WEBHOOK_URL` - For owner notifications (optional)

---

## Fresh VM Setup Workflow

```bash
# 1. Create server and volume
make volume-create    # one-time
make up

# 2. Attach storage and deploy
make volume-attach
make volume-setup
make deploy

# 3. Start services
make start-prod

# 4. Initialize database
make db-init          # or db-reset to clear existing data

# 5. Setup Windmill
make setup-windmill

# 6. Create admin user
make create-admin EMAIL=admin@example.com PASSWORD=secure123

# 7. Verify everything works
make healthcheck
```

---

## Database Management

Both commands sync `.env` and `db/` files to the server before running.

```bash
# Initialize schema + migrations + seed (preserves data)
make db-init

# Drop all tables and reinitialize (DESTRUCTIVE)
make db-reset
```

The seed data uses `envsubst` to substitute `${VARIABLES}` from `.env`:
- `${WHATSAPP_PHONE_NUMBER_ID}`
- `${WHATSAPP_ACCESS_TOKEN}`
- `${OWNER_EMAIL}`
- `${SLACK_WEBHOOK_URL}`

---

## Debugging Windmill Flows

When a Windmill flow fails or behaves unexpectedly, use these techniques to debug.

### 1. Get the WINDMILL_TOKEN

The token is in `.env` after running `make setup-windmill`:
```bash
grep WINDMILL_TOKEN ../.env
```

### 2. List Recent Flow Executions

```bash
curl -s -H "Authorization: Bearer $WINDMILL_TOKEN" \
  "https://windmill.jdsoftwarelabs.com/api/w/production/jobs/completed/list?per_page=5" \
  | python3 -m json.tool
```

### 3. Get Flow Execution Details

```bash
# Get the flow result and step status
curl -s -H "Authorization: Bearer $WINDMILL_TOKEN" \
  "https://windmill.jdsoftwarelabs.com/api/w/production/jobs/completed/get/<JOB_ID>" \
  | python3 -c "
import sys,json
j=json.load(sys.stdin)
print('Result:', json.dumps(j.get('result'), indent=2))
print('Args:', json.dumps(j.get('args'), indent=2))
for m in j.get('flow_status', {}).get('modules', []):
    print(f\"  {m['id']}: {m['type']} (job: {m.get('job', 'N/A')})\")"
```

### 4. Get Individual Step Results

```bash
# Get logs and result for a specific step
curl -s -H "Authorization: Bearer $WINDMILL_TOKEN" \
  "https://windmill.jdsoftwarelabs.com/api/w/production/jobs/completed/get/<STEP_JOB_ID>" \
  | python3 -c "
import sys,json
j=json.load(sys.stdin)
print('=== Result ===')
print(json.dumps(j.get('result'), indent=2))
print('=== Logs ===')
print(j.get('logs', 'No logs'))"
```

### 5. Common Issues

| Error | Cause | Fix |
|-------|-------|-----|
| "Chatbot not found" | Missing chatbot in DB for phone_number_id | Run `make db-reset` |
| "Currently Processing" | Duplicate idempotency check (fixed) | N/A - bug was fixed |
| "Variable not found" | Missing Windmill variable | Run `make setup-windmill` with API keys in .env |
| 400 Bad Request to Meta | Invalid/expired WhatsApp token | Update WHATSAPP_ACCESS_TOKEN in .env, run `make db-reset` |

---

## Useful Commands

```bash
make ssh              # SSH into the server
make ps               # Show container status
make logs-prod        # Tail all container logs
make healthcheck      # Run health checks

# Restart services
make restart-service SERVICE=webhook-ingress
make recreate-service SERVICE=webhook-ingress  # Reloads .env

# Sync code changes
make deploy           # Sync all code (excludes deployment/)
```

---

## Cleanup

```bash
make down             # Delete server (stops billing)
./cleanup-expired.sh  # Auto-cleanup based on TTL labels
```

Schedule automatic cleanup:
```bash
crontab -e
# Add: */30 * * * * /path/to/cleanup-expired.sh >> /path/to/cleanup.log 2>&1
```
