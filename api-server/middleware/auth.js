/**
 * JWT Authentication Middleware
 *
 * Provides JWT token verification and organization access control.
 */

const jwt = require('jsonwebtoken');
const { Pool } = require('pg');

const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-in-production';
const JWT_EXPIRATION = '24h';

// Database connection pool
const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: process.env.DB_PORT || 5432,
  user: process.env.DB_USER || 'business_logic_user',
  password: process.env.DB_PASSWORD || 'business_logic_password',
  database: process.env.DB_NAME || 'business_logic_app',
  max: 20,
  idleTimeoutMillis: 30000,
});

/**
 * Generate a JWT token for a user
 * @param {Object} user - User object with id, email, organization_id
 * @returns {string} JWT token
 */
function generateToken(user) {
  return jwt.sign(
    {
      userId: user.id,
      email: user.email,
      organizationId: user.organization_id,
      role: user.role
    },
    JWT_SECRET,
    { expiresIn: JWT_EXPIRATION }
  );
}

/**
 * Verify JWT token middleware
 * Extracts token from Authorization header and verifies it.
 * Attaches user info to req.user and req.organizationId
 */
function verifyToken(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader) {
    return res.status(401).json({ error: 'No authorization header provided' });
  }

  // Support both "Bearer <token>" and raw token
  const token = authHeader.startsWith('Bearer ')
    ? authHeader.slice(7)
    : authHeader;

  if (!token) {
    return res.status(401).json({ error: 'No token provided' });
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET);

    // Attach user info to request
    req.user = {
      id: decoded.userId,
      email: decoded.email,
      role: decoded.role
    };
    req.organizationId = decoded.organizationId;

    next();
  } catch (error) {
    if (error.name === 'TokenExpiredError') {
      return res.status(401).json({ error: 'Token expired' });
    }
    if (error.name === 'JsonWebTokenError') {
      return res.status(401).json({ error: 'Invalid token' });
    }
    console.error('Token verification error:', error);
    return res.status(401).json({ error: 'Token verification failed' });
  }
}

/**
 * Require organization access middleware
 * Verifies that the resource belongs to the user's organization.
 *
 * Usage:
 *   router.get('/:id', verifyToken, requireOrganizationAccess('chatbots'), handler)
 *
 * @param {string} resourceTable - Table name to check (e.g., 'chatbots')
 * @param {string} idParam - Request param containing resource ID (default: 'id')
 */
function requireOrganizationAccess(resourceTable, idParam = 'id') {
  return async (req, res, next) => {
    const resourceId = req.params[idParam];
    const organizationId = req.organizationId;

    if (!resourceId) {
      return res.status(400).json({ error: `Missing ${idParam} parameter` });
    }

    if (!organizationId) {
      return res.status(401).json({ error: 'Organization ID not found in token' });
    }

    try {
      // Check if resource belongs to user's organization
      const result = await pool.query(
        `SELECT id FROM ${resourceTable} WHERE id = $1 AND organization_id = $2`,
        [resourceId, organizationId]
      );

      if (result.rows.length === 0) {
        return res.status(404).json({
          error: 'Resource not found or access denied'
        });
      }

      // Resource belongs to user's org, continue
      next();
    } catch (error) {
      console.error('Organization access check error:', error);
      return res.status(500).json({ error: 'Failed to verify access' });
    }
  };
}

/**
 * Optional token middleware - doesn't fail if no token
 * Useful for endpoints that work for both authenticated and anonymous users
 */
function optionalToken(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader) {
    return next();
  }

  const token = authHeader.startsWith('Bearer ')
    ? authHeader.slice(7)
    : authHeader;

  if (!token) {
    return next();
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    req.user = {
      id: decoded.userId,
      email: decoded.email,
      role: decoded.role
    };
    req.organizationId = decoded.organizationId;
  } catch (error) {
    // Token invalid, but that's OK for optional auth
  }

  next();
}

module.exports = {
  generateToken,
  verifyToken,
  requireOrganizationAccess,
  optionalToken,
  pool,
  JWT_SECRET,
  JWT_EXPIRATION
};
