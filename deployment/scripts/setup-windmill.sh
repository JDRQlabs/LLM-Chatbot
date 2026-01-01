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

# Basic auth for Caddy proxy (optional - only needed when accessing via HTTPS subdomain)
BASIC_AUTH_USER="${BASIC_AUTH_USER:-}"
BASIC_AUTH_PASS="${BASIC_AUTH_PASS:-}"

# Build curl auth args if basic auth credentials are provided
CURL_AUTH_ARGS=""
if [ -n "$BASIC_AUTH_USER" ] && [ -n "$BASIC_AUTH_PASS" ]; then
    CURL_AUTH_ARGS="-u $BASIC_AUTH_USER:$BASIC_AUTH_PASS"
    echo "Using basic auth for Caddy proxy"
fi

echo "=== Windmill Automated Setup ==="
echo "URL: $WINDMILL_URL"
echo "Workspace: $WORKSPACE_NAME ($WORKSPACE_ID)"
echo ""

# Function to wait for Windmill to be ready
wait_for_windmill() {
    echo "Waiting for Windmill to be ready..."
    for i in $(seq 1 $MAX_RETRIES); do
        local http_code
        http_code=$(curl -s $CURL_AUTH_ARGS -w "%{http_code}" -o /dev/null "$WINDMILL_URL/api/version" 2>&1)
        if [ "$http_code" = "200" ]; then
            echo "Windmill is ready!"
            return 0
        fi
        echo "  Attempt $i/$MAX_RETRIES - Windmill not ready yet (HTTP $http_code)..."
        sleep $RETRY_INTERVAL
    done
    echo "ERROR: Windmill did not become ready in time"
    exit 1
}

# Function to get auth token
get_auth_token() {
    echo "Getting authentication token..."
    TOKEN=$(curl -s $CURL_AUTH_ARGS -X POST "$WINDMILL_URL/api/auth/login" \
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
    local response=$(curl -s $CURL_AUTH_ARGS -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $TOKEN" \
        "$WINDMILL_URL/api/w/$WORKSPACE_ID/exists")
    [ "$response" = "200" ]
}

# Function to create workspace
create_workspace() {
    echo "Creating workspace '$WORKSPACE_NAME' ($WORKSPACE_ID)..."

    local response=$(curl -s $CURL_AUTH_ARGS -X POST "$WINDMILL_URL/api/workspaces/create" \
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
    API_TOKEN=$(curl -s $CURL_AUTH_ARGS -X POST "$WINDMILL_URL/api/users/tokens/create" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"label": "webhook-ingress-prod", "expiration": null}')

    if [ -z "$API_TOKEN" ] || echo "$API_TOKEN" | grep -q "error"; then
        echo "ERROR: Failed to create API token"
        echo "Response: $API_TOKEN"
        exit 1
    fi

    # Validate the token works by making a test API call
    echo "Validating API token..."
    local validate_response
    validate_response=$(curl -s $CURL_AUTH_ARGS -w "%{http_code}" -o /dev/null \
        -H "Authorization: Bearer $API_TOKEN" \
        "$WINDMILL_URL/api/w/$WORKSPACE_ID/flows/list" 2>&1)

    if [ "$validate_response" != "200" ]; then
        echo "ERROR: API token validation failed (HTTP $validate_response)"
        echo "Token: $API_TOKEN"
        exit 1
    fi

    echo "API token created and validated successfully"
}

# Function to create or update a Windmill variable
create_variable() {
    local var_path="$1"
    local var_value="$2"
    local var_description="${3:-}"
    local is_secret="${4:-true}"

    if [ -z "$var_value" ]; then
        echo "  Skipping $var_path (no value provided)"
        return 0
    fi

    echo "  Creating variable: $var_path"

    # Check if variable exists
    local exists_code
    exists_code=$(curl -s $CURL_AUTH_ARGS -w "%{http_code}" -o /dev/null \
        -H "Authorization: Bearer $TOKEN" \
        "$WINDMILL_URL/api/w/$WORKSPACE_ID/variables/get/$var_path" 2>&1)

    if [ "$exists_code" = "200" ]; then
        # Update existing variable
        curl -s $CURL_AUTH_ARGS -X POST "$WINDMILL_URL/api/w/$WORKSPACE_ID/variables/update/$var_path" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"value\": \"$var_value\"}" > /dev/null
        echo "    Updated existing variable"
    else
        # Create new variable
        local response
        response=$(curl -s $CURL_AUTH_ARGS -X POST "$WINDMILL_URL/api/w/$WORKSPACE_ID/variables/create" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "{
                \"path\": \"$var_path\",
                \"value\": \"$var_value\",
                \"is_secret\": $is_secret,
                \"description\": \"$var_description\"
            }")

        if echo "$response" | grep -q "error"; then
            echo "    WARNING: Failed to create variable: $response"
        else
            echo "    Created new variable"
        fi
    fi
}

# Function to setup required Windmill variables
setup_variables() {
    echo "Setting up Windmill variables..."

    # Read values from environment (these should be set in .env or passed to the script)
    local google_api_key="${GOOGLE_API_KEY:-}"
    local openai_api_key="${OPENAI_API_KEY:-}"
    local slack_webhook="${SLACK_ALERT_WEBHOOK:-}"

    # Create variables used by the flows
    create_variable "u/admin/GoogleAPI_JD" "$google_api_key" "Google API Key for Gemini LLM" "true"
    create_variable "u/admin/OpenAI_API_Key" "$openai_api_key" "OpenAI API Key" "true"
    create_variable "u/admin/SLACK_ALERT_WEBHOOK" "$slack_webhook" "Slack webhook for alerts" "true"

    echo "Variables setup complete"
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
    # Windmill webhook endpoint format:
    #   /api/w/{workspace}/jobs/run/f/{flow_path}
    # Where flow_path is the full path like "f/development/whatsapp_webhook_processor"
    # This results in /api/w/.../jobs/run/f/f/development/... (the f/f is correct!)
    local flow_path="f/development/whatsapp_webhook_processor"
    # Use Docker internal hostname for container-to-container communication
    FLOW_ENDPOINT="http://windmill_server:8000/api/w/$WORKSPACE_ID/jobs/run/f/$flow_path"
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
echo "Step 6: Setup Variables"
setup_variables

echo ""
echo "Step 7: Get Flow Endpoint"
get_flow_endpoint

echo ""
echo "Step 8: Update .env File"
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
