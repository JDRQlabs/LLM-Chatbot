// app.js (Simplified)
import express from 'express';
import axios from 'axios';
import crypto from 'crypto';

const app = express();
app.use(express.json());

// 1. Meta Verification (GET) - Standard Meta Requirement
app.get('/', (req, res) => {
  if (
    req.query['hub.mode'] === 'subscribe' &&
    req.query['hub.verify_token'] === process.env.WEBHOOK_VERIFY_TOKEN
  ) {
    console.log('Webhook verified');
    res.send(req.query['hub.challenge']);
  } else {
    console.log('Webhook verification failed');
    res.sendStatus(400);
  }
});

// 2. Message Handling (POST)
app.post('/', async (req, res) => {
  console.log('Webhook received');
  // A. Immediate 200 OK to Meta
  res.sendStatus(200);

  const body = req.body;

  // B. Basic Filtering: Only process actual user messages
  // (Ignore status updates like "sent", "delivered", "read")
  if (body.object === 'whatsapp_business_account') {
    body.entry?.forEach((entry) => {
      entry.changes?.forEach((change) => {
        const value = change.value;

        // Check if it's a message (not a status update)
        if (value.messages && value.messages[0]) {
          console.log('Processing message');
          // C. Trigger Windmill Asynchronously
          // Fire and forget - don't await this
          triggerWindmillFlow(value);
          console.log('Triggered Windmill flow');
        }
      });
    });
  }
});

async function triggerWindmillFlow(payload) {
  try {
    const message = payload.messages[0];
    const contact = payload.contacts[0];
    const phoneNumberId = payload.metadata.phone_number_id;

    // Use the environment variable for the URL to keep it flexible
    const WINDMILL_URL = process.env.WINDMILL_MESSAGE_PROCESSING_ENDPOINT || 'http://windmill_server:8000';
    console.log('Triggering Windmill flow');
    await axios.post(
      `${WINDMILL_URL}`,
      {
        phone_number_id: phoneNumberId,
        user_phone: message.from,
        user_name: contact.profile.name,
        message_body: message.text.body,
        message_id: message.id
      },
      {
        headers: {
          // If you are using the default 'admin' user in local Windmill, 
          // you might need an API token generated from the UI.
          Authorization: `Bearer ${process.env.WINDMILL_TOKEN}`
        }
      }
    );
    console.log('Windmill flow triggered');
  } catch (error) {
    console.error("Failed to trigger Windmill:", error.message);
  }
}

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Webhook server is listening on port ${PORT}`);
});