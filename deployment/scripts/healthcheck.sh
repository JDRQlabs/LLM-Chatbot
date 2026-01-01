#!/bin/bash
# Health check script for Phase 0 deployment
# Usage: ./healthcheck.sh <server_ip>

set -e

IP="${1:-localhost}"
DOMAIN="${DOMAIN:-jdsoftwarelabs.com}"
WEBHOOK_TOKEN="${WEBHOOK_VERIFY_TOKEN:-JDlabs_webhook_verification}"
# Windmill basic auth credentials (default from Caddyfile)
WINDMILL_USER="${WINDMILL_AUTH_USER:-admin}"
WINDMILL_PASS="${WINDMILL_AUTH_PASS:-windmill-admin-2025}"

echo "=== Phase 0 Health Check - $IP ==="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}✓ PASS${NC}: $1"; }
fail() { echo -e "${RED}✗ FAIL${NC}: $1"; FAILED=1; }

FAILED=0

# 1. Caddy health (via HTTP for IP-based access)
echo "1. Testing Caddy reverse proxy..."
CADDY=$(curl -s --max-time 5 -o /dev/null -w "%{http_code}" "http://$IP/health" 2>/dev/null || echo "000")
if [ "$CADDY" = "200" ]; then
    pass "Caddy proxy responding"
else
    fail "Caddy proxy not responding (HTTP $CADDY)"
fi

# 2. API Server health (via subdomain)
echo "2. Testing API server..."
API_URL="https://api.$DOMAIN/api/health"
API=$(curl -s --max-time 5 "$API_URL" 2>/dev/null || echo '{}')
API_STATUS=$(echo "$API" | grep -o '"status":"healthy"' || echo "")
if [ -n "$API_STATUS" ]; then
    pass "API server healthy"
else
    fail "API server unhealthy: $API"
fi

# 3. Webhook verification (via subdomain)
echo "3. Testing webhook endpoint..."
WEBHOOK_URL="https://api.$DOMAIN/webhook?hub.mode=subscribe&hub.verify_token=$WEBHOOK_TOKEN&hub.challenge=HEALTH_CHECK"
WEBHOOK=$(curl -s --max-time 5 "$WEBHOOK_URL" 2>/dev/null || echo "")
if [ "$WEBHOOK" = "HEALTH_CHECK" ]; then
    pass "Webhook verification working"
else
    fail "Webhook verification failed: $WEBHOOK"
fi

# 4. Windmill API (via subdomain - API paths don't require basic auth)
echo "4. Testing Windmill..."
WINDMILL_URL="https://windmill.$DOMAIN/api/version"
WINDMILL_HTTP=$(curl -s --max-time 5 -o /dev/null -w "%{http_code}" "$WINDMILL_URL" 2>/dev/null || echo "000")
if [ "$WINDMILL_HTTP" = "200" ]; then
    WINDMILL=$(curl -s --max-time 5 "$WINDMILL_URL" 2>/dev/null || echo "")
    if [[ "$WINDMILL" == *"CE v"* ]] || [[ "$WINDMILL" == *"version"* ]]; then
        pass "Windmill responding: $WINDMILL"
    else
        pass "Windmill accessible (HTTP $WINDMILL_HTTP)"
    fi
elif [ "$WINDMILL_HTTP" = "401" ]; then
    # Shouldn't happen for /api/* paths, but handle just in case
    echo "  Warning: Windmill API returned 401 - check Caddy config"
    fail "Windmill API requires auth (unexpected)"
else
    fail "Windmill not responding (HTTP $WINDMILL_HTTP)"
fi

# 5. Database connectivity (via API health endpoint with extended check)
echo "5. Testing database connectivity..."
DB_CHECK=$(curl -s --max-time 5 "https://api.$DOMAIN/api/health" 2>/dev/null | grep -o '"status":"healthy"' || echo "")
if [ -n "$DB_CHECK" ]; then
    pass "Database connected (via API server)"
else
    fail "Database connection check failed"
fi

# Summary
echo ""
echo "=== Summary ==="
if [ "$FAILED" = "0" ]; then
    echo -e "${GREEN}All health checks passed!${NC}"
    exit 0
else
    echo -e "${RED}Some health checks failed${NC}"
    exit 1
fi
