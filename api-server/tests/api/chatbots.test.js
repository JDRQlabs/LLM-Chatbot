/**
 * Chatbots API Tests
 *
 * Tests for chatbot CRUD operations:
 * - GET /api/chatbots
 * - GET /api/chatbots/:id
 * - POST /api/chatbots
 * - PATCH /api/chatbots/:id
 * - DELETE /api/chatbots/:id
 */

const request = require('supertest');
const app = require('../../server');
const { pool } = require('../../middleware/auth');

describe('Chatbots API', () => {
  let authToken;
  let organizationId;
  let testChatbotId;
  const testEmail = `chatbot-test-${Date.now()}@example.com`;

  // Create test user and get token before all tests
  beforeAll(async () => {
    const registerRes = await request(app)
      .post('/api/auth/register')
      .send({
        email: testEmail,
        password: 'TestPassword123!',
        name: 'Chatbot Tester',
        organizationName: 'Chatbot Test Org'
      });

    authToken = registerRes.body.token;
    organizationId = registerRes.body.organization.id;
  });

  // Clean up after all tests
  afterAll(async () => {
    try {
      await pool.query('DELETE FROM chatbots WHERE organization_id = $1', [organizationId]);
      await pool.query('DELETE FROM users WHERE email = $1', [testEmail]);
      await pool.end();
    } catch (error) {
      console.error('Cleanup error:', error);
    }
  });

  describe('POST /api/chatbots', () => {
    it('should create a new chatbot', async () => {
      const res = await request(app)
        .post('/api/chatbots')
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          name: 'Test Chatbot',
          description: 'A test chatbot',
          systemPrompt: 'You are a helpful assistant.',
          temperature: 0.7
        });

      expect(res.statusCode).toBe(201);
      expect(res.body).toHaveProperty('chatbot');
      expect(res.body.chatbot.name).toBe('Test Chatbot');
      expect(res.body.chatbot.description).toBe('A test chatbot');
      expect(res.body.chatbot.systemPrompt).toBe('You are a helpful assistant.');
      expect(res.body.chatbot.temperature).toBe(0.7);

      testChatbotId = res.body.chatbot.id;
    });

    it('should create chatbot with default values', async () => {
      const res = await request(app)
        .post('/api/chatbots')
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          name: 'Minimal Chatbot'
        });

      expect(res.statusCode).toBe(201);
      expect(res.body.chatbot.name).toBe('Minimal Chatbot');
      // Should have default system prompt and temperature
      expect(res.body.chatbot).toHaveProperty('systemPrompt');
      expect(res.body.chatbot).toHaveProperty('temperature');
    });

    it('should reject chatbot creation without name', async () => {
      const res = await request(app)
        .post('/api/chatbots')
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          description: 'Missing name'
        });

      expect(res.statusCode).toBe(400);
      expect(res.body).toHaveProperty('error', 'Validation failed');
    });

    it('should reject invalid temperature values', async () => {
      const res = await request(app)
        .post('/api/chatbots')
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          name: 'Invalid Temp',
          temperature: 3.0  // Max is 2.0
        });

      expect(res.statusCode).toBe(400);
      expect(res.body).toHaveProperty('error', 'Validation failed');
    });

    it('should require authentication', async () => {
      const res = await request(app)
        .post('/api/chatbots')
        .send({
          name: 'Unauthorized Chatbot'
        });

      expect(res.statusCode).toBe(401);
    });
  });

  describe('GET /api/chatbots', () => {
    it('should list all chatbots for organization', async () => {
      const res = await request(app)
        .get('/api/chatbots')
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(200);
      expect(res.body).toHaveProperty('chatbots');
      expect(Array.isArray(res.body.chatbots)).toBe(true);
      expect(res.body.chatbots.length).toBeGreaterThan(0);
    });

    it('should support pagination', async () => {
      const res = await request(app)
        .get('/api/chatbots?limit=1&offset=0')
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(200);
      expect(res.body.chatbots.length).toBeLessThanOrEqual(1);
      expect(res.body).toHaveProperty('pagination');
    });

    it('should require authentication', async () => {
      const res = await request(app)
        .get('/api/chatbots');

      expect(res.statusCode).toBe(401);
    });
  });

  describe('GET /api/chatbots/:id', () => {
    it('should get a single chatbot by ID', async () => {
      const res = await request(app)
        .get(`/api/chatbots/${testChatbotId}`)
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(200);
      expect(res.body).toHaveProperty('chatbot');
      expect(res.body.chatbot.id).toBe(testChatbotId);
      expect(res.body.chatbot.name).toBe('Test Chatbot');
    });

    it('should return 404 for non-existent chatbot', async () => {
      const fakeId = '00000000-0000-0000-0000-000000000000';
      const res = await request(app)
        .get(`/api/chatbots/${fakeId}`)
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(404);
    });

    it('should not access chatbots from other organizations', async () => {
      // Create another user in a different organization
      const otherUserRes = await request(app)
        .post('/api/auth/register')
        .send({
          email: `other-${Date.now()}@example.com`,
          password: 'TestPassword123!',
          name: 'Other User',
          organizationName: 'Other Org'
        });

      const otherToken = otherUserRes.body.token;

      // Try to access the first user's chatbot
      const res = await request(app)
        .get(`/api/chatbots/${testChatbotId}`)
        .set('Authorization', `Bearer ${otherToken}`);

      expect(res.statusCode).toBe(404);

      // Clean up
      await pool.query('DELETE FROM users WHERE email = $1', [otherUserRes.body.user.email]);
    });
  });

  describe('PATCH /api/chatbots/:id', () => {
    it('should update chatbot name', async () => {
      const res = await request(app)
        .patch(`/api/chatbots/${testChatbotId}`)
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          name: 'Updated Chatbot Name'
        });

      expect(res.statusCode).toBe(200);
      expect(res.body.chatbot.name).toBe('Updated Chatbot Name');
    });

    it('should update chatbot system prompt', async () => {
      const res = await request(app)
        .patch(`/api/chatbots/${testChatbotId}`)
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          systemPrompt: 'You are a customer service bot.'
        });

      expect(res.statusCode).toBe(200);
      expect(res.body.chatbot.systemPrompt).toBe('You are a customer service bot.');
    });

    it('should update chatbot temperature', async () => {
      const res = await request(app)
        .patch(`/api/chatbots/${testChatbotId}`)
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          temperature: 0.5
        });

      expect(res.statusCode).toBe(200);
      expect(res.body.chatbot.temperature).toBe(0.5);
    });

    it('should reject invalid temperature update', async () => {
      const res = await request(app)
        .patch(`/api/chatbots/${testChatbotId}`)
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          temperature: 5.0
        });

      expect(res.statusCode).toBe(400);
    });

    it('should return 404 for non-existent chatbot', async () => {
      const fakeId = '00000000-0000-0000-0000-000000000000';
      const res = await request(app)
        .patch(`/api/chatbots/${fakeId}`)
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          name: 'Should Fail'
        });

      expect(res.statusCode).toBe(404);
    });
  });

  describe('DELETE /api/chatbots/:id', () => {
    it('should soft delete a chatbot', async () => {
      const res = await request(app)
        .delete(`/api/chatbots/${testChatbotId}`)
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(200);
      expect(res.body).toHaveProperty('message');
    });

    it('should not find deleted chatbot in list', async () => {
      const res = await request(app)
        .get('/api/chatbots')
        .set('Authorization', `Bearer ${authToken}`);

      const deletedChatbot = res.body.chatbots.find(c => c.id === testChatbotId);
      expect(deletedChatbot).toBeUndefined();
    });

    it('should return 404 for already deleted chatbot', async () => {
      const res = await request(app)
        .delete(`/api/chatbots/${testChatbotId}`)
        .set('Authorization', `Bearer ${authToken}`);

      expect(res.statusCode).toBe(404);
    });
  });
});
