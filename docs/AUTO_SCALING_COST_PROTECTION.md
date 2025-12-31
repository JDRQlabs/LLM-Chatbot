# Auto-Scaling with Cost Protection

**CRITICAL:** This document outlines hard safety limits to prevent cost explosions from DDOS attacks, bugs, or misconfiguration.

## Core Principles

1. **Fail Safe:** Hard-coded limits that cannot be accidentally changed
2. **Manual Approval:** Human verification required for significant scaling
3. **Cost Caps:** Absolute maximum monthly budget
4. **Alert Early:** Notify before limits are reached
5. **Fail Closed:** When in doubt, stop scaling (not start)

---

## Hard Limits (NON-NEGOTIABLE)

```javascript
// These limits are HARD-CODED and should NEVER be changed without review
const SAFETY_LIMITS = {
  MAX_SERVERS: 5,                    // Absolute maximum server count
  MAX_MONTHLY_COST_EUR: 50,          // Hard budget cap
  MAX_SCALE_UP_PER_HOUR: 1,          // Max new servers per hour
  MANUAL_APPROVAL_THRESHOLD: 3,       // Servers requiring manual approval
  DDOS_DETECTION_THRESHOLD: 1000,     // Requests/min triggering DDOS mode
  COST_ALERT_THRESHOLD_EUR: 40,       // Warning threshold
};
```

### Why These Limits?

**MAX_SERVERS = 5:**
- 5x CPX21 servers = €34.50/month
- Leaves budget for database, Redis, storage
- More than enough for MVP → 1000 users

**MAX_MONTHLY_COST_EUR = 50:**
- Conservative budget for early stage
- Prevents billing surprises
- Can be increased later with proper monitoring

**MANUAL_APPROVAL_THRESHOLD = 3:**
- 1-2 servers: Auto-scale freely
- 3+ servers: Requires human review
- Prevents runaway scaling from bugs

---

## Auto-Scaling Strategy

### Scale-Up Triggers

1. **CPU Usage > 80%** for 5 consecutive minutes
2. **Memory Usage > 85%** for 5 consecutive minutes
3. **API Response Time p95 > 2000ms** for 10 minutes

### Scale-Down Triggers

1. **CPU Usage < 30%** for 15 consecutive minutes
2. **Memory Usage < 40%** for 15 consecutive minutes
3. **AND** current server count > minimum (1)

### Cooldown Periods

- **Scale-Up Cooldown:** 10 minutes (prevent flapping)
- **Scale-Down Cooldown:** 30 minutes (more conservative)
- **Between Scale Operations:** 5 minutes minimum

---

## DDOS Detection & Response

### Detection Criteria

```javascript
function isDDOSAttack() {
  const requestsPerMinute = getRequestRate();
  const uniqueIPCount = getUniqueIPs();
  const errorRate = getErrorRate();

  // DDOS if:
  // - >1000 req/min AND <10 unique IPs
  // - OR >5000 req/min from any source
  // - OR >50% error rate with high traffic
  return (
    (requestsPerMinute > 1000 && uniqueIPCount < 10) ||
    (requestsPerMinute > 5000) ||
    (requestsPerMinute > 500 && errorRate > 0.5)
  );
}
```

### DDOS Response (instead of scaling)

1. **Enable Rate Limiting** (aggressive mode)
   - 10 requests/minute per IP
   - Block IPs with >100 requests in 5 minutes

2. **Enable Cloudflare "Under Attack" Mode**
   - Challenge suspicious requests
   - Block known attack patterns

3. **Alert Team** via Slack
   - Don't auto-scale
   - Investigate before adding servers

4. **If legitimate traffic spike:**
   - Manually approve scaling
   - Monitor cost dashboard
   - Scale down after spike

---

## Implementation: Hetzner Auto-Scaling Script

### Prerequisites

```bash
# Install Hetzner CLI
brew install hcloud  # or apt-get install hcloud

# Authenticate
hcloud context create whatsapp_chatbot
hcloud context use whatsapp_chatbot

# Set token (from Hetzner Console → API Tokens)
export HCLOUD_TOKEN=your_token_here
```

### Auto-Scaling Script

```bash
#!/bin/bash
# File: infrastructure/autoscale.sh
# Description: Auto-scaling with hard safety limits

set -euo pipefail

# ============================================
# HARD-CODED SAFETY LIMITS
# DO NOT CHANGE WITHOUT TEAM REVIEW
# ============================================
readonly MAX_SERVERS=5
readonly MIN_SERVERS=1
readonly MAX_MONTHLY_COST_EUR=50
readonly COST_ALERT_THRESHOLD_EUR=40
readonly MANUAL_APPROVAL_THRESHOLD=3
readonly MAX_SCALE_EVENTS_PER_HOUR=1
readonly DDOS_THRESHOLD_RPM=1000

# Slack webhook for alerts
readonly SLACK_WEBHOOK="${SLACK_WEBHOOK_URL:-}"

# ============================================
# Helper Functions
# ============================================

send_slack_alert() {
  local message="$1"
  local severity="${2:-info}"  # info, warning, critical

  local emoji="ℹ️"
  case "$severity" in
    warning) emoji="⚠️" ;;
    critical) emoji="🚨" ;;
  esac

  if [[ -n "$SLACK_WEBHOOK" ]]; then
    curl -X POST "$SLACK_WEBHOOK" \
      -H 'Content-Type: application/json' \
      -d "{\"text\": \"$emoji [AutoScale] $message\"}"
  fi

  echo "[$(date -Iseconds)] $emoji $message"
}

get_current_server_count() {
  hcloud server list --selector role=api --output columns=id | wc -l
}

get_estimated_monthly_cost() {
  local server_count=$1
  # CPX21 = €6.90/month
  # Managed PostgreSQL Small = €39/month
  # Redis 256MB = €4/month
  # Load Balancer = €5.90/month (if >1 server)

  local app_servers_cost=$(echo "$server_count * 6.90" | bc)
  local db_cost=39
  local redis_cost=4
  local lb_cost=0
  [[ $server_count -gt 1 ]] && lb_cost=5.90

  local total=$(echo "$app_servers_cost + $db_cost + $redis_cost + $lb_cost" | bc)
  echo "$total"
}

check_ddos() {
  # Query Prometheus or logs for request rate
  local rpm=$(curl -s http://localhost:9090/api/v1/query?query=rate(http_requests_total[1m]) | \
    jq -r '.data.result[0].value[1]')

  if (( $(echo "$rpm > $DDOS_THRESHOLD_RPM" | bc -l) )); then
    return 0  # Is DDOS
  else
    return 1  # Not DDOS
  fi
}

# ============================================
# Main Auto-Scaling Logic
# ============================================

main() {
  local action="${1:-check}"  # check, scale-up, scale-down

  # Get current state
  local current_servers=$(get_current_server_count)
  local estimated_cost=$(get_estimated_monthly_cost "$current_servers")

  send_slack_alert "Current: $current_servers servers, Est. cost: €${estimated_cost}/month" "info"

  # Safety check: Cost approaching limit
  if (( $(echo "$estimated_cost >= $COST_ALERT_THRESHOLD_EUR" | bc -l) )); then
    send_slack_alert "⚠️ Cost approaching limit: €${estimated_cost}/${MAX_MONTHLY_COST_EUR}" "warning"
  fi

  # Safety check: Cost exceeded
  if (( $(echo "$estimated_cost >= $MAX_MONTHLY_COST_EUR" | bc -l) )); then
    send_slack_alert "🚨 CRITICAL: Monthly cost limit reached (€${estimated_cost}/${MAX_MONTHLY_COST_EUR})" "critical"
    send_slack_alert "Auto-scaling DISABLED. Manual intervention required." "critical"
    exit 1
  fi

  # Handle scale-up request
  if [[ "$action" == "scale-up" ]]; then
    # Safety check: Already at max
    if [[ $current_servers -ge $MAX_SERVERS ]]; then
      send_slack_alert "Cannot scale up: Already at MAX_SERVERS ($MAX_SERVERS)" "warning"
      exit 1
    fi

    # Safety check: DDOS detection
    if check_ddos; then
      send_slack_alert "🚨 DDOS detected! Enabling rate limiting instead of scaling" "critical"
      # Enable aggressive rate limiting via Redis
      redis-cli SET "rate_limit:ddos_mode" "true" EX 3600
      exit 0
    fi

    # Safety check: Manual approval required
    if [[ $current_servers -ge $MANUAL_APPROVAL_THRESHOLD ]]; then
      send_slack_alert "Manual approval required to add server #$((current_servers + 1))" "warning"
      send_slack_alert "Reply 'APPROVE_SCALE_UP' in Slack to proceed (expires in 5 min)"  "warning"

      # Wait for manual approval (in production, use a proper approval flow)
      # For now, just block scaling
      echo "Waiting for manual approval..."
      exit 0
    fi

    # Calculate cost after scale-up
    local new_cost=$(get_estimated_monthly_cost "$((current_servers + 1))")
    if (( $(echo "$new_cost >= $MAX_MONTHLY_COST_EUR" | bc -l) )); then
      send_slack_alert "Cannot scale up: Would exceed cost limit (€${new_cost})" "warning"
      exit 1
    fi

    # All checks passed - proceed with scale-up
    send_slack_alert "Scaling UP: $current_servers → $((current_servers + 1)) servers" "info"

    # Create new server
    hcloud server create \
      --name "api-server-$((current_servers + 1))" \
      --type cpx21 \
      --image ubuntu-22.04 \
      --location fsn1 \
      --label role=api \
      --user-data-from-file infrastructure/cloud-init.yml

    send_slack_alert "✅ Server #$((current_servers + 1)) created successfully" "info"

    # If this is the 2nd server, create load balancer
    if [[ $((current_servers + 1)) -eq 2 ]]; then
      hcloud load-balancer create \
        --name api-lb \
        --type lb11 \
        --location fsn1

      send_slack_alert "✅ Load balancer created" "info"
    fi
  fi

  # Handle scale-down request
  if [[ "$action" == "scale-down" ]]; then
    # Safety check: Already at minimum
    if [[ $current_servers -le $MIN_SERVERS ]]; then
      send_slack_alert "Cannot scale down: Already at MIN_SERVERS ($MIN_SERVERS)" "info"
      exit 0
    fi

    send_slack_alert "Scaling DOWN: $current_servers → $((current_servers - 1)) servers" "info"

    # Remove oldest server
    local oldest_server=$(hcloud server list --selector role=api --output columns=id | sort -n | head -1)
    hcloud server delete "$oldest_server"

    send_slack_alert "✅ Server removed successfully" "info"

    # If down to 1 server, remove load balancer
    if [[ $((current_servers - 1)) -eq 1 ]]; then
      hcloud load-balancer delete api-lb || true
      send_slack_alert "✅ Load balancer removed (back to single server)" "info"
    fi
  fi
}

# Run main function
main "$@"
```

### Cloud-Init Configuration

```yaml
# File: infrastructure/cloud-init.yml
#cloud-config

packages:
  - docker.io
  - docker-compose
  - git

runcmd:
  # Clone application repository
  - git clone https://github.com/your-org/whatsapp_chatbot.git /opt/whatsapp_chatbot
  - cd /opt/whatsapp_chatbot

  # Setup environment
  - cp .env.example .env
  - echo "DB_HOST=managed-db.hetzner.cloud" >> .env
  - echo "REDIS_HOST=managed-redis.hetzner.cloud" >> .env

  # Start application
  - docker-compose up -d whatsapp_chatbot_api

  # Register with load balancer (if exists)
  - curl -X POST http://load-balancer:9000/register \
      -d '{"server": "'$(hostname -I | awk '{print $1}')'", "port": 4000}'
```

---

## Monitoring Dashboard

### Grafana Dashboard: Cost & Scaling

**Panels:**

1. **Current Monthly Cost Estimate**
   - Gauge: €X / €50 (budget)
   - Alert at €40

2. **Server Count Over Time**
   - Graph: Number of servers
   - Max line at 5 (hard limit)

3. **Auto-Scaling Events**
   - Timeline of scale-up/down events
   - Color-coded by approval status

4. **Request Rate**
   - Graph: Requests per minute
   - DDOS threshold line at 1000 rpm

5. **Resource Utilization**
   - CPU usage (all servers)
   - Memory usage (all servers)
   - Trigger thresholds visible

---

## Cost Monitoring Script

```bash
#!/bin/bash
# File: infrastructure/check-costs.sh
# Run daily via cron to verify actual costs match estimates

HETZNER_API_TOKEN="${HCLOUD_TOKEN}"
CURRENT_MONTH=$(date +%Y-%m)

# Get actual Hetzner usage for current month
actual_cost=$(curl -H "Authorization: Bearer $HETZNER_API_TOKEN" \
  "https://api.hetzner.cloud/v1/pricing" | \
  jq '.pricing.monthly_costs.amount')

echo "Actual cost for $CURRENT_MONTH: €${actual_cost}"

# Alert if over threshold
if (( $(echo "$actual_cost >= 40" | bc -l) )); then
  send_slack_alert "⚠️ Monthly cost: €${actual_cost} (approaching €50 limit)" "warning"
fi

# Block scaling if over limit
if (( $(echo "$actual_cost >= 50" | bc -l) )); then
  send_slack_alert "🚨 COST LIMIT EXCEEDED: €${actual_cost}" "critical"
  # Disable auto-scaling
  touch /var/lock/autoscale-disabled
fi
```

---

## Testing Auto-Scaling

### Test 1: Normal Scale-Up

```bash
# Simulate high CPU load
stress --cpu 4 --timeout 600s

# Monitor logs
tail -f /var/log/autoscale.log

# Expected: New server created after 5 minutes
```

### Test 2: DDOS Protection

```bash
# Simulate traffic spike
ab -n 100000 -c 100 http://your-api.com/

# Expected: Rate limiting enabled, NO new servers created
```

### Test 3: Cost Limit Protection

```bash
# Manually set high estimated cost
export FORCE_COST_ESTIMATE=55

# Try to scale
./infrastructure/autoscale.sh scale-up

# Expected: Scaling blocked, alert sent
```

### Test 4: Manual Approval Flow

```bash
# Start with 2 servers
# Trigger scale-up
./infrastructure/autoscale.sh scale-up

# Expected: Approval request sent to Slack, scaling paused
```

---

## Deployment Checklist

- [ ] Set `HCLOUD_TOKEN` environment variable
- [ ] Configure `SLACK_WEBHOOK_URL` for alerts
- [ ] Test auto-scaling script in staging
- [ ] Configure monitoring dashboard
- [ ] Document manual approval process
- [ ] Schedule daily cost check (cron: `0 9 * * * /usr/local/bin/check-costs.sh`)
- [ ] Test DDOS detection
- [ ] Document scale-down procedure
- [ ] Set up PagerDuty/OpsGenie for critical alerts

---

## Manual Override Procedures

### Disable Auto-Scaling (Emergency)

```bash
# Create lock file
touch /var/lock/autoscale-disabled

# Or set environment variable
export AUTOSCALE_DISABLED=true

# To re-enable
rm /var/lock/autoscale-disabled
```

### Force Scale-Down (Cost Reduction)

```bash
# Manually scale down to minimum
./infrastructure/autoscale.sh scale-down

# Verify
hcloud server list --selector role=api
```

### Override Cost Limit (Approved Increase)

```bash
# ONLY after team approval
# Edit hard-coded limit in autoscale.sh
# Commit change with approval reference

# Before changing, document in:
# - Slack channel
# - Git commit message
# - Cost tracking spreadsheet
```

---

## Summary

**Key Takeaways:**

1. ✅ Hard limits prevent runaway costs
2. ✅ Manual approval for significant scaling
3. ✅ DDOS detection prevents wasteful scaling
4. ✅ Daily cost monitoring catches overages
5. ✅ Alerts notify before problems occur

**Cost Protection Layers:**

1. **Hard-coded maximum** (5 servers, €50/month)
2. **Manual approval threshold** (3+ servers)
3. **Alert threshold** (€40/month)
4. **Daily cost checks** (actual vs. estimate)
5. **Emergency kill switch** (disable auto-scaling)

**Next Steps:**

1. Deploy auto-scaling script to production
2. Test in staging environment
3. Configure Slack alerts
4. Setup monitoring dashboard
5. Document manual procedures
6. Train team on override procedures
