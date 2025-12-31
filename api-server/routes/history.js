/**
 * Chat History Routes
 *
 * Provides endpoints for accessing chatbot conversation history
 * with cursor-based pagination for efficient large dataset handling.
 */

const express = require('express');
const { query, validationResult } = require('express-validator');
const { verifyToken, requireOrganizationAccess, pool } = require('../middleware/auth');

const router = express.Router();

// Maximum messages per page
const MAX_LIMIT = 200;
const DEFAULT_LIMIT = 50;

/**
 * Encode cursor from created_at timestamp and message id
 */
function encodeCursor(createdAt, id) {
  const data = JSON.stringify({ t: createdAt.toISOString(), i: id });
  return Buffer.from(data).toString('base64');
}

/**
 * Decode cursor to get timestamp and id
 */
function decodeCursor(cursor) {
  try {
    const data = JSON.parse(Buffer.from(cursor, 'base64').toString());
    return { createdAt: new Date(data.t), id: data.i };
  } catch (e) {
    return null;
  }
}

/**
 * GET /api/chatbots/:chatbotId/history
 * Get conversation history for a chatbot with cursor-based pagination
 *
 * Query params:
 *   - limit: Number of messages (1-200, default 50)
 *   - cursor: Pagination cursor for next page
 *   - contactId: Filter by specific contact (optional)
 *   - startDate: Filter messages after this date (optional)
 *   - endDate: Filter messages before this date (optional)
 *
 * Returns: { messages: [...], nextCursor: "...", hasMore: bool }
 */
router.get('/:chatbotId/history',
  verifyToken,
  requireOrganizationAccess('chatbots', 'chatbotId'),
  query('limit').optional().isInt({ min: 1, max: MAX_LIMIT }).toInt(),
  query('cursor').optional().isString(),
  query('contactId').optional().isUUID(),
  query('startDate').optional().isISO8601(),
  query('endDate').optional().isISO8601(),

  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        error: 'Validation failed',
        details: errors.array()
      });
    }

    const chatbotId = req.params.chatbotId;
    const limit = Math.min(req.query.limit || DEFAULT_LIMIT, MAX_LIMIT);
    const cursor = req.query.cursor;
    const contactId = req.query.contactId;
    const startDate = req.query.startDate;
    const endDate = req.query.endDate;

    try {
      // Build query with optional filters
      let whereClause = 'c.chatbot_id = $1';
      const params = [chatbotId];
      let paramIndex = 2;

      // Handle cursor-based pagination
      if (cursor) {
        const cursorData = decodeCursor(cursor);
        if (!cursorData) {
          return res.status(400).json({ error: 'Invalid cursor' });
        }
        whereClause += ` AND (m.created_at, m.id) < ($${paramIndex}, $${paramIndex + 1})`;
        params.push(cursorData.createdAt, cursorData.id);
        paramIndex += 2;
      }

      // Optional contact filter
      if (contactId) {
        whereClause += ` AND c.id = $${paramIndex}`;
        params.push(contactId);
        paramIndex++;
      }

      // Optional date range filters
      if (startDate) {
        whereClause += ` AND m.created_at >= $${paramIndex}`;
        params.push(startDate);
        paramIndex++;
      }

      if (endDate) {
        whereClause += ` AND m.created_at <= $${paramIndex}`;
        params.push(endDate);
        paramIndex++;
      }

      // Fetch messages (limit + 1 to check if there are more)
      params.push(limit + 1);

      const result = await pool.query(
        `SELECT
           m.id,
           m.contact_id,
           m.role,
           m.content,
           m.whatsapp_message_id,
           m.tool_calls,
           m.tool_results,
           m.created_at,
           c.phone_number as contact_phone,
           c.name as contact_name
         FROM messages m
         JOIN contacts c ON m.contact_id = c.id
         WHERE ${whereClause}
         ORDER BY m.created_at DESC, m.id DESC
         LIMIT $${paramIndex}`,
        params
      );

      // Check if there are more results
      const hasMore = result.rows.length > limit;
      const messages = hasMore ? result.rows.slice(0, limit) : result.rows;

      // Generate next cursor if there are more results
      let nextCursor = null;
      if (hasMore && messages.length > 0) {
        const lastMessage = messages[messages.length - 1];
        nextCursor = encodeCursor(lastMessage.created_at, lastMessage.id);
      }

      res.json({
        messages: messages.map(row => ({
          id: row.id,
          contactId: row.contact_id,
          contactPhone: row.contact_phone,
          contactName: row.contact_name,
          role: row.role,
          content: row.content,
          whatsappMessageId: row.whatsapp_message_id,
          toolCalls: row.tool_calls,
          toolResults: row.tool_results,
          createdAt: row.created_at
        })),
        nextCursor,
        hasMore
      });

    } catch (error) {
      console.error('Get history error:', error);
      res.status(500).json({ error: 'Failed to get history' });
    }
  }
);

/**
 * GET /api/chatbots/:chatbotId/history/:messageId
 * Get a single message with context (surrounding messages)
 *
 * Query params:
 *   - context: Number of surrounding messages to include (default 5)
 *
 * Returns: { message: {...}, context: [...] }
 */
router.get('/:chatbotId/history/:messageId',
  verifyToken,
  requireOrganizationAccess('chatbots', 'chatbotId'),
  query('context').optional().isInt({ min: 0, max: 20 }).toInt(),

  async (req, res) => {
    const chatbotId = req.params.chatbotId;
    const messageId = req.params.messageId;
    const contextSize = req.query.context || 5;

    try {
      // Get the target message
      const messageResult = await pool.query(
        `SELECT
           m.id, m.contact_id, m.role, m.content, m.whatsapp_message_id,
           m.tool_calls, m.tool_results, m.created_at,
           c.phone_number as contact_phone, c.name as contact_name
         FROM messages m
         JOIN contacts c ON m.contact_id = c.id
         WHERE m.id = $1 AND c.chatbot_id = $2`,
        [messageId, chatbotId]
      );

      if (messageResult.rows.length === 0) {
        return res.status(404).json({ error: 'Message not found' });
      }

      const message = messageResult.rows[0];

      // Get context messages (before and after)
      const contextResult = await pool.query(
        `(
           SELECT m.id, m.role, m.content, m.created_at, 'before' as position
           FROM messages m
           WHERE m.contact_id = $1 AND m.created_at < $2
           ORDER BY m.created_at DESC
           LIMIT $3
         )
         UNION ALL
         (
           SELECT m.id, m.role, m.content, m.created_at, 'after' as position
           FROM messages m
           WHERE m.contact_id = $1 AND m.created_at > $2
           ORDER BY m.created_at ASC
           LIMIT $3
         )
         ORDER BY created_at`,
        [message.contact_id, message.created_at, contextSize]
      );

      res.json({
        message: {
          id: message.id,
          contactId: message.contact_id,
          contactPhone: message.contact_phone,
          contactName: message.contact_name,
          role: message.role,
          content: message.content,
          whatsappMessageId: message.whatsapp_message_id,
          toolCalls: message.tool_calls,
          toolResults: message.tool_results,
          createdAt: message.created_at
        },
        context: contextResult.rows.map(row => ({
          id: row.id,
          role: row.role,
          content: row.content,
          createdAt: row.created_at,
          position: row.position
        }))
      });

    } catch (error) {
      console.error('Get message error:', error);
      res.status(500).json({ error: 'Failed to get message' });
    }
  }
);

/**
 * GET /api/chatbots/:chatbotId/contacts
 * List all contacts for a chatbot
 *
 * Query params:
 *   - limit, offset: Pagination
 *   - search: Search by name or phone
 *
 * Returns: { contacts: [...], pagination: {...} }
 */
router.get('/:chatbotId/contacts',
  verifyToken,
  requireOrganizationAccess('chatbots', 'chatbotId'),
  query('limit').optional().isInt({ min: 1, max: 100 }).toInt(),
  query('offset').optional().isInt({ min: 0 }).toInt(),
  query('search').optional().isString().trim(),

  async (req, res) => {
    const chatbotId = req.params.chatbotId;
    const limit = req.query.limit || 20;
    const offset = req.query.offset || 0;
    const search = req.query.search;

    try {
      let whereClause = 'chatbot_id = $1';
      const params = [chatbotId];
      let paramIndex = 2;

      if (search) {
        whereClause += ` AND (name ILIKE $${paramIndex} OR phone_number ILIKE $${paramIndex})`;
        params.push(`%${search}%`);
        paramIndex++;
      }

      params.push(limit, offset);

      const result = await pool.query(
        `SELECT
           id, phone_number, name, conversation_mode,
           unread_count, variables, tags, last_message_at,
           created_at, updated_at
         FROM contacts
         WHERE ${whereClause}
         ORDER BY last_message_at DESC
         LIMIT $${paramIndex} OFFSET $${paramIndex + 1}`,
        params
      );

      // Get total count
      const countResult = await pool.query(
        `SELECT COUNT(*) as total FROM contacts WHERE ${whereClause}`,
        params.slice(0, paramIndex - 1)
      );

      const total = parseInt(countResult.rows[0].total);

      res.json({
        contacts: result.rows.map(row => ({
          id: row.id,
          phoneNumber: row.phone_number,
          name: row.name,
          conversationMode: row.conversation_mode,
          unreadCount: row.unread_count,
          variables: row.variables,
          tags: row.tags,
          lastMessageAt: row.last_message_at,
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
      console.error('List contacts error:', error);
      res.status(500).json({ error: 'Failed to list contacts' });
    }
  }
);

module.exports = router;
