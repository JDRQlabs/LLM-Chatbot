/**
 * Integrations Routes
 *
 * Provides endpoints for managing MCP tools and integrations.
 */

const express = require('express');
const { body, validationResult } = require('express-validator');
const { verifyToken, pool } = require('../middleware/auth');

const router = express.Router();

/**
 * GET /api/integrations/available
 * List all available integrations for the organization
 *
 * Returns: { integrations: [...] }
 */
router.get('/available', verifyToken, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT
         id, provider, name, config, is_active, created_at, updated_at
       FROM org_integrations
       WHERE organization_id = $1
       ORDER BY name`,
      [req.organizationId]
    );

    res.json({
      integrations: result.rows.map(row => ({
        id: row.id,
        provider: row.provider,
        name: row.name,
        description: row.config?.description || null,
        serverUrl: row.config?.server_url || null,
        llmInstructions: row.config?.llm_instructions || null,
        parameters: row.config?.parameters || null,
        isActive: row.is_active,
        createdAt: row.created_at,
        updatedAt: row.updated_at
      }))
    });

  } catch (error) {
    console.error('List integrations error:', error);
    res.status(500).json({ error: 'Failed to list integrations' });
  }
});

/**
 * GET /api/integrations/:id
 * Get a single integration
 */
router.get('/:id', verifyToken, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT
         id, provider, name, config, credentials, is_active,
         created_at, updated_at
       FROM org_integrations
       WHERE id = $1 AND organization_id = $2`,
      [req.params.id, req.organizationId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Integration not found' });
    }

    const row = result.rows[0];

    // Don't expose credentials
    res.json({
      integration: {
        id: row.id,
        provider: row.provider,
        name: row.name,
        config: row.config,
        hasCredentials: !!row.credentials && Object.keys(row.credentials).length > 0,
        isActive: row.is_active,
        createdAt: row.created_at,
        updatedAt: row.updated_at
      }
    });

  } catch (error) {
    console.error('Get integration error:', error);
    res.status(500).json({ error: 'Failed to get integration' });
  }
});

/**
 * POST /api/integrations
 * Create a new integration
 *
 * Body: { provider, name, config, credentials? }
 */
router.post('/',
  verifyToken,
  body('provider').trim().notEmpty().withMessage('Provider is required'),
  body('name').trim().notEmpty().withMessage('Name is required'),
  body('config').isObject().withMessage('Config must be an object'),

  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        error: 'Validation failed',
        details: errors.array()
      });
    }

    const { provider, name, config, credentials } = req.body;

    try {
      const result = await pool.query(
        `INSERT INTO org_integrations
         (organization_id, provider, name, config, credentials, is_active)
         VALUES ($1, $2, $3, $4, $5, TRUE)
         RETURNING id, provider, name, config, is_active, created_at`,
        [req.organizationId, provider, name, config, credentials || {}]
      );

      const row = result.rows[0];

      res.status(201).json({
        integration: {
          id: row.id,
          provider: row.provider,
          name: row.name,
          config: row.config,
          isActive: row.is_active,
          createdAt: row.created_at
        }
      });

    } catch (error) {
      console.error('Create integration error:', error);
      res.status(500).json({ error: 'Failed to create integration' });
    }
  }
);

/**
 * PATCH /api/integrations/:id
 * Update an integration
 */
router.patch('/:id',
  verifyToken,
  body('name').optional().trim().notEmpty(),
  body('config').optional().isObject(),
  body('isActive').optional().isBoolean(),

  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        error: 'Validation failed',
        details: errors.array()
      });
    }

    const integrationId = req.params.id;
    const updates = req.body;

    // Verify ownership
    const checkResult = await pool.query(
      'SELECT id FROM org_integrations WHERE id = $1 AND organization_id = $2',
      [integrationId, req.organizationId]
    );

    if (checkResult.rows.length === 0) {
      return res.status(404).json({ error: 'Integration not found' });
    }

    const setClauses = [];
    const values = [];
    let paramIndex = 1;

    const fieldMap = {
      name: 'name',
      config: 'config',
      credentials: 'credentials',
      isActive: 'is_active'
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

    values.push(integrationId);

    try {
      const result = await pool.query(
        `UPDATE org_integrations
         SET ${setClauses.join(', ')}, updated_at = NOW()
         WHERE id = $${paramIndex}
         RETURNING id, provider, name, config, is_active, updated_at`,
        values
      );

      const row = result.rows[0];

      res.json({
        integration: {
          id: row.id,
          provider: row.provider,
          name: row.name,
          config: row.config,
          isActive: row.is_active,
          updatedAt: row.updated_at
        }
      });

    } catch (error) {
      console.error('Update integration error:', error);
      res.status(500).json({ error: 'Failed to update integration' });
    }
  }
);

/**
 * DELETE /api/integrations/:id
 * Delete or disable an integration
 *
 * Query: ?hard=true for permanent deletion
 */
router.delete('/:id', verifyToken, async (req, res) => {
  const integrationId = req.params.id;
  const hardDelete = req.query.hard === 'true';

  // Verify ownership
  const checkResult = await pool.query(
    'SELECT id FROM org_integrations WHERE id = $1 AND organization_id = $2',
    [integrationId, req.organizationId]
  );

  if (checkResult.rows.length === 0) {
    return res.status(404).json({ error: 'Integration not found' });
  }

  try {
    if (hardDelete) {
      await pool.query('DELETE FROM org_integrations WHERE id = $1', [integrationId]);
      res.json({ message: 'Integration permanently deleted' });
    } else {
      await pool.query(
        'UPDATE org_integrations SET is_active = FALSE, updated_at = NOW() WHERE id = $1',
        [integrationId]
      );
      res.json({ message: 'Integration disabled' });
    }

  } catch (error) {
    console.error('Delete integration error:', error);
    res.status(500).json({ error: 'Failed to delete integration' });
  }
});

/**
 * POST /api/integrations/:id/enable
 * Enable an integration for a chatbot
 *
 * Body: { chatbotId, settingsOverride? }
 */
router.post('/:id/enable',
  verifyToken,
  body('chatbotId').isUUID().withMessage('Valid chatbot ID is required'),

  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        error: 'Validation failed',
        details: errors.array()
      });
    }

    const integrationId = req.params.id;
    const { chatbotId, settingsOverride } = req.body;

    try {
      // Verify integration belongs to org
      const integrationCheck = await pool.query(
        'SELECT id FROM org_integrations WHERE id = $1 AND organization_id = $2',
        [integrationId, req.organizationId]
      );

      if (integrationCheck.rows.length === 0) {
        return res.status(404).json({ error: 'Integration not found' });
      }

      // Verify chatbot belongs to org
      const chatbotCheck = await pool.query(
        'SELECT id FROM chatbots WHERE id = $1 AND organization_id = $2',
        [chatbotId, req.organizationId]
      );

      if (chatbotCheck.rows.length === 0) {
        return res.status(404).json({ error: 'Chatbot not found' });
      }

      // Insert or update chatbot_integrations
      const result = await pool.query(
        `INSERT INTO chatbot_integrations
         (chatbot_id, integration_id, is_enabled, settings_override)
         VALUES ($1, $2, TRUE, $3)
         ON CONFLICT (chatbot_id, integration_id)
         DO UPDATE SET is_enabled = TRUE, settings_override = $3, updated_at = NOW()
         RETURNING chatbot_id, integration_id, is_enabled, settings_override, created_at`,
        [chatbotId, integrationId, settingsOverride || {}]
      );

      res.json({
        enabled: true,
        chatbotId: result.rows[0].chatbot_id,
        integrationId: result.rows[0].integration_id,
        settingsOverride: result.rows[0].settings_override
      });

    } catch (error) {
      console.error('Enable integration error:', error);
      res.status(500).json({ error: 'Failed to enable integration' });
    }
  }
);

/**
 * POST /api/integrations/:id/disable
 * Disable an integration for a chatbot
 *
 * Body: { chatbotId }
 */
router.post('/:id/disable',
  verifyToken,
  body('chatbotId').isUUID().withMessage('Valid chatbot ID is required'),

  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        error: 'Validation failed',
        details: errors.array()
      });
    }

    const integrationId = req.params.id;
    const { chatbotId } = req.body;

    try {
      const result = await pool.query(
        `UPDATE chatbot_integrations
         SET is_enabled = FALSE, updated_at = NOW()
         WHERE chatbot_id = $1 AND integration_id = $2
         RETURNING chatbot_id, integration_id`,
        [chatbotId, integrationId]
      );

      if (result.rows.length === 0) {
        return res.status(404).json({ error: 'Integration not enabled for this chatbot' });
      }

      res.json({
        disabled: true,
        chatbotId: result.rows[0].chatbot_id,
        integrationId: result.rows[0].integration_id
      });

    } catch (error) {
      console.error('Disable integration error:', error);
      res.status(500).json({ error: 'Failed to disable integration' });
    }
  }
);

module.exports = router;
