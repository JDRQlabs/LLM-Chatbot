/**
 * Quota Enforcement Middleware
 *
 * Checks if a chatbot's organization has remaining quota before
 * allowing knowledge base operations.
 */

const fetch = require('node-fetch');

const WINDMILL_URL = process.env.WINDMILL_URL || 'http://localhost:8000';
const WINDMILL_TOKEN = process.env.WINDMILL_TOKEN;
const WINDMILL_WORKSPACE = process.env.WINDMILL_WORKSPACE || 'development';

/**
 * Middleware to check knowledge quota before upload/ingestion
 *
 * Expects req.params.chatbotId and req.body.sourceType
 * Optionally req.body.fileSizeMb
 */
async function checkQuota(req, res, next) {
  const { chatbotId } = req.params;
  const { sourceType, fileSizeMb = 0 } = req.body;

  if (!chatbotId) {
    return res.status(400).json({ error: 'Missing chatbot ID' });
  }

  if (!sourceType) {
    return res.status(400).json({ error: 'Missing source type' });
  }

  try {
    // Call Windmill script to check quota
    const response = await fetch(
      `${WINDMILL_URL}/api/w/${WINDMILL_WORKSPACE}/jobs/run/p/f/development/utils/check_knowledge_quota`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${WINDMILL_TOKEN}`
        },
        body: JSON.stringify({
          chatbot_id: chatbotId,
          source_type: sourceType,
          file_size_mb: fileSizeMb
        })
      }
    );

    if (!response.ok) {
      throw new Error(`Windmill API error: ${response.statusText}`);
    }

    const result = await response.json();

    // Check if allowed
    if (!result.allowed) {
      return res.status(403).json({
        error: 'Quota exceeded',
        quotaType: result.quota_type,
        current: result.current,
        max: result.max,
        remaining: result.remaining
      });
    }

    // Store quota info in request for later use
    req.quotaInfo = result;
    next();

  } catch (error) {
    console.error('Quota check error:', error);
    return res.status(500).json({
      error: 'Failed to check quota',
      message: error.message
    });
  }
}

module.exports = { checkQuota };
