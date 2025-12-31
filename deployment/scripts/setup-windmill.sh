#!/bin/bash
# setup-windmill.sh
# Automates Windmill workspace creation, token generation, and flow sync
# Run this after Windmill is healthy on a fresh deployment

set -e

# Configuration
WINDMILL_URL="${WINDMILL_URL:-http://localhost:8000}"
WINDMILL_EMAIL="${WINDMILL_EMAIL:-admin@windmill.dev}"
WINDMILL_PASSWORD="${WINDMILL_PASSWORD:-changeme}"
WORKSPACE_NAME="${WORKSPACE_NAME:-production}"
WORKSPACE_ID="${WORKSPACE_ID:-production}"
SCRIPTS_DIR="${SCRIPTS_DIR:-$(dirname "$0")/../../}"  # Parent of deployment/scripts
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
        -d "{\"email\": \"$WINDMILL_EMAIL\", \"password\": \"$WINDMILL_PASSWORD\"}" \
        | grep -o '"token":"[^"]*' | cut -d'"' -f4)

    if [ -z "$TOKEN" ]; then
        echo "ERROR: Failed to get auth token. Check credentials."
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
    local response=$(curl -s -X POST "$WINDMILL_URL/api/users/tokens/create" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"label": "webhook-ingress", "expiration": null}')

    API_TOKEN=$(echo "$response" | grep -o '"token":"[^"]*' | cut -d'"' -f4)

    if [ -z "$API_TOKEN" ]; then
        echo "ERROR: Failed to create API token"
        echo "Response: $response"
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
    FLOW_ENDPOINT="$WINDMILL_URL/api/w/$WORKSPACE_ID/jobs/run/f/development/whatsapp_webhook_processor__flow"
    echo "Flow endpoint: $FLOW_ENDPOINT"
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
echo "=========================================="
echo "Windmill Setup Complete!"
echo "=========================================="
echo ""
echo "Add these to your .env file:"
echo ""
echo "WINDMILL_TOKEN=$API_TOKEN"
echo "WINDMILL_MESSAGE_PROCESSING_ENDPOINT=$FLOW_ENDPOINT"
echo ""
echo "Or run this to append them:"
echo "cat >> .env << EOF"
echo "WINDMILL_TOKEN=$API_TOKEN"
echo "WINDMILL_MESSAGE_PROCESSING_ENDPOINT=$FLOW_ENDPOINT"
echo "EOF"
echo ""
