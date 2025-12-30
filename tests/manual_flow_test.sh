#!/bin/bash

# Manual flow test script
# Tests the WhatsApp webhook flow end-to-end

# Load environment variables
set -a
source ../.env
set +a

# Test webhook payload (from Meta's test message)
PAYLOAD='{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "0",
    "changes": [{
      "field": "messages",
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "display_phone_number": "16505551111",
          "phone_number_id": "123456123"
        },
        "contacts": [{
          "profile": {"name": "test user name"},
          "wa_id": "16315551181"
        }],
        "messages": [{
          "from": "16315551181",
          "id": "ABGGFlA5Fpa",
          "timestamp": "1504902988",
          "type": "text",
          "text": {"body": "this is a text message"}
        }]
      }
    }]
  }]
}'

echo "Testing webhook endpoint..."
curl -X POST http://localhost:3000/ \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"

echo -e "\n\nDone. Check Docker logs for results:"
echo "docker logs webhook-ingress"
echo "docker logs windmill_server"
