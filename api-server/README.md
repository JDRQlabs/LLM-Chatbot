# FastBots.ai Knowledge Base API

REST API for managing chatbot knowledge bases with PDF/DOCX uploads, URL ingestion, web crawling, and RAG search.

## Base URL

```
http://localhost:4000
```

## Endpoints

### 1. Upload File (PDF/DOCX)

Upload a PDF or DOCX document to the knowledge base.

**Request:**
```http
POST /api/chatbots/:id/knowledge/upload
Content-Type: multipart/form-data

file: <binary file data>
```

**Response:**
```json
{
  "success": true,
  "knowledge_source_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_id": "abc-123-def",
  "status": "pending",
  "quota": {
    "allowed": true,
    "current": 5,
    "max": 50,
    "remaining": 45
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:4000/api/chatbots/YOUR_CHATBOT_ID/knowledge/upload \
  -F "file=@document.pdf"
```

**Status Codes:**
- `200 OK` - File uploaded successfully
- `400 Bad Request` - No file provided or invalid file type
- `403 Forbidden` - Quota exceeded
- `413 Payload Too Large` - File exceeds 10MB limit

---

### 2. Add Single URL

Add a single URL to the knowledge base.

**Request:**
```http
POST /api/chatbots/:id/knowledge/url
Content-Type: application/json

{
  "url": "https://example.com/page"
}
```

**Response:**
```json
{
  "success": true,
  "knowledge_source_id": "550e8400-e29b-41d4-a716-446655440001",
  "job_id": "xyz-789-ghi",
  "quota": {
    "allowed": true,
    "current": 2,
    "max": 20,
    "remaining": 18
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:4000/api/chatbots/YOUR_CHATBOT_ID/knowledge/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.example.com/faq"}'
```

---

### 3. Crawl Website

Discover relevant links from a base URL.

**Request:**
```http
POST /api/chatbots/:id/knowledge/crawl
Content-Type: application/json

{
  "baseUrl": "https://example.com",
  "maxDepth": 2,
  "maxPages": 50,
  "filterKeywords": ["faq", "docs", "support"]
}
```

**Response:**
```json
{
  "success": true,
  "discovered_urls": [
    {
      "url": "https://example.com/faq",
      "title": "Frequently Asked Questions",
      "relevance_score": 0.7,
      "depth": 1,
      "content_preview": "Q: How do I get started? A: First, create an account...",
      "suggested": true
    },
    {
      "url": "https://example.com/docs",
      "title": "Documentation",
      "relevance_score": 0.65,
      "depth": 1,
      "content_preview": "Welcome to our documentation. Here you will find...",
      "suggested": true
    }
  ],
  "total_discovered": 15,
  "crawl_time_seconds": 18.5,
  "base_domain": "example.com",
  "robots_txt_respected": true
}
```

**Example:**
```bash
curl -X POST http://localhost:4000/api/chatbots/YOUR_CHATBOT_ID/knowledge/crawl \
  -H "Content-Type: application/json" \
  -d '{
    "baseUrl": "https://docs.example.com",
    "maxDepth": 2,
    "maxPages": 30
  }'
```

**Parameters:**
- `baseUrl` (required) - Starting URL to crawl
- `maxDepth` (optional, default: 2) - Maximum crawl depth
- `maxPages` (optional, default: 50) - Maximum pages to discover
- `filterKeywords` (optional) - Keywords to boost relevance scoring

---

### 4. Ingest Batch URLs

Ingest multiple URLs discovered from crawling.

**Request:**
```http
POST /api/chatbots/:id/knowledge/ingest-batch
Content-Type: application/json

{
  "urls": [
    "https://example.com/faq",
    "https://example.com/docs",
    "https://example.com/support"
  ]
}
```

**Response:**
```json
{
  "success": true,
  "total_urls": 3,
  "successful": 3,
  "failed": 0,
  "results": [
    {
      "url": "https://example.com/faq",
      "success": true,
      "knowledge_source_id": "550e8400-e29b-41d4-a716-446655440002",
      "job_id": "job-123",
      "quota_info": {
        "allowed": true,
        "current": 3,
        "max": 20,
        "remaining": 17
      }
    },
    {
      "url": "https://example.com/docs",
      "success": true,
      "knowledge_source_id": "550e8400-e29b-41d4-a716-446655440003",
      "job_id": "job-124",
      "quota_info": {
        "allowed": true,
        "current": 4,
        "max": 20,
        "remaining": 16
      }
    }
  ],
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

**Example:**
```bash
curl -X POST http://localhost:4000/api/chatbots/YOUR_CHATBOT_ID/knowledge/ingest-batch \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://example.com/faq",
      "https://example.com/docs"
    ]
  }'
```

---

### 5. List Knowledge Sources

Get all knowledge sources for a chatbot with pagination and filtering.

**Request:**
```http
GET /api/chatbots/:id/knowledge/sources?page=1&limit=20&status=synced&sourceType=url
```

**Query Parameters:**
- `page` (optional, default: 1) - Page number
- `limit` (optional, default: 20) - Results per page
- `status` (optional) - Filter by status: `pending`, `processing`, `synced`, `failed`
- `sourceType` (optional) - Filter by type: `pdf`, `doc`, `url`

**Response:**
```json
{
  "success": true,
  "sources": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "source_type": "url",
      "source_url": "https://example.com/faq",
      "source_file_name": null,
      "status": "synced",
      "error_message": null,
      "file_size_bytes": 15360,
      "chunk_count": 12,
      "created_at": "2024-01-15T10:00:00.000Z",
      "updated_at": "2024-01-15T10:02:30.000Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 25,
    "totalPages": 2
  }
}
```

**Example:**
```bash
curl http://localhost:4000/api/chatbots/YOUR_CHATBOT_ID/knowledge/sources?page=1&limit=10
```

---

### 6. Get Source Status

Get detailed processing status for a specific knowledge source.

**Request:**
```http
GET /api/chatbots/:id/knowledge/sources/:sourceId/status
```

**Response:**
```json
{
  "success": true,
  "source_id": "550e8400-e29b-41d4-a716-446655440002",
  "status": "synced",
  "error_message": null,
  "chunk_count": 12,
  "processing_time_seconds": 8.5,
  "created_at": "2024-01-15T10:00:00.000Z",
  "updated_at": "2024-01-15T10:02:30.000Z"
}
```

**Example:**
```bash
curl http://localhost:4000/api/chatbots/YOUR_CHATBOT_ID/knowledge/sources/550e8400-e29b-41d4-a716-446655440002/status
```

**Status Values:**
- `pending` - Queued for processing
- `processing` - Currently being processed
- `synced` - Successfully processed and ready
- `failed` - Processing failed (see error_message)

---

### 7. Delete Knowledge Source

Delete a knowledge source and all its associated chunks.

**Request:**
```http
DELETE /api/chatbots/:id/knowledge/sources/:sourceId
```

**Response:**
```json
{
  "success": true,
  "message": "Knowledge source deleted successfully"
}
```

**Example:**
```bash
curl -X DELETE http://localhost:4000/api/chatbots/YOUR_CHATBOT_ID/knowledge/sources/550e8400-e29b-41d4-a716-446655440002
```

**Status Codes:**
- `200 OK` - Source deleted successfully
- `404 Not Found` - Source not found or doesn't belong to this chatbot

---

### 8. Test RAG Search

Test RAG search functionality to see what context would be retrieved.

**Request:**
```http
POST /api/chatbots/:id/knowledge/search
Content-Type: application/json

{
  "query": "How do I get started?",
  "limit": 5
}
```

**Response:**
```json
{
  "success": true,
  "query": "How do I get started?",
  "results": [],
  "message": "RAG search endpoint - implementation pending"
}
```

**Example:**
```bash
curl -X POST http://localhost:4000/api/chatbots/YOUR_CHATBOT_ID/knowledge/search \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I reset my password?", "limit": 5}'
```

**Note:** This endpoint is currently a placeholder. RAG search will be fully implemented in a future update.

---

### 9. Get Quota Usage

Get current quota usage for the chatbot's organization.

**Request:**
```http
GET /api/chatbots/:id/knowledge/quota
```

**Response:**
```json
{
  "success": true,
  "quota": {
    "pdfs": {
      "current": 5,
      "max": 50,
      "remaining": 45
    },
    "urls": {
      "current": 12,
      "max": 20,
      "remaining": 8
    },
    "storage": {
      "current_mb": 45.3,
      "max_mb": 500,
      "remaining_mb": 454.7
    },
    "daily_ingestions": {
      "today": 8,
      "max": 100,
      "remaining": 92
    }
  }
}
```

**Example:**
```bash
curl http://localhost:4000/api/chatbots/YOUR_CHATBOT_ID/knowledge/quota
```

---

## Error Handling

All endpoints return errors in the following format:

```json
{
  "error": "Error message here",
  "stack": "Stack trace (only in development mode)"
}
```

### Common Error Codes

- `400 Bad Request` - Invalid input parameters
- `403 Forbidden` - Quota exceeded
- `404 Not Found` - Resource not found
- `413 Payload Too Large` - File size exceeds 10MB
- `500 Internal Server Error` - Server error

---

## Health Check

**Request:**
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:00:00.000Z",
  "service": "fastbots-api-server",
  "version": "1.0.0"
}
```

---

## Development

### Running Locally

```bash
cd api-server
npm install
npm run dev
```

### Environment Variables

Set these in your `.env` file:

```env
PORT=4000
NODE_ENV=development
DB_HOST=localhost
DB_PORT=5432
DB_USER=business_logic_user
DB_PASSWORD=business_logic_password
DB_NAME=business_logic_app
WINDMILL_URL=http://localhost:8000
WINDMILL_TOKEN=your_windmill_token
WINDMILL_WORKSPACE=development
```

### Running with Docker

```bash
docker-compose up fastbots_api
```

---

## Architecture

The API server acts as a gateway between the frontend and Windmill:

1. **File Upload**: API receives file → Calls Windmill `upload_document` → Returns job ID
2. **URL Ingestion**: API receives URLs → Calls Windmill `ingest_multiple_urls` → Returns job IDs
3. **Web Crawling**: API receives base URL → Calls Windmill `web_crawler` → Returns discovered URLs
4. **Status Checking**: API queries PostgreSQL directly for real-time status
5. **Quota Enforcement**: Middleware calls Windmill `check_knowledge_quota` before operations

All processing happens asynchronously in Windmill workers. The API provides immediate responses with job IDs for tracking.
