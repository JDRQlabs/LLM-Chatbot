#!/bin/bash
# setup-windmill.sh
# ==============================================================================
# WINDMILL SERVER SETUP SCRIPT
# ==============================================================================
#
# This script sets up the Windmill SERVER (not workers). It:
#   1. Creates a workspace for your flows
#   2. Generates an API token for webhook-ingress to trigger flows
#   3. Syncs all scripts/flows from the local f/ directory
#   4. Updates .env with the generated credentials
#
# ARCHITECTURE NOTE (Phase 1 Scaling):
# ------------------------------------
# Windmill has two components:
#   - SERVER (windmill_server): Lightweight API/UI, job coordination, queue management
#   - WORKERS (windmill_worker): Heavy compute, executes Python/JS scripts
#
# For autoscaling:
#   - Run ONE server for coordination (this script sets it up)
#   - Scale WORKERS horizontally - they share the PostgreSQL job queue
#   - Workers can run on same VM or different VMs
#   - All workers connect to the same database
#
# Example Phase 1 architecture:
#   VM1: windmill_server + windmill_worker (primary)
#   VM2: windmill_worker only (connects to VM1's database)
#   VM3: windmill_worker only (connects to VM1's database)
#
# Run this after Windmill is healthy on a fresh deployment.
# ==============================================================================

set -e

# Configuration
WINDMILL_URL="${WINDMILL_URL:-http://localhost:8000}"
WINDMILL_EMAIL="${WINDMILL_EMAIL:-admin@windmill.dev}"
WINDMILL_PASSWORD="${WINDMILL_PASSWORD:-changeme}"
WORKSPACE_NAME="${WORKSPACE_NAME:-production}"
WORKSPACE_ID="${WORKSPACE_ID:-production}"
SCRIPTS_DIR="${SCRIPTS_DIR:-$(dirname "$0")/../../}"  # Parent of deployment/scripts
ENV_FILE="${ENV_FILE:-$SCRIPTS_DIR/.env}"
MAX_RETRIES=30
RETRY_INTERVAL=5

echo "=== Windmill Automated Setup ==="
echo "URL: $WINDMILL_URL"
echo "Workspace: $WORKSPACE_NAME ($WORKSPACE_ID)"
echo ""

# Function to wait for Windmill to be ready
wait_for_windmill() {
    echo "Waiting for Windmill to be ready..."
    for i in $(seq 1 $MAX_RETRIES); do
        if curl -s "$WINDMILL_URL/api/version" > /dev/null 2>&1; then
            echo "Windmill is ready!"
            return 0
        fi
        echo "  Attempt $i/$MAX_RETRIES - Windmill not ready yet..."
        sleep $RETRY_INTERVAL
    done
    echo "ERROR: Windmill did not become ready in time"
    exit 1
}

# Function to get auth token
get_auth_token() {
    echo "Getting authentication token..."
    TOKEN=$(curl -s -X POST "$WINDMILL_URL/api/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\": \"$WINDMILL_EMAIL\", \"password\": \"$WINDMILL_PASSWORD\"}")

    # Token is returned as plain text, not JSON
    if [ -z "$TOKEN" ] || echo "$TOKEN" | grep -q "error"; then
        echo "ERROR: Failed to get auth token. Check credentials."
        echo "Response: $TOKEN"
        exit 1
    fi
    echo "Got auth token"
}

# Function to check if workspace exists
workspace_exists() {
    local response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $TOKEN" \
        "$WINDMILL_URL/api/w/$WORKSPACE_ID/exists")
    [ "$response" = "200" ]
}

# Function to create workspace
create_workspace() {
    echo "Creating workspace '$WORKSPACE_NAME' ($WORKSPACE_ID)..."

    local response=$(curl -s -X POST "$WINDMILL_URL/api/workspaces/create" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"id\": \"$WORKSPACE_ID\", \"name\": \"$WORKSPACE_NAME\"}")

    if echo "$response" | grep -q "error"; then
        # Check if it already exists
        if echo "$response" | grep -q "already exists"; then
            echo "Workspace already exists"
            return 0
        fi
        echo "ERROR creating workspace: $response"
        exit 1
    fi
    echo "Workspace created successfully"
}

# Function to create an API token
create_api_token() {
    echo "Creating API token..."

    # Create a token that doesn't expire (or expires far in the future)
    # API returns the token as plain text, not JSON
    API_TOKEN=$(curl -s -X POST "$WINDMILL_URL/api/users/tokens/create" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"label": "webhook-ingress", "expiration": null}')

    if [ -z "$API_TOKEN" ] || echo "$API_TOKEN" | grep -q "error"; then
        echo "ERROR: Failed to create API token"
        echo "Response: $API_TOKEN"
        exit 1
    fi
    echo "API token created successfully"
}

# Function to sync scripts using wmill CLI
sync_scripts() {
    echo "Syncing scripts and flows..."

    cd "$SCRIPTS_DIR"

    # Add workspace to wmill CLI
    wmill workspace add "$WORKSPACE_NAME" "$WORKSPACE_ID" "$WINDMILL_URL" --token "$API_TOKEN" 2>/dev/null || true
    wmill workspace switch "$WORKSPACE_NAME" 2>/dev/null || true

    # Sync scripts
    wmill sync push --yes

    echo "Scripts synced successfully"
}

# Function to get the flow webhook endpoint
get_flow_endpoint() {
    local flow_path="f/$WORKSPACE_ID/whatsapp_webhook_processor__flow"
    # Use Docker internal hostname for container-to-container communication
    FLOW_ENDPOINT="http://windmill_server:8000/api/w/$WORKSPACE_ID/jobs/run/f/development/whatsapp_webhook_processor__flow"
    echo "Flow endpoint: $FLOW_ENDPOINT"
}

# Function to update .env file with generated credentials
update_env_file() {
    echo "Updating .env file..."

    if [ ! -f "$ENV_FILE" ]; then
        echo "WARNING: .env file not found at $ENV_FILE"
        echo "You'll need to manually add the credentials."
        return 1
    fi

    # Backup existing .env
    cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%Y%m%d_%H%M%S)"

    # Update or add WINDMILL_TOKEN
    if grep -q "^WINDMILL_TOKEN=" "$ENV_FILE"; then
        sed -i "s|^WINDMILL_TOKEN=.*|WINDMILL_TOKEN=$API_TOKEN|" "$ENV_FILE"
        echo "  Updated WINDMILL_TOKEN"
    else
        echo "WINDMILL_TOKEN=$API_TOKEN" >> "$ENV_FILE"
        echo "  Added WINDMILL_TOKEN"
    fi

    # Update or add WINDMILL_MESSAGE_PROCESSING_ENDPOINT
    if grep -q "^WINDMILL_MESSAGE_PROCESSING_ENDPOINT=" "$ENV_FILE"; then
        sed -i "s|^WINDMILL_MESSAGE_PROCESSING_ENDPOINT=.*|WINDMILL_MESSAGE_PROCESSING_ENDPOINT=$FLOW_ENDPOINT|" "$ENV_FILE"
        echo "  Updated WINDMILL_MESSAGE_PROCESSING_ENDPOINT"
    else
        echo "WINDMILL_MESSAGE_PROCESSING_ENDPOINT=$FLOW_ENDPOINT" >> "$ENV_FILE"
        echo "  Added WINDMILL_MESSAGE_PROCESSING_ENDPOINT"
    fi

    echo ".env file updated successfully"
}

# Main execution
echo ""
echo "Step 1: Wait for Windmill"
wait_for_windmill

echo ""
echo "Step 2: Authenticate"
get_auth_token

echo ""
echo "Step 3: Create Workspace"
create_workspace

echo ""
echo "Step 4: Create API Token"
create_api_token

echo ""
echo "Step 5: Sync Scripts"
sync_scripts

echo ""
echo "Step 6: Get Flow Endpoint"
get_flow_endpoint

echo ""
echo "Step 7: Update .env File"
update_env_file

echo ""
echo "=========================================="
echo "Windmill Server Setup Complete!"
echo "=========================================="
echo ""
echo "Generated credentials:"
echo "  WINDMILL_TOKEN=$API_TOKEN"
echo "  WINDMILL_MESSAGE_PROCESSING_ENDPOINT=$FLOW_ENDPOINT"
echo ""
echo "IMPORTANT: Restart webhook-ingress to pick up new credentials:"
echo "  docker compose -f docker-compose.phase0.yml restart webhook-ingress"
echo ""
