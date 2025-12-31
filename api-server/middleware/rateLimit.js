/**
 * Rate Limiting Middleware
 *
 * Provides rate limiting for various API endpoints to prevent abuse.
 * Uses express-rate-limit with configurable limits per endpoint type.
 */

const rateLimit = require('express-rate-limit');

/**
 * Auth endpoints rate limiter
 * - Strict limits to prevent brute force attacks
 * - 5 requests per 15 minutes for login/register
 */
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 5, // 5 requests per window
  message: {
    error: 'Too many authentication attempts, please try again after 15 minutes',
    retryAfter: 900 // seconds
  },
  standardHeaders: true, // Return rate limit info in headers
  legacyHeaders: false, // Disable X-RateLimit-* headers
  skipSuccessfulRequests: false, // Count all requests
  keyGenerator: (req) => {
    // Use IP address as identifier
    return req.ip || req.connection.remoteAddress;
  }
});

/**
 * General API rate limiter
 * - More permissive for authenticated endpoints
 * - 100 requests per minute
 */
const apiLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 100, // 100 requests per minute
  message: {
    error: 'Too many requests, please slow down',
    retryAfter: 60
  },
  standardHeaders: true,
  legacyHeaders: false,
  keyGenerator: (req) => {
    // Use JWT user ID if authenticated, otherwise IP
    return req.user?.id || req.ip || req.connection.remoteAddress;
  }
});

/**
 * Knowledge upload rate limiter
 * - Prevents abuse of resource-intensive upload endpoints
 * - 10 uploads per hour
 */
const uploadLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 hour
  max: 10, // 10 uploads per hour
  message: {
    error: 'Upload limit reached, please try again later',
    retryAfter: 3600
  },
  standardHeaders: true,
  legacyHeaders: false,
  keyGenerator: (req) => {
    return req.organizationId || req.ip;
  }
});

/**
 * Webhook rate limiter
 * - High throughput for WhatsApp webhooks
 * - 1000 requests per minute (matching Phase 0 target)
 */
const webhookLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 1000, // 1000 per minute (~16 req/s)
  message: {
    error: 'Rate limit exceeded',
    retryAfter: 60
  },
  standardHeaders: true,
  legacyHeaders: false,
  keyGenerator: (req) => {
    // Use phone number ID if available, otherwise IP
    return req.body?.entry?.[0]?.changes?.[0]?.value?.metadata?.phone_number_id || req.ip;
  }
});

/**
 * Strict IP-based limiter for security-sensitive operations
 * - 3 requests per hour
 * - For password reset, account deletion, etc.
 */
const strictLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 hour
  max: 3,
  message: {
    error: 'Too many sensitive operations attempted, please try again later',
    retryAfter: 3600
  },
  standardHeaders: true,
  legacyHeaders: false
});

module.exports = {
  authLimiter,
  apiLimiter,
  uploadLimiter,
  webhookLimiter,
  strictLimiter
};
