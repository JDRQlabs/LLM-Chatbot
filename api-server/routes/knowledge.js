/**
 * Knowledge Base API Routes
 *
 * Provides endpoints for managing chatbot knowledge bases:
 * - File uploads, URL ingestion, web crawling
 * - Document management and status tracking
 * - RAG search testing
 */

const express = require('express');
const multer = require('multer');
const { Pool } = require('pg');
const fetch = require('node-fetch');
const { checkQuota } = require('../middleware/quota');

const router = express.Router();

// Database connection pool
const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: process.env.DB_PORT || 5432,
  user: process.env.DB_USER || 'windmill_user',
  password: process.env.DB_PASSWORD || 'changeme',
  database: process.env.DB_NAME || 'windmill',
  max: 20,
  idleTimeoutMillis: 30000,
});

// Windmill configuration
const WINDMILL_URL = process.env.WINDMILL_URL || 'http://localhost:8000';
const WINDMILL_TOKEN = process.env.WINDMILL_TOKEN;
const WINDMILL_WORKSPACE = process.env.WINDMILL_WORKSPACE || 'development';

// File upload configuration (10MB limit)
const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 10 * 1024 * 1024, // 10MB
  },
  fileFilter: (req, file, cb) => {
    const allowedMimeTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // .docx
      'application/msword' // .doc
    ];

    if (allowedMimeTypes.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error('Invalid file type. Only PDF and DOCX files are allowed.'));
    }
  }
});

/**
 * Helper: Call Windmill script
 */
async function callWindmillScript(scriptPath, args) {
  const response = await fetch(
    `${WINDMILL_URL}/api/w/${WINDMILL_WORKSPACE}/jobs/run/p/${scriptPath}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${WINDMILL_TOKEN}`
      },
      body: JSON.stringify(args)
    }
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Windmill API error: ${error}`);
  }

  return await response.json();
}

/**
 * 1. POST /api/chatbots/:id/knowledge/upload
 * Upload PDF or DOCX file
 */
router.post('/:id/knowledge/upload', upload.single('file'), async (req, res, next) => {
  try {
    const { id: chatbotId } = req.params;
    const file = req.file;

    if (!file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }

    const fileSizeMb = file.size / (1024 * 1024);

    // Check quota
    req.body.sourceType = file.mimetype.includes('pdf') ? 'pdf' : 'doc';
    req.body.fileSizeMb = fileSizeMb;
    req.params.chatbotId = chatbotId;

    await checkQuota(req, res, async () => {
      // Call Windmill upload script
      const result = await callWindmillScript('f/development/upload_document', {
        chatbot_id: chatbotId,
        file_content: file.buffer.toString('base64'),
        filename: file.originalname,
        content_type: file.mimetype
      });

      res.json({
        success: true,
        knowledge_source_id: result.knowledge_source_id,
        job_id: result.job_id,
        status: result.status,
        quota: req.quotaInfo
      });
    });

  } catch (error) {
    next(error);
  }
});

/**
 * 2. POST /api/chatbots/:id/knowledge/url
 * Add single URL to knowledge base
 */
router.post('/:id/knowledge/url', async (req, res, next) => {
  try {
    const { id: chatbotId } = req.params;
    const { url } = req.body;

    if (!url) {
      return res.status(400).json({ error: 'Missing URL' });
    }

    // Check quota
    req.body.sourceType = 'url';
    req.params.chatbotId = chatbotId;

    await checkQuota(req, res, async () => {
      // Call batch ingestion with single URL
      const result = await callWindmillScript('f/development/ingest_multiple_urls', {
        chatbot_id: chatbotId,
        urls: [url]
      });

      const urlResult = result.results[0];

      if (!urlResult.success) {
        return res.status(400).json({
          success: false,
          error: urlResult.error
        });
      }

      res.json({
        success: true,
        knowledge_source_id: urlResult.knowledge_source_id,
        job_id: urlResult.job_id,
        quota: req.quotaInfo
      });
    });

  } catch (error) {
    next(error);
  }
});

/**
 * 3. POST /api/chatbots/:id/knowledge/crawl
 * Discover links from base URL
 */
router.post('/:id/knowledge/crawl', async (req, res, next) => {
  try {
    const { id: chatbotId } = req.params;
    const { baseUrl, maxDepth = 2, maxPages = 50, filterKeywords } = req.body;

    if (!baseUrl) {
      return res.status(400).json({ error: 'Missing base URL' });
    }

    // Call web crawler
    const result = await callWindmillScript('f/development/utils/web_crawler', {
      base_url: baseUrl,
      max_depth: maxDepth,
      max_pages: maxPages,
      ...(filterKeywords && { filter_keywords: filterKeywords })
    });

    res.json({
      success: true,
      ...result
    });

  } catch (error) {
    next(error);
  }
});

/**
 * 4. POST /api/chatbots/:id/knowledge/ingest-batch
 * Ingest multiple URLs in batch
 */
router.post('/:id/knowledge/ingest-batch', async (req, res, next) => {
  try {
    const { id: chatbotId } = req.params;
    const { urls } = req.body;

    if (!urls || !Array.isArray(urls) || urls.length === 0) {
      return res.status(400).json({ error: 'Missing or invalid URLs array' });
    }

    // Call batch ingestion
    const result = await callWindmillScript('f/development/ingest_multiple_urls', {
      chatbot_id: chatbotId,
      urls: urls
    });

    res.json({
      success: true,
      ...result
    });

  } catch (error) {
    next(error);
  }
});

/**
 * 5. GET /api/chatbots/:id/knowledge/sources
 * List all knowledge sources (paginated)
 */
router.get('/:id/knowledge/sources', async (req, res, next) => {
  try {
    const { id: chatbotId } = req.params;
    const { page = 1, limit = 20, status, sourceType } = req.query;

    const offset = (page - 1) * limit;

    // Build query
    let query = `
      SELECT
        id,
        source_type,
        source_url,
        source_file_name,
        status,
        error_message,
        file_size_bytes,
        chunk_count,
        created_at,
        updated_at
      FROM knowledge_sources
      WHERE chatbot_id = $1
    `;

    const params = [chatbotId];
    let paramIndex = 2;

    if (status) {
      query += ` AND status = $${paramIndex}`;
      params.push(status);
      paramIndex++;
    }

    if (sourceType) {
      query += ` AND source_type = $${paramIndex}`;
      params.push(sourceType);
      paramIndex++;
    }

    query += ` ORDER BY created_at DESC LIMIT $${paramIndex} OFFSET $${paramIndex + 1}`;
    params.push(limit, offset);

    const result = await pool.query(query, params);

    // Get total count
    const countQuery = `
      SELECT COUNT(*) as total
      FROM knowledge_sources
      WHERE chatbot_id = $1
      ${status ? `AND status = '${status}'` : ''}
      ${sourceType ? `AND source_type = '${sourceType}'` : ''}
    `;
    const countResult = await pool.query(countQuery, [chatbotId]);
    const total = parseInt(countResult.rows[0].total);

    res.json({
      success: true,
      sources: result.rows,
      pagination: {
        page: parseInt(page),
        limit: parseInt(limit),
        total,
        totalPages: Math.ceil(total / limit)
      }
    });

  } catch (error) {
    next(error);
  }
});

/**
 * 6. GET /api/chatbots/:id/knowledge/sources/:sourceId/status
 * Get processing status of a knowledge source
 */
router.get('/:id/knowledge/sources/:sourceId/status', async (req, res, next) => {
  try {
    const { sourceId } = req.params;

    const result = await pool.query(
      `SELECT
        id,
        status,
        error_message,
        chunk_count,
        processing_started_at,
        processing_completed_at,
        created_at,
        updated_at
      FROM knowledge_sources
      WHERE id = $1`,
      [sourceId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Knowledge source not found' });
    }

    const source = result.rows[0];

    // Calculate processing time if applicable
    let processingTimeSeconds = null;
    if (source.processing_started_at && source.processing_completed_at) {
      processingTimeSeconds =
        (new Date(source.processing_completed_at) - new Date(source.processing_started_at)) / 1000;
    }

    res.json({
      success: true,
      source_id: source.id,
      status: source.status,
      error_message: source.error_message,
      chunk_count: source.chunk_count,
      processing_time_seconds: processingTimeSeconds,
      created_at: source.created_at,
      updated_at: source.updated_at
    });

  } catch (error) {
    next(error);
  }
});

/**
 * 7. DELETE /api/chatbots/:id/knowledge/sources/:sourceId
 * Delete a knowledge source
 */
router.delete('/:id/knowledge/sources/:sourceId', async (req, res, next) => {
  try {
    const { id: chatbotId, sourceId } = req.params;

    const client = await pool.connect();

    try {
      await client.query('BEGIN');

      // Verify ownership
      const checkResult = await client.query(
        'SELECT id FROM knowledge_sources WHERE id = $1 AND chatbot_id = $2',
        [sourceId, chatbotId]
      );

      if (checkResult.rows.length === 0) {
        await client.query('ROLLBACK');
        return res.status(404).json({ error: 'Knowledge source not found' });
      }

      // Delete chunks first (foreign key constraint)
      await client.query('DELETE FROM document_chunks WHERE knowledge_source_id = $1', [sourceId]);

      // Delete source
      await client.query('DELETE FROM knowledge_sources WHERE id = $1', [sourceId]);

      await client.query('COMMIT');

      res.json({
        success: true,
        message: 'Knowledge source deleted successfully'
      });

    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }

  } catch (error) {
    next(error);
  }
});

/**
 * 8. POST /api/chatbots/:id/knowledge/search
 * Test RAG search
 */
router.post('/:id/knowledge/search', async (req, res, next) => {
  try {
    const { id: chatbotId } = req.params;
    const { query, limit = 5 } = req.body;

    if (!query) {
      return res.status(400).json({ error: 'Missing search query' });
    }

    // Call retrieve_knowledge function (this would be implemented in a Windmill script)
    // For now, return a placeholder response
    // TODO: Implement actual RAG search via Windmill script

    res.json({
      success: true,
      query,
      results: [],
      message: 'RAG search endpoint - implementation pending'
    });

  } catch (error) {
    next(error);
  }
});

/**
 * 9. GET /api/chatbots/:id/knowledge/quota
 * Get current quota usage
 */
router.get('/:id/knowledge/quota', async (req, res, next) => {
  try {
    const { id: chatbotId } = req.params;

    const result = await pool.query(
      `SELECT
        o.max_knowledge_pdfs,
        o.max_knowledge_urls,
        o.max_knowledge_ingestions_per_day,
        o.max_knowledge_storage_mb,
        o.current_knowledge_pdfs,
        o.current_knowledge_urls,
        o.current_storage_mb,
        COALESCE(dic.ingestion_count, 0) as today_ingestions
      FROM chatbots c
      JOIN organizations o ON c.organization_id = o.id
      LEFT JOIN daily_ingestion_counts dic
        ON dic.organization_id = o.id
        AND dic.date = CURRENT_DATE
      WHERE c.id = $1`,
      [chatbotId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Chatbot not found' });
    }

    const quota = result.rows[0];

    res.json({
      success: true,
      quota: {
        pdfs: {
          current: quota.current_knowledge_pdfs,
          max: quota.max_knowledge_pdfs,
          remaining: quota.max_knowledge_pdfs - quota.current_knowledge_pdfs
        },
        urls: {
          current: quota.current_knowledge_urls,
          max: quota.max_knowledge_urls,
          remaining: quota.max_knowledge_urls - quota.current_knowledge_urls
        },
        storage: {
          current_mb: parseFloat(quota.current_storage_mb),
          max_mb: quota.max_knowledge_storage_mb,
          remaining_mb: quota.max_knowledge_storage_mb - parseFloat(quota.current_storage_mb)
        },
        daily_ingestions: {
          today: quota.today_ingestions,
          max: quota.max_knowledge_ingestions_per_day,
          remaining: quota.max_knowledge_ingestions_per_day - quota.today_ingestions
        }
      }
    });

  } catch (error) {
    next(error);
  }
});

module.exports = router;
