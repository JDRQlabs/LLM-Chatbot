// app.js (Simplified)
import express from 'express';
import axios from 'axios';
import crypto from 'crypto';
import pg from 'pg';
import { initializeRedis, checkRateLimit, closeRedis } from './rateLimiter.js';

const { Pool } = pg;

const app = express();

// SECURITY: Store raw body for HMAC signature verification
app.use(express.json({
  verify: (req, res, buf) => {
    req.rawBody = buf;
  }
}));

// SECURITY: Meta App Secret for HMAC signature verification
// This should be your Meta WhatsApp Business app's secret
const APP_SECRET = process.env.META_APP_SECRET;

/**
 * Verify Meta webhook signature (HMAC-SHA256)
 * Meta sends X-Hub-Signature-256 header with all webhook requests
 */
function verifyWebhookSignature(req) {
  // Skip verification if APP_SECRET not configured (development mode)
  if (!APP_SECRET) {
    console.warn('WARNING: META_APP_SECRET not set - webhook signature verification disabled');
    return true;
  }

  const signature = req.headers['x-hub-signature-256'];
  if (!signature) {
    console.error('Missing X-Hub-Signature-256 header');
    return false;
  }

  const expectedSignature = 'sha256=' + crypto
    .createHmac('sha256', APP_SECRET)
    .update(req.rawBody)
    .digest('hex');

  const isValid = crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expectedSignature)
  );

  if (!isValid) {
    console.error('Invalid webhook signature');
  }

  return isValid;
}

// Database connection pool for business logic database
const pool = new Pool({
  host: process.env.DB_HOST || 'business_logic_db',
  port: process.env.DB_PORT || 5432,
  user: process.env.DB_USER || 'business_logic_user',
  password: process.env.DB_PASSWORD || 'business_logic_password',
  database: process.env.DB_NAME || 'business_logic_app',
  max: 10,
  idleTimeoutMillis: 30000,
});

// Message size limits per plan tier (in characters)
const MESSAGE_LIMITS = {
  free: 2000,
  pro: 5000,
  enterprise: 10000
};

// Initialize Redis for rate limiting
initializeRedis().catch(err => {
  console.error('Failed to initialize Redis:', err);
  console.warn('Rate limiting will be disabled (fail-open mode)');
});

app.use((req, res, next) => {
  // Log EVERYTHING
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
  if (req.method === 'POST') {
    console.log('Payload:', JSON.stringify(req.body, null, 2));
  }
  next();
});


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

  // SECURITY: Verify webhook signature before processing
  if (!verifyWebhookSignature(req)) {
    console.error('Webhook signature verification failed - rejecting request');
    return res.status(401).json({ error: 'Invalid signature' });
  }

  const body = req.body;

  // B. Basic Filtering: Only process actual user messages
  // (Ignore status updates like "sent", "delivered", "read")
  if (body.object !== 'whatsapp_business_account') {
    return res.sendStatus(200);
  }

  // Process each entry/change
  for (const entry of body.entry || []) {
    for (const change of entry.changes || []) {
      const value = change.value;

      // Check if it's a message (not a status update)
      if (!value.messages || !value.messages[0]) {
        continue;
      }

      const message = value.messages[0];
      const phoneNumberId = value.metadata?.phone_number_id;
      const whatsappMessageId = message.id;

      // A. Idempotency Check - BEFORE triggering Windmill
      // This prevents duplicate processing if Meta sends the same webhook multiple times
      if (whatsappMessageId && phoneNumberId) {
        try {
          const result = await pool.query(
            `INSERT INTO webhook_events
             (whatsapp_message_id, phone_number_id, status, raw_payload, received_at)
             VALUES ($1, $2, 'processing', $3, NOW())
             ON CONFLICT (whatsapp_message_id) DO NOTHING
             RETURNING id`,
            [whatsappMessageId, phoneNumberId, JSON.stringify(body)]
          );

          if (result.rows.length === 0) {
            // Duplicate webhook - already processed or being processed
            console.log(`Duplicate webhook detected: ${whatsappMessageId} - skipping`);
            return res.status(200).json({ status: 'duplicate' });
          }

          console.log(`Webhook event created: ${whatsappMessageId} (id: ${result.rows[0].id})`);
        } catch (e) {
          // Fail open - if idempotency check fails, continue processing
          // This prevents blocking legitimate requests due to DB issues
          console.error('Idempotency check failed (continuing anyway):', e.message);
        }
      }

      // B. Respond 200 OK to Meta immediately (they require < 3 seconds)
      res.sendStatus(200);

      // C. Trigger Windmill Asynchronously
      console.log('Processing message:', whatsappMessageId);
      triggerWindmillFlow(value).catch(err => {
        console.error('Windmill flow failed:', err.message);
        // Update webhook_events status to 'failed' if possible
        if (whatsappMessageId) {
          pool.query(
            `UPDATE webhook_events SET status = 'failed', error_message = $1, processed_at = NOW() WHERE whatsapp_message_id = $2`,
            [err.message, whatsappMessageId]
          ).catch(dbErr => console.error('Failed to update webhook status:', dbErr.message));
        }
      });

      console.log('Triggered Windmill flow');
      return; // Only process first message, then exit
    }
  }

  // No messages found, just acknowledge
  res.sendStatus(200);
});

async function triggerWindmillFlow(payload) {
  try {
    const message = payload.messages[0];
    const contact = payload.contacts[0];
    const phoneNumberId = payload.metadata.phone_number_id;
    const messageBody = message.text?.body || '';

    // Phase 7.1: Message Size Validation
    // Get chatbot's organization plan tier to enforce message limits
    let planTier = 'free'; // Default to most restrictive
    let maxMessageLength = MESSAGE_LIMITS.free;

    try {
      const result = await pool.query(`
        SELECT o.plan_tier
        FROM chatbots c
        JOIN organizations o ON c.organization_id = o.id
        WHERE c.phone_number_id = $1
        LIMIT 1
      `, [phoneNumberId]);

      if (result.rows.length > 0) {
        planTier = result.rows[0].plan_tier;
        maxMessageLength = MESSAGE_LIMITS[planTier] || MESSAGE_LIMITS.free;
      }
    } catch (dbError) {
      console.error('Failed to fetch plan tier, using default (free):', dbError.message);
    }

    // Validate message size
    if (messageBody.length > maxMessageLength) {
      console.warn(`Message too long: ${messageBody.length} chars (max: ${maxMessageLength} for ${planTier} plan)`);
      console.log(`Rejecting message from ${message.from} - exceeds ${planTier} plan limit`);

      // Don't trigger Windmill flow - message rejected for being too long
      // In production, you might want to send a WhatsApp reply explaining the limit
      return;
    }

    console.log(`Message validated: ${messageBody.length}/${maxMessageLength} chars (${planTier} plan)`);

    // Phase 7.2: Rate Limiting
    // Check if chatbot has exceeded rate limit for their plan tier
    const rateLimit = await checkRateLimit(phoneNumberId, planTier);

    if (!rateLimit.allowed) {
      console.warn(`Rate limit exceeded for ${phoneNumberId}: ${rateLimit.current}/${rateLimit.max} messages/hour (${planTier} plan)`);
      console.log(`Rejecting message from ${message.from} - rate limit exceeded, resets in ${rateLimit.resetIn}s`);

      // Don't trigger Windmill flow - rate limit exceeded
      // In production, you might want to send a WhatsApp reply explaining the limit
      return;
    }

    console.log(`Rate limit OK: ${rateLimit.current}/${rateLimit.max} messages/hour (${planTier} plan)`);

    // Use the environment variable for the URL to keep it flexible
    const WINDMILL_URL = process.env.WINDMILL_MESSAGE_PROCESSING_ENDPOINT || 'http://windmill_server:8000';
    console.log('Triggering Windmill flow with payload:', payload);
    console.log('WINDMILL_URL:', WINDMILL_URL);
    await axios.post(
      `${WINDMILL_URL}`,
      {
        phone_number_id: phoneNumberId,
        user_phone: message.from,
        user_name: contact.profile.name,
        message_body: messageBody,
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
    console.log('Windmill flow triggered successfully');
  } catch (error) {
    console.error("Failed to trigger Windmill:", error.message);
    console.error("Error details:", error.response?.data);
  }
}

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Webhook server is listening on port ${PORT}`);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, shutting down gracefully...');
  await closeRedis();
  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('SIGINT received, shutting down gracefully...');
  await closeRedis();
  process.exit(0);
});