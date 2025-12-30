#!/usr/bin/env bash
set -euo pipefail


# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions for colored output
error() {
  echo -e "${RED}✗ Error: $1${NC}" >&2
}

success() {
  echo -e "${GREEN}✓ $1${NC}"
}

info() {
  echo -e "${YELLOW}ℹ $1${NC}"
}

# 1. Load environment variables from the .env file in parent directory
load_env() {
  # Get the directory where this script is located
  local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # .env should be in the parent of the script's directory (src/.env)
  local env_file="${script_dir}/../.env"
  
  if [ ! -f "$env_file" ]; then
    error ".env file not found at: $env_file"
    echo "  Expected location: $(dirname "$script_dir")/.env"
    exit 1
  fi
  
  # Use a more robust method: set -a enables automatic export
  # Filter out comments and empty lines, then source
  set -a
  # Create a temporary file with cleaned .env content
  local temp_env=$(mktemp)
  grep -v '^[[:space:]]*#' "$env_file" | grep -v '^[[:space:]]*$' > "$temp_env"
  
  # Source the cleaned .env file
  # This properly handles quoted values, spaces, and special characters
  . "$temp_env" 2>/dev/null || {
    # Fallback: read line by line if sourcing fails
    while IFS= read -r line || [ -n "$line" ]; do
      [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
      # Remove inline comments (simple approach)
      line=$(echo "$line" | sed 's/[[:space:]]*#.*$//')
      [[ -z "$line" ]] && continue
      # Export the variable
      export "$line" 2>/dev/null || true
    done < "$env_file"
  }
  set +a
  rm -f "$temp_env"
  
  success ".env file loaded"
}

load_env

WINDMILL_URL="http://localhost:8081/api/w/development/jobs/run_wait_result/f/f/development/whatsapp_webhook_processor"
TOKEN="$WINDMILL_TOKEN"
WHATSAPP_PHONE_NUMBER_ID="$WHATSAPP_PHONE_NUMBER_ID"
WHATSAPP_USER_PHONE="5216441921909"
WHATSAPP_USER_NAME="JD"
WHATSAPP_MESSAGE_BODY="Hello, how are you?"
WHATSAPP_MESSAGE_ID="wamid.test.123"


info "curl command sent: \n
    curl -X POST \"$WINDMILL_URL\" -H \"Content-Type: application/json\" -H \"Authorization: Bearer $TOKEN\" -d '{
        \"phone_number_id\": \"$WHATSAPP_PHONE_NUMBER_ID\",
        \"user_phone\": \"$WHATSAPP_USER_PHONE\",
        \"user_name\": \"$WHATSAPP_USER_NAME\",
        \"message_body\": \"$WHATSAPP_MESSAGE_BODY\",
        \"message_id\": \"$WHATSAPP_MESSAGE_ID\"
      }'"

curl -X POST "$WINDMILL_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
        "phone_number_id": "911040768760384",
        "user_phone": "5216441921909",
        "user_name": "JD",
        "message_body": "Hello, how are you?",
        "message_id": "wamid.test.123"
      }'
