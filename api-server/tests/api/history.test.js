/**
 * History API Tests
 *
 * Tests for conversation history endpoints:
 * - GET /api/chatbots/:id/history (cursor-based pagination)
 * - GET /api/chatbots/:id/history/:messageId
 * - GET /api/chatbots/:id/contacts
 */

const request = require('supertest');
const app = require('../../server');
const { pool } = require('../../middleware/auth');

describe('History API', () => {
  let authToken;
  let organizationId;
  let testChatbotId;
  const testEmail = `history-test-${Date.now()}@example.com`;
  const messageIds = [];

  // Create test user, chatbot, and sample messages
  beforeAll(async () => {
    // Register user
    const registerRes = await request(app)
      .post('/api/auth/register')
      .send({
        email: testEmail,
        password: 'TestPassword123!',
        name: 'History Tester',
        organizationName: 'History Test Org'
      });

    authToken = registerRes.body.token;
    organizationId = registerRes.body.organization.id;

    // Create chatbot
    const chatbotRes = await request(app)
      .post('/api/chatbots')
      .set('Authorization', `Bearer ${authToken}`)
      .send({
        name: 'History Test Chatbot',
        description: 'For testing history'
      });

    testChatbotId = chatbotRes.body.chatbot.id;

    // Create sample contacts
    const contact1Result = await pool.query(
      `INSERT INTO contacts (phone_number, organization_id, display_name)
       VALUES ($1, $2, $3)
       RETURNING id`,
      ['+1234567890', organizationId, 'Test Contact 1']
    );
    const contact1Id = contact1Result.rows[0].id;

    const contact2Result = await pool.query(
      `INSERT INTO contacts (phone_number, organization_id, display_name)
       VALUES ($1, $2, $3)
       RETURNING id`,
      ['+0987654321', organizationId, 'Test Contact 2']
    );
    const contact2Id = contact2Result.rows[0].id;

    // Create sample messages (5 messages with delays for proper ordering)
    for (let i = 1; i <= 5; i++) {
      const result = await pool.query(
        `INSERT INTO messages
         (chatbot_id, contact_id, direction, content, created_at)
         VALUES ($1, $2, $3, $4, NOW() - INTERVAL '${6 - i} minutes')
         RETURNING id`,
        [
          testChatbotId,
          i % 2 === 0 ? contact2Id : contact1Id,
          i % 2 === 0 ? 'outbound' : 'inbound',
          `Test message ${i}`
        ]
      );
      messageIds.push(result.rows[0].id);
    }
  });

  // Clean up after all tests
  afterAll(async () => {
    try {
      await pool.query('DELETE FROM messages WHERE chatbot_id = $1', [testChatbotId]);
      await pool.query('DELETE FROM contacts WHERE organization_id = $1', [organizationId]);
      await pool.query('DELETE FROM chatbots WHERE organization_id = $1', [organizationId]);
      await pool.query('DELETE FROM users WHERE email = $1', [testEmail]);
      await pool.end();
    } catch (error) {
      console.error('Cleanup error:', error);
    }
  });

  describe('GET /api/chatbots/:id/history', () => {
    it('should return messages with pagination', async () => {
      const res = await request(app)
        .get(`/api/chatbots/${testChatbotId}/history`)
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(200);
      expect(res.body).toHaveProperty('messages');
      expect(Array.isArray(res.body.messages)).toBe(true);
      expect(res.body.messages.length).toBeGreaterThan(0);
      expect(res.body.messages.length).toBeLessThanOrEqual(50); // Default limit
    });

    it('should respect limit parameter', async () => {
      const res = await request(app)
        .get(`/api/chatbots/${testChatbotId}/history?limit=2`)
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(200);
      expect(res.body.messages.length).toBeLessThanOrEqual(2);
      expect(res.body).toHaveProperty('nextCursor');
    });

    it('should support cursor-based pagination', async () => {
      // Get first page
      const page1 = await request(app)
        .get(`/api/chatbots/${testChatbotId}/history?limit=2`)
        .set('Authorization', `Bearer ${authToken}`);

      expect(page1.statusCode).toBe(200);
      expect(page1.body).toHaveProperty('nextCursor');

      // Get second page using cursor
      const page2 = await request(app)
        .get(`/api/chatbots/${testChatbotId}/history?limit=2&cursor=${page1.body.nextCursor}`)
        .set('Authorization', `Bearer ${authToken}`);

      expect(page2.statusCode).toBe(200);

      // Messages should be different
      const page1Ids = page1.body.messages.map(m => m.id);
      const page2Ids = page2.body.messages.map(m => m.id);
      const overlap = page1Ids.filter(id => page2Ids.includes(id));
      expect(overlap.length).toBe(0);
    });

    it('should return messages in chronological order (newest first)', async () => {
      const res = await request(app)
        .get(`/api/chatbots/${testChatbotId}/history`)
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(200);

      // Check that messages are sorted by created_at descending
      for (let i = 0; i < res.body.messages.length - 1; i++) {
        const currentDate = new Date(res.body.messages[i].createdAt);
        const nextDate = new Date(res.body.messages[i + 1].createdAt);
        expect(currentDate >= nextDate).toBe(true);
      }
    });

    it('should filter by contact if provided', async () => {
      const res = await request(app)
        .get(`/api/chatbots/${testChatbotId}/history?contact=+1234567890`)
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(200);
      // All messages should be from/to the specified contact
      res.body.messages.forEach(msg => {
        expect(msg.contact.phoneNumber).toBe('+1234567890');
      });
    });

    it('should require authentication', async () => {
      const res = await request(app)
        .get(`/api/chatbots/${testChatbotId}/history`);

      expect(res.statusCode).toBe(401);
    });

    it('should return 404 for non-existent chatbot', async () => {
      const fakeId = '00000000-0000-0000-0000-000000000000';
      const res = await request(app)
        .get(`/api/chatbots/${fakeId}/history`)
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(404);
    });

    it('should enforce max limit', async () => {
      const res = await request(app)
        .get(`/api/chatbots/${testChatbotId}/history?limit=500`) // Over max of 200
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(200);
      // Should be capped at 200
      expect(res.body.messages.length).toBeLessThanOrEqual(200);
    });
  });

  describe('GET /api/chatbots/:id/history/:messageId', () => {
    it('should return a single message with context', async () => {
      const messageId = messageIds[2]; // Get middle message

      const res = await request(app)
        .get(`/api/chatbots/${testChatbotId}/history/${messageId}`)
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(200);
      expect(res.body).toHaveProperty('message');
      expect(res.body.message.id).toBe(messageId);
      expect(res.body).toHaveProperty('context');
    });

    it('should return 404 for non-existent message', async () => {
      const fakeId = '00000000-0000-0000-0000-000000000000';
      const res = await request(app)
        .get(`/api/chatbots/${testChatbotId}/history/${fakeId}`)
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(404);
    });
  });

  describe('GET /api/chatbots/:id/contacts', () => {
    it('should list contacts for the chatbot', async () => {
      const res = await request(app)
        .get(`/api/chatbots/${testChatbotId}/contacts`)
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(200);
      expect(res.body).toHaveProperty('contacts');
      expect(Array.isArray(res.body.contacts)).toBe(true);
    });

    it('should require authentication', async () => {
      const res = await request(app)
        .get(`/api/chatbots/${testChatbotId}/contacts`);

      expect(res.statusCode).toBe(401);
    });
  });
});
