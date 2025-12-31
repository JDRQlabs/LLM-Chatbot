/**
 * Chatbots Routes
 *
 * Provides CRUD endpoints for managing chatbots.
 */

const express = require('express');
const { body, query, validationResult } = require('express-validator');
const { verifyToken, requireOrganizationAccess, pool } = require('../middleware/auth');

const router = express.Router();

/**
 * GET /api/chatbots
 * List all chatbots for the user's organization
 *
 * Query params: limit (default 20), offset (default 0)
 * Returns: { chatbots: [...], pagination: {...} }
 */
router.get('/',
  verifyToken,
  query('limit').optional().isInt({ min: 1, max: 100 }).toInt(),
  query('offset').optional().isInt({ min: 0 }).toInt(),

  async (req, res) => {
    const limit = req.query.limit || 20;
    const offset = req.query.offset || 0;

    try {
      // Get chatbots
      const result = await pool.query(
        `SELECT
           id, name, whatsapp_phone_number_id, model_name,
           system_prompt, persona, temperature, rag_enabled,
           is_active, created_at, updated_at
         FROM chatbots
         WHERE organization_id = $1
         ORDER BY created_at DESC
         LIMIT $2 OFFSET $3`,
        [req.organizationId, limit, offset]
      );

      // Get total count
      const countResult = await pool.query(
        'SELECT COUNT(*) as total FROM chatbots WHERE organization_id = $1',
        [req.organizationId]
      );

      const total = parseInt(countResult.rows[0].total);

      res.json({
        chatbots: result.rows.map(row => ({
          id: row.id,
          name: row.name,
          phoneNumberId: row.whatsapp_phone_number_id,
          modelName: row.model_name,
          systemPrompt: row.system_prompt,
          persona: row.persona,
          temperature: parseFloat(row.temperature),
          ragEnabled: row.rag_enabled,
          isActive: row.is_active,
          createdAt: row.created_at,
          updatedAt: row.updated_at
        })),
        pagination: {
          limit,
          offset,
          total,
          hasMore: offset + limit < total
        }
      });

    } catch (error) {
      console.error('List chatbots error:', error);
      res.status(500).json({ error: 'Failed to list chatbots' });
    }
  }
);

/**
 * GET /api/chatbots/:id
 * Get a single chatbot by ID
 *
 * Returns: { chatbot: {...} }
 */
router.get('/:id',
  verifyToken,
  requireOrganizationAccess('chatbots'),

  async (req, res) => {
    try {
      const result = await pool.query(
        `SELECT
           c.id, c.name, c.whatsapp_phone_number_id, c.whatsapp_business_account_id,
           c.model_name, c.system_prompt, c.persona, c.temperature,
           c.rag_enabled, c.fallback_message_error, c.fallback_message_limit,
           c.is_active, c.settings, c.created_at, c.updated_at,
           (SELECT COUNT(*) FROM contacts WHERE chatbot_id = c.id) as contact_count,
           (SELECT COUNT(*) FROM knowledge_sources WHERE chatbot_id = c.id) as knowledge_source_count
         FROM chatbots c
         WHERE c.id = $1`,
        [req.params.id]
      );

      if (result.rows.length === 0) {
        return res.status(404).json({ error: 'Chatbot not found' });
      }

      const row = result.rows[0];

      res.json({
        chatbot: {
          id: row.id,
          name: row.name,
          phoneNumberId: row.whatsapp_phone_number_id,
          businessAccountId: row.whatsapp_business_account_id,
          modelName: row.model_name,
          systemPrompt: row.system_prompt,
          persona: row.persona,
          temperature: parseFloat(row.temperature),
          ragEnabled: row.rag_enabled,
          fallbackMessages: {
            error: row.fallback_message_error,
            limit: row.fallback_message_limit
          },
          isActive: row.is_active,
          settings: row.settings,
          stats: {
            contactCount: parseInt(row.contact_count),
            knowledgeSourceCount: parseInt(row.knowledge_source_count)
          },
          createdAt: row.created_at,
          updatedAt: row.updated_at
        }
      });

    } catch (error) {
      console.error('Get chatbot error:', error);
      res.status(500).json({ error: 'Failed to get chatbot' });
    }
  }
);

/**
 * POST /api/chatbots
 * Create a new chatbot
 *
 * Body: { name, phoneNumberId, businessAccountId?, accessToken, systemPrompt?, temperature? }
 * Returns: { chatbot: {...} }
 */
router.post('/',
  verifyToken,
  body('name').trim().notEmpty().withMessage('Name is required'),
  body('phoneNumberId').trim().notEmpty().withMessage('Phone number ID is required'),
  body('accessToken').trim().notEmpty().withMessage('Access token is required'),
  body('systemPrompt').optional().trim(),
  body('temperature').optional().isFloat({ min: 0, max: 2 }).withMessage('Temperature must be between 0 and 2'),

  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        error: 'Validation failed',
        details: errors.array()
      });
    }

    const {
      name,
      phoneNumberId,
      businessAccountId,
      accessToken,
      systemPrompt = 'You are a helpful assistant.',
      temperature = 0.7
    } = req.body;

    try {
      // Check if phone number ID already exists
      const existing = await pool.query(
        'SELECT id FROM chatbots WHERE whatsapp_phone_number_id = $1',
        [phoneNumberId]
      );

      if (existing.rows.length > 0) {
        return res.status(409).json({ error: 'Phone number ID already registered' });
      }

      const result = await pool.query(
        `INSERT INTO chatbots
         (organization_id, name, whatsapp_phone_number_id, whatsapp_business_account_id,
          whatsapp_access_token, system_prompt, temperature, is_active)
         VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
         RETURNING id, name, whatsapp_phone_number_id, model_name, system_prompt,
                   temperature, rag_enabled, is_active, created_at`,
        [req.organizationId, name, phoneNumberId, businessAccountId || null,
         accessToken, systemPrompt, temperature]
      );

      const row = result.rows[0];

      res.status(201).json({
        chatbot: {
          id: row.id,
          name: row.name,
          phoneNumberId: row.whatsapp_phone_number_id,
          modelName: row.model_name,
          systemPrompt: row.system_prompt,
          temperature: parseFloat(row.temperature),
          ragEnabled: row.rag_enabled,
          isActive: row.is_active,
          createdAt: row.created_at
        }
      });

    } catch (error) {
      console.error('Create chatbot error:', error);
      res.status(500).json({ error: 'Failed to create chatbot' });
    }
  }
);

/**
 * PATCH /api/chatbots/:id
 * Update a chatbot
 *
 * Body: { name?, systemPrompt?, persona?, temperature?, ragEnabled?, isActive?, fallbackMessages? }
 * Returns: { chatbot: {...} }
 */
router.patch('/:id',
  verifyToken,
  requireOrganizationAccess('chatbots'),
  body('name').optional().trim().notEmpty(),
  body('systemPrompt').optional().trim(),
  body('persona').optional().trim(),
  body('temperature').optional().isFloat({ min: 0, max: 2 }),
  body('ragEnabled').optional().isBoolean(),
  body('isActive').optional().isBoolean(),

  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        error: 'Validation failed',
        details: errors.array()
      });
    }

    const chatbotId = req.params.id;
    const updates = req.body;

    // Build dynamic update query
    const allowedFields = {
      name: 'name',
      systemPrompt: 'system_prompt',
      persona: 'persona',
      temperature: 'temperature',
      ragEnabled: 'rag_enabled',
      isActive: 'is_active'
    };

    const setClauses = [];
    const values = [];
    let paramIndex = 1;

    for (const [key, dbField] of Object.entries(allowedFields)) {
      if (updates[key] !== undefined) {
        setClauses.push(`${dbField} = $${paramIndex}`);
        values.push(updates[key]);
        paramIndex++;
      }
    }

    // Handle fallback messages separately
    if (updates.fallbackMessages) {
      if (updates.fallbackMessages.error !== undefined) {
        setClauses.push(`fallback_message_error = $${paramIndex}`);
        values.push(updates.fallbackMessages.error);
        paramIndex++;
      }
      if (updates.fallbackMessages.limit !== undefined) {
        setClauses.push(`fallback_message_limit = $${paramIndex}`);
        values.push(updates.fallbackMessages.limit);
        paramIndex++;
      }
    }

    if (setClauses.length === 0) {
      return res.status(400).json({ error: 'No valid fields to update' });
    }

    values.push(chatbotId);

    try {
      const result = await pool.query(
        `UPDATE chatbots
         SET ${setClauses.join(', ')}, updated_at = NOW()
         WHERE id = $${paramIndex}
         RETURNING id, name, whatsapp_phone_number_id, model_name, system_prompt,
                   persona, temperature, rag_enabled, fallback_message_error,
                   fallback_message_limit, is_active, updated_at`,
        values
      );

      if (result.rows.length === 0) {
        return res.status(404).json({ error: 'Chatbot not found' });
      }

      const row = result.rows[0];

      res.json({
        chatbot: {
          id: row.id,
          name: row.name,
          phoneNumberId: row.whatsapp_phone_number_id,
          modelName: row.model_name,
          systemPrompt: row.system_prompt,
          persona: row.persona,
          temperature: parseFloat(row.temperature),
          ragEnabled: row.rag_enabled,
          fallbackMessages: {
            error: row.fallback_message_error,
            limit: row.fallback_message_limit
          },
          isActive: row.is_active,
          updatedAt: row.updated_at
        }
      });

    } catch (error) {
      console.error('Update chatbot error:', error);
      res.status(500).json({ error: 'Failed to update chatbot' });
    }
  }
);

/**
 * DELETE /api/chatbots/:id
 * Delete a chatbot (soft delete by setting is_active = false)
 *
 * Query: ?hard=true for permanent deletion
 */
router.delete('/:id',
  verifyToken,
  requireOrganizationAccess('chatbots'),

  async (req, res) => {
    const chatbotId = req.params.id;
    const hardDelete = req.query.hard === 'true';

    try {
      if (hardDelete) {
        // Permanent deletion - cascades to related tables
        await pool.query('DELETE FROM chatbots WHERE id = $1', [chatbotId]);
        res.json({ message: 'Chatbot permanently deleted' });
      } else {
        // Soft delete
        await pool.query(
          'UPDATE chatbots SET is_active = FALSE, updated_at = NOW() WHERE id = $1',
          [chatbotId]
        );
        res.json({ message: 'Chatbot deactivated' });
      }

    } catch (error) {
      console.error('Delete chatbot error:', error);
      res.status(500).json({ error: 'Failed to delete chatbot' });
    }
  }
);

module.exports = router;
