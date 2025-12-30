/**
 * Rate Limiting Middleware for WhatsApp Messages
 *
 * Prevents spam and abuse by limiting messages per chatbot based on plan tier:
 * - Free tier: 20 messages/hour
 * - Pro tier: 100 messages/hour
 * - Enterprise tier: 500 messages/hour
 *
 * Uses Redis for distributed rate limiting across multiple server instances.
 */

import { createClient } from 'redis';

// Rate limits per plan tier (messages per hour)
const RATE_LIMITS = {
  free: 20,
  pro: 100,
  enterprise: 500
};

// Redis client
let redisClient = null;

/**
 * Initialize Redis client
 */
export async function initializeRedis() {
  const redisHost = process.env.REDIS_HOST || 'localhost';
  const redisPort = process.env.REDIS_PORT || 6379;

  redisClient = createClient({
    socket: {
      host: redisHost,
      port: redisPort
    }
  });

  redisClient.on('error', (err) => {
    console.error('Redis Client Error:', err);
  });

  redisClient.on('connect', () => {
    console.log(`Redis connected: ${redisHost}:${redisPort}`);
  });

  await redisClient.connect();
}

/**
 * Check rate limit for a chatbot
 *
 * @param {string} phoneNumberId - WhatsApp phone number ID (chatbot identifier)
 * @param {string} planTier - Organization plan tier (free, pro, enterprise)
 * @returns {Promise<{allowed: boolean, current: number, max: number, resetIn: number}>}
 */
export async function checkRateLimit(phoneNumberId, planTier = 'free') {
  if (!redisClient || !redisClient.isOpen) {
    console.warn('Redis not connected, allowing request (fail-open)');
    return {
      allowed: true,
      current: 0,
      max: RATE_LIMITS[planTier] || RATE_LIMITS.free,
      resetIn: 3600
    };
  }

  const maxRequests = RATE_LIMITS[planTier] || RATE_LIMITS.free;
  const windowSeconds = 3600; // 1 hour
  const key = `ratelimit:${phoneNumberId}`;

  try {
    // Use Redis for sliding window rate limit
    const now = Date.now();
    const windowStart = now - (windowSeconds * 1000);

    // Multi-command transaction for atomic rate limit check
    const multi = redisClient.multi();

    // Remove old entries outside the time window
    multi.zRemRangeByScore(key, 0, windowStart);

    // Count current requests in window
    multi.zCard(key);

    // Add current request
    multi.zAdd(key, { score: now, value: now.toString() });

    // Set expiry on the key (cleanup)
    multi.expire(key, windowSeconds);

    const results = await multi.exec();

    // results[1] is the count before adding current request
    const currentCount = results[1];

    if (currentCount >= maxRequests) {
      // Rate limit exceeded
      // Get the oldest request to calculate reset time
      const oldestRequest = await redisClient.zRange(key, 0, 0, { REV: false });
      const resetIn = oldestRequest.length > 0
        ? Math.ceil((parseInt(oldestRequest[0]) + (windowSeconds * 1000) - now) / 1000)
        : windowSeconds;

      return {
        allowed: false,
        current: currentCount,
        max: maxRequests,
        resetIn
      };
    }

    return {
      allowed: true,
      current: currentCount + 1,
      max: maxRequests,
      resetIn: windowSeconds
    };

  } catch (error) {
    console.error('Rate limit check error:', error);
    // Fail open - allow request if Redis has issues
    return {
      allowed: true,
      current: 0,
      max: maxRequests,
      resetIn: windowSeconds
    };
  }
}

/**
 * Close Redis connection
 */
export async function closeRedis() {
  if (redisClient) {
    await redisClient.quit();
  }
}
