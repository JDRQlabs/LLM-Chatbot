/**
 * WhatsApp Chatbot Management API Server
 *
 * Provides REST API for:
 * - Authentication (JWT-based)
 * - Organization management
 * - Chatbot configuration
 * - Conversation history
 * - Integrations/MCP tools
 * - Knowledge base management (RAG)
 */

const express = require('express');
const cors = require('cors');

// Route imports
const authRoutes = require('./routes/auth');
const chatbotsRoutes = require('./routes/chatbots');
const organizationsRoutes = require('./routes/organizations');
const integrationsRoutes = require('./routes/integrations');
const historyRoutes = require('./routes/history');
const knowledgeRoutes = require('./routes/knowledge');

const app = express();
const PORT = process.env.PORT || 4000;

// CORS configuration
const corsOptions = {
  origin: process.env.CORS_ORIGIN || '*',
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
};

// Middleware
app.use(cors(corsOptions));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Request logging
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    console.log(`${new Date().toISOString()} - ${req.method} ${req.path} ${res.statusCode} ${duration}ms`);
  });
  next();
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    service: 'whatsapp-chatbot-api',
    version: '1.0.0'
  });
});

// API routes
app.use('/api/auth', authRoutes);
app.use('/api/organizations', organizationsRoutes);
app.use('/api/chatbots', chatbotsRoutes);
app.use('/api/chatbots', historyRoutes);  // History is nested under chatbots
app.use('/api/chatbots', knowledgeRoutes); // Knowledge is nested under chatbots
app.use('/api/integrations', integrationsRoutes);

// Error handling middleware
app.use((err, req, res, next) => {
  console.error('Error:', err);

  const statusCode = err.statusCode || 500;
  const message = err.message || 'Internal server error';

  res.status(statusCode).json({
    error: message,
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack })
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    error: 'Endpoint not found',
    path: req.path,
    method: req.method
  });
});

// Start server only when run directly (not imported for testing)
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Whatsapp Chatbot API Server running on port ${PORT}`);
    console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
    console.log(`Database host: ${process.env.DB_HOST || 'localhost'}`);
    console.log(`Windmill URL: ${process.env.WINDMILL_URL || 'http://localhost:8000'}`);
  });

  // Graceful shutdown
  process.on('SIGTERM', () => {
    console.log('SIGTERM received, shutting down gracefully...');
    process.exit(0);
  });

  process.on('SIGINT', () => {
    console.log('SIGINT received, shutting down gracefully...');
    process.exit(0);
  });
}

// Export app for testing
module.exports = app;
