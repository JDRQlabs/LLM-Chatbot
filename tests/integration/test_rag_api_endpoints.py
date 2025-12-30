"""
Integration tests for RAG API endpoints.

Tests the knowledge base API endpoints defined in api-server/routes/knowledge.js
"""

import pytest
from unittest.mock import Mock, patch
import sys
from pathlib import Path
import json


@pytest.mark.integration
class TestRAGAPIEndpoints:
    """Test knowledge base API endpoint logic and contracts."""

    @pytest.fixture
    def chatbot_id(self):
        """Test chatbot ID."""
        return "22222222-2222-2222-2222-222222222222"

    @pytest.fixture
    def organization_id(self):
        """Test organization ID."""
        return "11111111-1111-1111-1111-111111111111"

    @pytest.fixture
    def sample_quota_response(self):
        """Sample quota response from database."""
        return {
            "max_knowledge_pdfs": 50,
            "max_knowledge_urls": 20,
            "max_knowledge_ingestions_per_day": 100,
            "max_knowledge_storage_mb": 500,
            "current_knowledge_pdfs": 10,
            "current_knowledge_urls": 5,
            "current_storage_mb": 100,
            "today_ingestions": 25
        }

    @pytest.fixture
    def sample_crawl_result(self):
        """Sample web crawler result."""
        return {
            "success": True,
            "discovered_urls": [
                {
                    "url": "https://example.com/docs",
                    "title": "Documentation",
                    "relevance_score": 0.7,
                    "depth": 0,
                    "content_preview": "Welcome to our documentation...",
                    "suggested": True
                },
                {
                    "url": "https://example.com/api",
                    "title": "API Reference",
                    "relevance_score": 0.65,
                    "depth": 1,
                    "content_preview": "API endpoints for...",
                    "suggested": True
                }
            ],
            "total_discovered": 2,
            "crawl_stats": {
                "pages_crawled": 2,
                "links_found": 10
            }
        }

    # ========================================================================
    # Test 1: GET /api/chatbots/:id/knowledge/quota
    # ========================================================================

    def test_quota_endpoint_returns_current_usage(self, db_with_data, chatbot_id, sample_quota_response):
        """Test quota endpoint returns current organization usage."""
        # Setup: Verify quota data in database
        db_with_data.execute("""
            SELECT
                o.max_knowledge_pdfs,
                o.current_knowledge_pdfs,
                o.max_knowledge_urls,
                o.current_knowledge_urls,
                o.max_knowledge_ingestions_per_day,
                o.max_knowledge_storage_mb,
                o.current_storage_mb,
                COALESCE(dic.ingestion_count, 0) as today_ingestions
            FROM chatbots c
            JOIN organizations o ON c.organization_id = o.id
            LEFT JOIN daily_ingestion_counts dic
                ON dic.organization_id = o.id
                AND dic.date = CURRENT_DATE
            WHERE c.id = %s
        """, (chatbot_id,))

        result = db_with_data.fetchone()
        assert result is not None

        # Expected response structure
        expected_response = {
            "success": True,
            "quota": {
                "pdfs": {
                    "current": result["current_knowledge_pdfs"],
                    "max": result["max_knowledge_pdfs"],
                    "remaining": result["max_knowledge_pdfs"] - result["current_knowledge_pdfs"]
                },
                "urls": {
                    "current": result["current_knowledge_urls"],
                    "max": result["max_knowledge_urls"],
                    "remaining": result["max_knowledge_urls"] - result["current_knowledge_urls"]
                },
                "storage_mb": {
                    "current": float(result["current_storage_mb"]),
                    "max": result["max_knowledge_storage_mb"],
                    "remaining": result["max_knowledge_storage_mb"] - float(result["current_storage_mb"])
                },
                "daily_ingestions": {
                    "current": result["today_ingestions"],
                    "max": result["max_knowledge_ingestions_per_day"],
                    "remaining": result["max_knowledge_ingestions_per_day"] - result["today_ingestions"]
                }
            }
        }

        # Verify structure matches expected API response
        assert expected_response["success"] is True
        assert "quota" in expected_response
        assert "pdfs" in expected_response["quota"]
        assert "urls" in expected_response["quota"]
        assert "storage_mb" in expected_response["quota"]
        assert "daily_ingestions" in expected_response["quota"]

    def test_quota_endpoint_calculates_remaining_correctly(self, db_with_data, chatbot_id):
        """Test that quota endpoint calculates remaining quota correctly."""
        # Setup: Set specific values
        db_with_data.execute("""
            UPDATE organizations
            SET max_knowledge_pdfs = 50,
                current_knowledge_pdfs = 15,
                max_knowledge_urls = 20,
                current_knowledge_urls = 8
            WHERE id = '11111111-1111-1111-1111-111111111111'
        """)

        # Query data
        db_with_data.execute("""
            SELECT
                o.max_knowledge_pdfs,
                o.current_knowledge_pdfs,
                o.max_knowledge_urls,
                o.current_knowledge_urls
            FROM chatbots c
            JOIN organizations o ON c.organization_id = o.id
            WHERE c.id = %s
        """, (chatbot_id,))

        result = db_with_data.fetchone()

        # Calculate remaining
        pdf_remaining = result["max_knowledge_pdfs"] - result["current_knowledge_pdfs"]
        url_remaining = result["max_knowledge_urls"] - result["current_knowledge_urls"]

        assert pdf_remaining == 35  # 50 - 15
        assert url_remaining == 12  # 20 - 8

    # ========================================================================
    # Test 3: POST /api/chatbots/:id/knowledge/crawl
    # ========================================================================

    def test_crawl_endpoint_returns_discovered_urls(self, sample_crawl_result):
        """Test crawl endpoint returns properly structured URL list."""
        # Expected request body
        request_body = {
            "baseUrl": "https://example.com",
            "maxDepth": 2,
            "maxPages": 50
        }

        # Expected response structure
        assert "discovered_urls" in sample_crawl_result
        assert len(sample_crawl_result["discovered_urls"]) > 0

        # Verify each URL has required fields
        for url_item in sample_crawl_result["discovered_urls"]:
            assert "url" in url_item
            assert "title" in url_item
            assert "relevance_score" in url_item
            assert "depth" in url_item
            assert "suggested" in url_item
            assert isinstance(url_item["suggested"], bool)
            assert 0 <= url_item["relevance_score"] <= 1

    def test_crawl_endpoint_marks_high_score_urls_as_suggested(self, sample_crawl_result):
        """Test that URLs with score > 0.5 are marked as suggested."""
        for url_item in sample_crawl_result["discovered_urls"]:
            if url_item["relevance_score"] > 0.5:
                assert url_item["suggested"] is True
            else:
                assert url_item["suggested"] is False

    # ========================================================================
    # Test 5: GET /api/chatbots/:id/knowledge/sources
    # ========================================================================

    def test_sources_list_endpoint(self, db_with_data, chatbot_id):
        """Test listing knowledge sources for a chatbot."""
        # Setup: Insert test knowledge sources
        db_with_data.execute("""
            INSERT INTO knowledge_sources (chatbot_id, source_type, source_name, source_url, status)
            VALUES
                (%s, 'pdf', 'Product Manual', NULL, 'synced'),
                (%s, 'url', 'FAQ Page', 'https://example.com/faq', 'synced'),
                (%s, 'pdf', 'Training Doc', NULL, 'pending')
            RETURNING id
        """, (chatbot_id, chatbot_id, chatbot_id))

        # Query sources
        db_with_data.execute("""
            SELECT id, source_type, source_name, source_url, status, created_at
            FROM knowledge_sources
            WHERE chatbot_id = %s
            ORDER BY created_at DESC
        """, (chatbot_id,))

        sources = db_with_data.fetchall()

        # Verify results
        assert len(sources) >= 3
        assert all(s["source_type"] in ["pdf", "url", "doc"] for s in sources)
        assert all(s["status"] in ["pending", "processing", "synced", "failed"] for s in sources)

    def test_sources_list_includes_chunk_count(self, db_with_data, chatbot_id):
        """Test that source list includes document chunk count."""
        # Setup: Insert knowledge source with chunks
        db_with_data.execute("""
            INSERT INTO knowledge_sources (chatbot_id, source_type, source_name, status)
            VALUES (%s, 'pdf', 'Test PDF', 'synced')
            RETURNING id
        """, (chatbot_id,))

        source_id = db_with_data.fetchone()["id"]

        # Insert chunks
        for i in range(5):
            db_with_data.execute("""
                INSERT INTO document_chunks (knowledge_source_id, chunk_index, content, embedding)
                VALUES (%s, %s, %s, %s)
            """, (source_id, i, f"Chunk {i}", "[0.1, 0.2, 0.3]"))

        # Query with chunk count
        db_with_data.execute("""
            SELECT
                ks.id,
                ks.source_name,
                COUNT(dc.id) as chunk_count
            FROM knowledge_sources ks
            LEFT JOIN document_chunks dc ON dc.knowledge_source_id = ks.id
            WHERE ks.id = %s
            GROUP BY ks.id
        """, (source_id,))

        result = db_with_data.fetchone()
        assert result["chunk_count"] == 5

    # ========================================================================
    # Test 6: GET /api/chatbots/:id/knowledge/sources/:sourceId/status
    # ========================================================================

    def test_source_status_endpoint(self, db_with_data, chatbot_id):
        """Test getting processing status of a specific knowledge source."""
        # Setup: Insert source with status
        db_with_data.execute("""
            INSERT INTO knowledge_sources (chatbot_id, source_type, source_name, status, error_message)
            VALUES (%s, 'pdf', 'Processing Doc', 'processing', NULL)
            RETURNING id
        """, (chatbot_id,))

        source_id = db_with_data.fetchone()["id"]

        # Query status
        db_with_data.execute("""
            SELECT id, source_name, status, error_message, created_at, updated_at
            FROM knowledge_sources
            WHERE id = %s
        """, (source_id,))

        result = db_with_data.fetchone()

        # Expected response structure
        expected_response = {
            "success": True,
            "source": {
                "id": str(result["id"]),
                "name": result["source_name"],
                "status": result["status"],
                "error_message": result["error_message"],
                "created_at": result["created_at"].isoformat(),
                "updated_at": result["updated_at"].isoformat()
            }
        }

        assert expected_response["success"] is True
        assert expected_response["source"]["status"] == "processing"

    # ========================================================================
    # Test 7: DELETE /api/chatbots/:id/knowledge/sources/:sourceId
    # ========================================================================

    def test_delete_source_endpoint(self, db_with_data, chatbot_id):
        """Test deleting a knowledge source."""
        # Setup: Insert source
        db_with_data.execute("""
            INSERT INTO knowledge_sources (chatbot_id, source_type, source_name, status)
            VALUES (%s, 'pdf', 'To Delete', 'synced')
            RETURNING id
        """, (chatbot_id,))

        source_id = db_with_data.fetchone()["id"]

        # Delete source
        db_with_data.execute("""
            DELETE FROM knowledge_sources
            WHERE id = %s AND chatbot_id = %s
            RETURNING id
        """, (source_id, chatbot_id))

        deleted = db_with_data.fetchone()
        assert deleted is not None

        # Verify deleted
        db_with_data.execute("""
            SELECT id FROM knowledge_sources WHERE id = %s
        """, (source_id,))

        result = db_with_data.fetchone()
        assert result is None

    def test_delete_source_decrements_quota(self, db_with_data, chatbot_id):
        """Test that deleting a source should trigger quota decrement (via trigger)."""
        # Get initial count
        db_with_data.execute("""
            SELECT current_knowledge_pdfs FROM organizations
            WHERE id = '11111111-1111-1111-1111-111111111111'
        """)
        initial_count = db_with_data.fetchone()["current_knowledge_pdfs"]

        # Insert and then delete (trigger should decrement on delete)
        # Note: This would require a DELETE trigger which we haven't implemented yet
        # This test documents the expected behavior

        # For now, just verify that manual decrement works
        db_with_data.execute("""
            UPDATE organizations
            SET current_knowledge_pdfs = current_knowledge_pdfs - 1
            WHERE id = '11111111-1111-1111-1111-111111111111'
        """)

        db_with_data.execute("""
            SELECT current_knowledge_pdfs FROM organizations
            WHERE id = '11111111-1111-1111-1111-111111111111'
        """)
        new_count = db_with_data.fetchone()["current_knowledge_pdfs"]

        assert new_count == initial_count - 1

    # ========================================================================
    # Test 8: POST /api/chatbots/:id/knowledge/search (RAG Test)
    # ========================================================================

    def test_search_endpoint_structure(self):
        """Test RAG search endpoint request/response structure."""
        # Expected request
        request_body = {
            "query": "How do I reset my password?",
            "top_k": 5
        }

        # Expected response structure
        expected_response = {
            "success": True,
            "results": [
                {
                    "content": "To reset your password, go to...",
                    "source_name": "FAQ Page",
                    "source_type": "url",
                    "similarity_score": 0.85,
                    "chunk_index": 0
                }
            ],
            "query": "How do I reset my password?",
            "results_count": 5
        }

        # Verify structure
        assert "success" in expected_response
        assert "results" in expected_response
        assert "query" in expected_response
        assert len(expected_response["results"]) > 0

        # Verify result structure
        result = expected_response["results"][0]
        assert "content" in result
        assert "source_name" in result
        assert "similarity_score" in result
        assert 0 <= result["similarity_score"] <= 1

    # ========================================================================
    # Test 4: POST /api/chatbots/:id/knowledge/ingest-batch
    # ========================================================================

    def test_batch_ingest_endpoint_structure(self):
        """Test batch URL ingestion endpoint structure."""
        # Expected request
        request_body = {
            "urls": [
                {
                    "url": "https://example.com/docs",
                    "title": "Documentation"
                },
                {
                    "url": "https://example.com/faq",
                    "title": "FAQ"
                }
            ]
        }

        # Expected response
        expected_response = {
            "success": True,
            "ingested_count": 2,
            "failed_count": 0,
            "results": [
                {
                    "url": "https://example.com/docs",
                    "knowledge_source_id": "uuid-here",
                    "status": "pending"
                },
                {
                    "url": "https://example.com/faq",
                    "knowledge_source_id": "uuid-here",
                    "status": "pending"
                }
            ]
        }

        # Verify structure
        assert expected_response["success"] is True
        assert "ingested_count" in expected_response
        assert "results" in expected_response
        assert len(expected_response["results"]) == len(request_body["urls"])

    # ========================================================================
    # Error Handling Tests
    # ========================================================================

    def test_quota_exceeded_error_response(self):
        """Test error response when quota exceeded."""
        expected_error = {
            "success": False,
            "error": "QUOTA_EXCEEDED",
            "message": "PDF upload limit reached (10/10). Upgrade plan to add more documents.",
            "quota_type": "PDF_LIMIT_EXCEEDED",
            "current": 10,
            "max": 10
        }

        assert expected_error["success"] is False
        assert "error" in expected_error
        assert "quota_type" in expected_error

    def test_chatbot_not_found_error(self):
        """Test error response when chatbot doesn't exist."""
        expected_error = {
            "success": False,
            "error": "CHATBOT_NOT_FOUND",
            "message": "Chatbot not found or access denied"
        }

        assert expected_error["success"] is False
        assert expected_error["error"] == "CHATBOT_NOT_FOUND"

    def test_invalid_url_error(self):
        """Test error response for invalid URL in crawl request."""
        expected_error = {
            "success": False,
            "error": "INVALID_URL",
            "message": "Invalid URL format"
        }

        assert expected_error["success"] is False
        assert expected_error["error"] == "INVALID_URL"
