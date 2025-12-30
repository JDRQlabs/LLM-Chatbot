const express = require('express');
const { Pool } = require('pg');

const app = express();
const PORT = process.env.PORT || 3003;

// PostgreSQL connection pool
const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: process.env.DB_PORT || 5432,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
});

app.use(express.json());

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'contact-owner-mcp' });
});

/**
 * Purpose-agnostic owner notification endpoint
 *
 * LLM calls this when it wants to notify the chatbot owner about something important:
 * - High-value leads
 * - Urgent customer issues
 * - Critical errors
 * - Any other scenario requiring owner attention
 */
app.post('/tools/contact_owner', async (req, res) => {
  const { chatbot_id, message, contact_info, urgency } = req.body;

  // Validate required fields
  if (!chatbot_id || !message) {
    return res.status(400).json({
      success: false,
      error: 'Missing required fields: chatbot_id and message are required'
    });
  }

  try {
    // Get chatbot owner and notification preferences
    const chatbotQuery = `
      SELECT
        c.id as chatbot_id,
        c.name as chatbot_name,
        c.organization_id,
        o.name as organization_name,
        o.slug as organization_slug,
        o.notification_method,
        o.slack_webhook_url,
        o.notification_email,
        u.email as owner_email,
        u.full_name as owner_name
      FROM chatbots c
      JOIN organizations o ON c.organization_id = o.id
      JOIN users u ON o.id = u.organization_id AND u.role = 'owner'
      WHERE c.id = $1 AND c.is_active = TRUE
      LIMIT 1
    `;

    const chatbotResult = await pool.query(chatbotQuery, [chatbot_id]);

    if (chatbotResult.rows.length === 0) {
      return res.status(404).json({
        success: false,
        error: 'Chatbot not found or inactive'
      });
    }

    const chatbot = chatbotResult.rows[0];

    // Get notification method from database (defaults to 'disabled' if not set)
    const notificationMethod = chatbot.notification_method || 'disabled';

    // Dispatch notification based on method
    let notificationResult = null;

    if (notificationMethod === 'slack') {
      notificationResult = await sendSlackNotification(chatbot, message, contact_info, urgency);
    } else if (notificationMethod === 'email') {
      // STUB: Email notification support
      notificationResult = {
        success: false,
        error: 'Email notifications not yet implemented'
      };
    } else if (notificationMethod === 'whatsapp') {
      // STUB: WhatsApp notification support (requires template messages)
      notificationResult = {
        success: false,
        error: 'WhatsApp notifications not yet implemented'
      };
    } else {
      notificationResult = {
        success: true,
        message: 'Notifications disabled for this chatbot'
      };
    }

    // Log notification attempt
    console.log(`[CONTACT_OWNER] Chatbot: ${chatbot.chatbot_name}, Method: ${notificationMethod}, Result:`, notificationResult);

    res.json({
      success: notificationResult.success,
      method: notificationMethod,
      owner: chatbot.owner_name,
      notification_sent: notificationResult.success,
      details: notificationResult
    });

  } catch (error) {
    console.error('[CONTACT_OWNER] Error:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

/**
 * Send Slack notification to chatbot owner
 */
async function sendSlackNotification(chatbot, message, contact_info, urgency) {
  // Get Slack webhook URL from database
  const slackWebhookUrl = chatbot.slack_webhook_url;

  if (!slackWebhookUrl) {
    return {
      success: false,
      error: 'Slack webhook not configured for this organization'
    };
  }

  // Build Slack message
  const urgencyEmoji = urgency === 'high' ? '🚨' : urgency === 'medium' ? '⚠️' : 'ℹ️';
  const color = urgency === 'high' ? 'danger' : urgency === 'medium' ? 'warning' : 'good';

  const slackPayload = {
    text: `${urgencyEmoji} Notification from ${chatbot.chatbot_name}`,
    attachments: [
      {
        color: color,
        title: 'Message from your AI Assistant',
        text: message,
        fields: [
          {
            title: 'Chatbot',
            value: chatbot.chatbot_name,
            short: true
          },
          {
            title: 'Organization',
            value: chatbot.organization_name,
            short: true
          }
        ],
        footer: 'JD Labs WhatsApp Chatbot',
        ts: Math.floor(Date.now() / 1000)
      }
    ]
  };

  // Add contact info if provided
  if (contact_info) {
    slackPayload.attachments[0].fields.push({
      title: 'Contact Information',
      value: formatContactInfo(contact_info),
      short: false
    });
  }

  try {
    const fetch = (await import('node-fetch')).default;
    const response = await fetch(slackWebhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(slackPayload)
    });

    if (response.ok) {
      return {
        success: true,
        message: 'Slack notification sent successfully'
      };
    } else {
      const errorText = await response.text();
      return {
        success: false,
        error: `Slack API error: ${errorText}`
      };
    }
  } catch (error) {
    return {
      success: false,
      error: `Failed to send Slack notification: ${error.message}`
    };
  }
}

/**
 * Format contact info for display (purpose-agnostic)
 * Handles any fields the LLM provides, regardless of business type
 */
function formatContactInfo(contact_info) {
  if (typeof contact_info === 'string') {
    return contact_info;
  }

  if (!contact_info || typeof contact_info !== 'object') {
    return 'No contact details provided';
  }

  // Generic formatting: iterate over all provided fields
  const parts = [];
  for (const [key, value] of Object.entries(contact_info)) {
    if (value !== null && value !== undefined && value !== '') {
      // Format key: convert snake_case or camelCase to Title Case
      const formattedKey = key
        .replace(/_/g, ' ')
        .replace(/([A-Z])/g, ' $1')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');

      // Format value: handle different types
      let formattedValue = value;
      if (typeof value === 'object') {
        formattedValue = JSON.stringify(value, null, 2);
      }

      parts.push(`*${formattedKey}:* ${formattedValue}`);
    }
  }

  return parts.length > 0 ? parts.join('\n') : 'No contact details provided';
}

// Start server
app.listen(PORT, () => {
  console.log(`[contact-owner-mcp] Server running on port ${PORT}`);
});
