/**
 * Organizations Routes
 *
 * Provides endpoints for organization management and usage tracking.
 */

const express = require('express');
const { body, validationResult } = require('express-validator');
const { verifyToken, pool } = require('../middleware/auth');

const router = express.Router();

// Valid plan tiers
const VALID_TIERS = ['free', 'starter', 'pro', 'enterprise'];

/**
 * GET /api/organizations/usage
 * Get current usage and limits for the user's organization
 *
 * Returns: { usage: {...}, limits: {...}, period: {...} }
 */
router.get('/usage', verifyToken, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT
         o.id, o.name, o.plan_tier,
         o.message_limit_monthly, o.token_limit_monthly,
         o.billing_period_start, o.billing_period_end,
         o.max_knowledge_pdfs, o.max_knowledge_urls,
         o.max_knowledge_storage_mb, o.max_knowledge_ingestions_per_day,
         o.current_knowledge_pdfs, o.current_knowledge_urls,
         o.current_storage_mb,
         COALESCE(us.current_period_messages, 0) as messages_used,
         COALESCE(us.current_period_tokens, 0) as tokens_used,
         COALESCE(dic.ingestion_count, 0) as today_ingestions
       FROM organizations o
       LEFT JOIN usage_summary us ON o.id = us.organization_id
       LEFT JOIN daily_ingestion_counts dic
         ON o.id = dic.organization_id AND dic.date = CURRENT_DATE
       WHERE o.id = $1`,
      [req.organizationId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Organization not found' });
    }

    const org = result.rows[0];

    res.json({
      organization: {
        id: org.id,
        name: org.name,
        planTier: org.plan_tier
      },
      usage: {
        messages: {
          used: org.messages_used,
          limit: org.message_limit_monthly,
          remaining: Math.max(0, org.message_limit_monthly - org.messages_used)
        },
        tokens: {
          used: parseInt(org.tokens_used),
          limit: parseInt(org.token_limit_monthly),
          remaining: Math.max(0, parseInt(org.token_limit_monthly) - parseInt(org.tokens_used))
        },
        knowledge: {
          pdfs: {
            used: org.current_knowledge_pdfs,
            limit: org.max_knowledge_pdfs,
            remaining: Math.max(0, org.max_knowledge_pdfs - org.current_knowledge_pdfs)
          },
          urls: {
            used: org.current_knowledge_urls,
            limit: org.max_knowledge_urls,
            remaining: Math.max(0, org.max_knowledge_urls - org.current_knowledge_urls)
          },
          storage: {
            usedMb: parseFloat(org.current_storage_mb),
            limitMb: org.max_knowledge_storage_mb,
            remainingMb: Math.max(0, org.max_knowledge_storage_mb - parseFloat(org.current_storage_mb))
          },
          dailyIngestions: {
            today: org.today_ingestions,
            limit: org.max_knowledge_ingestions_per_day,
            remaining: Math.max(0, org.max_knowledge_ingestions_per_day - org.today_ingestions)
          }
        }
      },
      billingPeriod: {
        start: org.billing_period_start,
        end: org.billing_period_end
      }
    });

  } catch (error) {
    console.error('Get usage error:', error);
    res.status(500).json({ error: 'Failed to get usage' });
  }
});

/**
 * PUT /api/organizations/billing
 * Update organization billing tier
 *
 * Body: { planTier: "free" | "starter" | "pro" | "enterprise" }
 * Returns: { organization: {...} }
 */
router.put('/billing',
  verifyToken,
  body('planTier').isIn(VALID_TIERS).withMessage(`Plan tier must be one of: ${VALID_TIERS.join(', ')}`),

  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        error: 'Validation failed',
        details: errors.array()
      });
    }

    const { planTier } = req.body;

    // Define limits per tier
    const tierLimits = {
      free: {
        message_limit_monthly: 100,
        token_limit_monthly: 50000,
        max_knowledge_pdfs: 5,
        max_knowledge_urls: 3,
        max_knowledge_storage_mb: 50,
        max_knowledge_ingestions_per_day: 10
      },
      starter: {
        message_limit_monthly: 500,
        token_limit_monthly: 250000,
        max_knowledge_pdfs: 20,
        max_knowledge_urls: 10,
        max_knowledge_storage_mb: 200,
        max_knowledge_ingestions_per_day: 50
      },
      pro: {
        message_limit_monthly: 2000,
        token_limit_monthly: 1000000,
        max_knowledge_pdfs: 50,
        max_knowledge_urls: 25,
        max_knowledge_storage_mb: 500,
        max_knowledge_ingestions_per_day: 100
      },
      enterprise: {
        message_limit_monthly: 10000,
        token_limit_monthly: 5000000,
        max_knowledge_pdfs: 200,
        max_knowledge_urls: 100,
        max_knowledge_storage_mb: 2000,
        max_knowledge_ingestions_per_day: 500
      }
    };

    const limits = tierLimits[planTier];

    try {
      const result = await pool.query(
        `UPDATE organizations
         SET plan_tier = $1,
             message_limit_monthly = $2,
             token_limit_monthly = $3,
             max_knowledge_pdfs = $4,
             max_knowledge_urls = $5,
             max_knowledge_storage_mb = $6,
             max_knowledge_ingestions_per_day = $7,
             updated_at = NOW()
         WHERE id = $8
         RETURNING id, name, slug, plan_tier, message_limit_monthly,
                   token_limit_monthly, max_knowledge_pdfs, max_knowledge_urls,
                   max_knowledge_storage_mb`,
        [
          planTier,
          limits.message_limit_monthly,
          limits.token_limit_monthly,
          limits.max_knowledge_pdfs,
          limits.max_knowledge_urls,
          limits.max_knowledge_storage_mb,
          limits.max_knowledge_ingestions_per_day,
          req.organizationId
        ]
      );

      if (result.rows.length === 0) {
        return res.status(404).json({ error: 'Organization not found' });
      }

      const org = result.rows[0];

      res.json({
        organization: {
          id: org.id,
          name: org.name,
          slug: org.slug,
          planTier: org.plan_tier,
          limits: {
            messagesMonthly: org.message_limit_monthly,
            tokensMonthly: parseInt(org.token_limit_monthly),
            knowledgePdfs: org.max_knowledge_pdfs,
            knowledgeUrls: org.max_knowledge_urls,
            knowledgeStorageMb: org.max_knowledge_storage_mb
          }
        },
        message: `Successfully upgraded to ${planTier} plan`
      });

    } catch (error) {
      console.error('Update billing error:', error);
      res.status(500).json({ error: 'Failed to update billing' });
    }
  }
);

/**
 * GET /api/organizations/settings
 * Get organization settings
 */
router.get('/settings', verifyToken, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT
         id, name, slug, plan_tier,
         notification_method, slack_webhook_url, notification_email,
         created_at, updated_at
       FROM organizations
       WHERE id = $1`,
      [req.organizationId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Organization not found' });
    }

    const org = result.rows[0];

    res.json({
      organization: {
        id: org.id,
        name: org.name,
        slug: org.slug,
        planTier: org.plan_tier,
        notifications: {
          method: org.notification_method,
          slackWebhookConfigured: !!org.slack_webhook_url,
          email: org.notification_email
        },
        createdAt: org.created_at,
        updatedAt: org.updated_at
      }
    });

  } catch (error) {
    console.error('Get settings error:', error);
    res.status(500).json({ error: 'Failed to get settings' });
  }
});

/**
 * PATCH /api/organizations/settings
 * Update organization settings
 */
router.patch('/settings',
  verifyToken,
  body('name').optional().trim().notEmpty(),
  body('notificationMethod').optional().isIn(['disabled', 'slack', 'email', 'whatsapp']),
  body('slackWebhookUrl').optional().isURL(),
  body('notificationEmail').optional().isEmail(),

  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        error: 'Validation failed',
        details: errors.array()
      });
    }

    const updates = req.body;
    const setClauses = [];
    const values = [];
    let paramIndex = 1;

    const fieldMap = {
      name: 'name',
      notificationMethod: 'notification_method',
      slackWebhookUrl: 'slack_webhook_url',
      notificationEmail: 'notification_email'
    };

    for (const [key, dbField] of Object.entries(fieldMap)) {
      if (updates[key] !== undefined) {
        setClauses.push(`${dbField} = $${paramIndex}`);
        values.push(updates[key]);
        paramIndex++;
      }
    }

    if (setClauses.length === 0) {
      return res.status(400).json({ error: 'No valid fields to update' });
    }

    values.push(req.organizationId);

    try {
      const result = await pool.query(
        `UPDATE organizations
         SET ${setClauses.join(', ')}, updated_at = NOW()
         WHERE id = $${paramIndex}
         RETURNING id, name, slug, notification_method, notification_email, updated_at`,
        values
      );

      if (result.rows.length === 0) {
        return res.status(404).json({ error: 'Organization not found' });
      }

      const org = result.rows[0];

      res.json({
        organization: {
          id: org.id,
          name: org.name,
          slug: org.slug,
          notifications: {
            method: org.notification_method,
            email: org.notification_email
          },
          updatedAt: org.updated_at
        }
      });

    } catch (error) {
      console.error('Update settings error:', error);
      res.status(500).json({ error: 'Failed to update settings' });
    }
  }
);

module.exports = router;
