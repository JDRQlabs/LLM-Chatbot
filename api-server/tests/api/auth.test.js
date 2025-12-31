/**
 * Auth API Tests
 *
 * Tests for authentication endpoints:
 * - POST /api/auth/register
 * - POST /api/auth/login
 * - GET /api/auth/me
 */

const request = require('supertest');
const jwt = require('jsonwebtoken');
const app = require('../../server');
const { pool } = require('../../middleware/auth');

describe('Auth API', () => {
  let testToken;
  let testUserId;
  const testEmail = `test-${Date.now()}@example.com`;
  const testPassword = 'TestPassword123!';

  // Clean up test data after all tests
  afterAll(async () => {
    try {
      // Delete test user and organization if they exist
      await pool.query('DELETE FROM users WHERE email = $1', [testEmail]);
      await pool.end();
    } catch (error) {
      console.error('Cleanup error:', error);
    }
  });

  describe('POST /api/auth/register', () => {
    it('should register a new user and return JWT token', async () => {
      const res = await request(app)
        .post('/api/auth/register')
        .send({
          email: testEmail,
          password: testPassword,
          name: 'Test User',
          organizationName: 'Test Organization'
        });

      expect(res.statusCode).toBe(201);
      expect(res.body).toHaveProperty('token');
      expect(res.body).toHaveProperty('user');
      expect(res.body.user.email).toBe(testEmail);
      expect(res.body.user.name).toBe('Test User');
      expect(res.body).toHaveProperty('organization');
      expect(res.body.organization.name).toBe('Test Organization');

      // Save for later tests
      testToken = res.body.token;
      testUserId = res.body.user.id;

      // Verify JWT is valid
      const decoded = jwt.verify(testToken, process.env.JWT_SECRET);
      expect(decoded).toHaveProperty('userId');
      expect(decoded).toHaveProperty('organizationId');
    });

    it('should reject registration with invalid email', async () => {
      const res = await request(app)
        .post('/api/auth/register')
        .send({
          email: 'invalid-email',
          password: testPassword,
          name: 'Test User'
        });

      expect(res.statusCode).toBe(400);
      expect(res.body).toHaveProperty('error', 'Validation failed');
    });

    it('should reject registration with short password', async () => {
      const res = await request(app)
        .post('/api/auth/register')
        .send({
          email: 'valid@example.com',
          password: 'short',
          name: 'Test User'
        });

      expect(res.statusCode).toBe(400);
      expect(res.body).toHaveProperty('error', 'Validation failed');
    });

    it('should reject duplicate email registration', async () => {
      const res = await request(app)
        .post('/api/auth/register')
        .send({
          email: testEmail,
          password: testPassword,
          name: 'Duplicate User'
        });

      expect(res.statusCode).toBe(409);
      expect(res.body).toHaveProperty('error', 'Email already registered');
    });
  });

  describe('POST /api/auth/login', () => {
    it('should login with valid credentials', async () => {
      const res = await request(app)
        .post('/api/auth/login')
        .send({
          email: testEmail,
          password: testPassword
        });

      expect(res.statusCode).toBe(200);
      expect(res.body).toHaveProperty('token');
      expect(res.body).toHaveProperty('user');
      expect(res.body.user.email).toBe(testEmail);

      // Update token for subsequent tests
      testToken = res.body.token;
    });

    it('should reject login with invalid password', async () => {
      const res = await request(app)
        .post('/api/auth/login')
        .send({
          email: testEmail,
          password: 'WrongPassword123!'
        });

      expect(res.statusCode).toBe(401);
      expect(res.body).toHaveProperty('error', 'Invalid credentials');
    });

    it('should reject login with non-existent email', async () => {
      const res = await request(app)
        .post('/api/auth/login')
        .send({
          email: 'nonexistent@example.com',
          password: testPassword
        });

      expect(res.statusCode).toBe(401);
      expect(res.body).toHaveProperty('error', 'Invalid credentials');
    });
  });

  describe('GET /api/auth/me', () => {
    it('should return current user with valid token', async () => {
      const res = await request(app)
        .get('/api/auth/me')
        .set('Authorization', `Bearer ${testToken}`);

      expect(res.statusCode).toBe(200);
      expect(res.body).toHaveProperty('user');
      expect(res.body.user.email).toBe(testEmail);
      expect(res.body).toHaveProperty('organization');
    });

    it('should reject request without token', async () => {
      const res = await request(app)
        .get('/api/auth/me');

      expect(res.statusCode).toBe(401);
      expect(res.body).toHaveProperty('error');
    });

    it('should reject request with invalid token', async () => {
      const res = await request(app)
        .get('/api/auth/me')
        .set('Authorization', 'Bearer invalid-token-here');

      expect(res.statusCode).toBe(401);
      expect(res.body).toHaveProperty('error');
    });

    it('should reject request with expired token', async () => {
      // Create an expired token
      const expiredToken = jwt.sign(
        { userId: testUserId, organizationId: 'test-org-id' },
        process.env.JWT_SECRET,
        { expiresIn: '-1h' }
      );

      const res = await request(app)
        .get('/api/auth/me')
        .set('Authorization', `Bearer ${expiredToken}`);

      expect(res.statusCode).toBe(401);
      expect(res.body).toHaveProperty('error');
    });
  });
});
