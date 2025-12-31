/**
 * Authentication Routes
 *
 * Provides user registration, login, and profile endpoints.
 * Rate limited to prevent brute force attacks.
 */

const express = require('express');
const bcrypt = require('bcrypt');
const { body, validationResult } = require('express-validator');
const { generateToken, verifyToken, pool } = require('../middleware/auth');
const { authLimiter } = require('../middleware/rateLimit');

const router = express.Router();

// Password hashing configuration
const SALT_ROUNDS = 12;

/**
 * POST /api/auth/register
 * Register a new user and organization
 *
 * SECURITY: Public registration is DISABLED in Phase 0.
 * Admin accounts must be created via SSH using: make create-admin
 *
 * Phase 1 will implement email verification + admin approval workflow.
 * See TODO.md for details.
 *
 * Body: { email, password, fullName, organizationName }
 * Returns: { token, user, organization }
 */
router.post('/register',
  // Rate limiting
  authLimiter,

  async (req, res) => {
    // SECURITY: Public registration disabled for Phase 0
    // Use `make create-admin EMAIL=... PASSWORD=...` via SSH instead
    return res.status(403).json({
      error: 'Public registration is disabled',
      message: 'Contact an administrator to create an account'
    });
  }
);

/**
 * DISABLED - Original registration implementation
 * TODO: Re-enable with email verification in Phase 1
 */
const _disabledRegister = router.post('/register-disabled',
  // Rate limiting
  authLimiter,
  // Validation
  body('email').isEmail().normalizeEmail().withMessage('Valid email is required'),
  body('password').isLength({ min: 8 }).withMessage('Password must be at least 8 characters'),
  body('fullName').trim().notEmpty().withMessage('Full name is required'),
  body('organizationName').trim().notEmpty().withMessage('Organization name is required'),

  async (req, res) => {
    // Check validation errors
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        error: 'Validation failed',
        details: errors.array()
      });
    }

    const { email, password, fullName, organizationName } = req.body;

    const client = await pool.connect();

    try {
      await client.query('BEGIN');

      // Check if email already exists
      const existingUser = await client.query(
        'SELECT id FROM users WHERE email = $1',
        [email]
      );

      if (existingUser.rows.length > 0) {
        await client.query('ROLLBACK');
        return res.status(409).json({ error: 'Email already registered' });
      }

      // Create organization
      const orgSlug = organizationName
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
        .substring(0, 50);

      const orgResult = await client.query(
        `INSERT INTO organizations (name, slug, plan_tier, is_active)
         VALUES ($1, $2, 'free', TRUE)
         RETURNING id, name, slug, plan_tier, message_limit_monthly, token_limit_monthly`,
        [organizationName, orgSlug + '-' + Date.now().toString(36)]
      );

      const organization = orgResult.rows[0];

      // Hash password
      const passwordHash = await bcrypt.hash(password, SALT_ROUNDS);

      // Create user as owner
      const userResult = await client.query(
        `INSERT INTO users (organization_id, email, password_hash, full_name, role)
         VALUES ($1, $2, $3, $4, 'owner')
         RETURNING id, email, full_name, role, organization_id, created_at`,
        [organization.id, email, passwordHash, fullName]
      );

      const user = userResult.rows[0];

      // Initialize usage summary for the organization
      await client.query(
        `INSERT INTO usage_summary (organization_id, current_period_messages, current_period_tokens, period_start, period_end)
         VALUES ($1, 0, 0, CURRENT_DATE, CURRENT_DATE + INTERVAL '1 month')
         ON CONFLICT (organization_id) DO NOTHING`,
        [organization.id]
      );

      await client.query('COMMIT');

      // Generate JWT token
      const token = generateToken(user);

      res.status(201).json({
        token,
        user: {
          id: user.id,
          email: user.email,
          fullName: user.full_name,
          role: user.role
        },
        organization: {
          id: organization.id,
          name: organization.name,
          slug: organization.slug,
          planTier: organization.plan_tier
        }
      });

    } catch (error) {
      await client.query('ROLLBACK');
      console.error('Registration error:', error);
      res.status(500).json({ error: 'Registration failed' });
    } finally {
      client.release();
    }
  }
);

/**
 * POST /api/auth/login
 * Authenticate user and return JWT token
 *
 * Body: { email, password }
 * Returns: { token, user, organization }
 */
router.post('/login',
  // Rate limiting
  authLimiter,
  // Validation
  body('email').isEmail().normalizeEmail().withMessage('Valid email is required'),
  body('password').notEmpty().withMessage('Password is required'),

  async (req, res) => {
    // Check validation errors
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        error: 'Validation failed',
        details: errors.array()
      });
    }

    const { email, password } = req.body;

    try {
      // Find user by email with organization info
      const result = await pool.query(
        `SELECT
           u.id, u.email, u.password_hash, u.full_name, u.role, u.organization_id,
           o.name as org_name, o.slug as org_slug, o.plan_tier
         FROM users u
         JOIN organizations o ON u.organization_id = o.id
         WHERE u.email = $1 AND o.is_active = TRUE`,
        [email]
      );

      if (result.rows.length === 0) {
        return res.status(401).json({ error: 'Invalid email or password' });
      }

      const user = result.rows[0];

      // Verify password
      const validPassword = await bcrypt.compare(password, user.password_hash);

      if (!validPassword) {
        return res.status(401).json({ error: 'Invalid email or password' });
      }

      // Update last login
      await pool.query(
        'UPDATE users SET last_login_at = NOW() WHERE id = $1',
        [user.id]
      );

      // Generate JWT token
      const token = generateToken({
        id: user.id,
        email: user.email,
        organization_id: user.organization_id,
        role: user.role
      });

      res.json({
        token,
        user: {
          id: user.id,
          email: user.email,
          fullName: user.full_name,
          role: user.role
        },
        organization: {
          id: user.organization_id,
          name: user.org_name,
          slug: user.org_slug,
          planTier: user.plan_tier
        }
      });

    } catch (error) {
      console.error('Login error:', error);
      res.status(500).json({ error: 'Login failed' });
    }
  }
);

/**
 * GET /api/auth/me
 * Get current user profile
 *
 * Requires: JWT token in Authorization header
 * Returns: { user, organization }
 */
router.get('/me', verifyToken, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT
         u.id, u.email, u.full_name, u.role, u.created_at, u.last_login_at,
         o.id as org_id, o.name as org_name, o.slug as org_slug,
         o.plan_tier, o.message_limit_monthly, o.token_limit_monthly,
         o.billing_period_start, o.billing_period_end
       FROM users u
       JOIN organizations o ON u.organization_id = o.id
       WHERE u.id = $1`,
      [req.user.id]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'User not found' });
    }

    const data = result.rows[0];

    // Get current usage
    const usageResult = await pool.query(
      `SELECT current_period_messages, current_period_tokens
       FROM usage_summary
       WHERE organization_id = $1`,
      [data.org_id]
    );

    const usage = usageResult.rows[0] || { current_period_messages: 0, current_period_tokens: 0 };

    res.json({
      user: {
        id: data.id,
        email: data.email,
        fullName: data.full_name,
        role: data.role,
        createdAt: data.created_at,
        lastLoginAt: data.last_login_at
      },
      organization: {
        id: data.org_id,
        name: data.org_name,
        slug: data.org_slug,
        planTier: data.plan_tier,
        limits: {
          messagesMonthly: data.message_limit_monthly,
          tokensMonthly: data.token_limit_monthly
        },
        usage: {
          messagesUsed: usage.current_period_messages,
          tokensUsed: usage.current_period_tokens
        },
        billingPeriod: {
          start: data.billing_period_start,
          end: data.billing_period_end
        }
      }
    });

  } catch (error) {
    console.error('Get profile error:', error);
    res.status(500).json({ error: 'Failed to get profile' });
  }
});

module.exports = router;
