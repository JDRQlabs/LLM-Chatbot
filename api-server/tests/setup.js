/**
 * Test Setup
 *
 * Configures Jest with test database connection and mocks.
 * Uses the test database defined in .env.example (port 5434).
 */

// Set test environment variables
process.env.NODE_ENV = 'test';
process.env.JWT_SECRET = 'test-secret-key-for-testing';

// Use test database if available
process.env.DB_HOST = process.env.TEST_DB_HOST || 'localhost';
process.env.DB_PORT = process.env.TEST_DB_PORT || '5434';
process.env.DB_USER = process.env.TEST_DB_USER || 'test_user';
process.env.DB_PASSWORD = process.env.TEST_DB_PASSWORD || 'test_password';
process.env.DB_NAME = process.env.TEST_DB_NAME || 'test_business_logic';

// Windmill mocks
process.env.WINDMILL_URL = 'http://localhost:8000';
process.env.WINDMILL_TOKEN = 'test-token';
process.env.WINDMILL_WORKSPACE = 'development';

// Increase test timeout for database operations
jest.setTimeout(30000);

// Global teardown
afterAll(async () => {
  // Allow connections to close properly
  await new Promise(resolve => setTimeout(resolve, 100));
});
