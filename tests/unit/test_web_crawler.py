"""
Unit tests for web crawler functionality.

Tests the web_crawler.py utility including URL discovery, relevance scoring,
robots.txt compliance, and rate limiting.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path
import time

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "f" / "development" / "utils"))

from web_crawler import main as crawl_url, calculate_relevance_score


@pytest.mark.unit
class TestWebCrawler:
    """Test web crawling functionality."""

    @pytest.fixture
    def mock_html_response(self):
        """Mock HTML response with links."""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Test Documentation</title></head>
        <body>
            <h1>Documentation</h1>
            <a href="/docs/getting-started">Getting Started</a>
            <a href="/docs/api/reference">API Reference</a>
            <a href="/faq">FAQ</a>
            <a href="/support">Support</a>
            <a href="https://external-site.com">External Link</a>
            <a href="#section">Anchor Link</a>
        </body>
        </html>
        """

    @pytest.fixture
    def mock_robots_txt(self):
        """Mock robots.txt allowing all paths."""
        return """
        User-agent: *
        Allow: /
        """

    @pytest.fixture
    def mock_robots_txt_disallow(self):
        """Mock robots.txt disallowing some paths."""
        return """
        User-agent: *
        Disallow: /admin
        Disallow: /private
        Allow: /
        """

    def test_basic_crawl_success(self, mock_html_response, mock_robots_txt):
        """Test basic successful crawl of a URL."""
        base_url = "https://example.com"

        with patch('requests.get') as mock_get:
            # Mock robots.txt response
            robots_response = Mock()
            robots_response.status_code = 200
            robots_response.text = mock_robots_txt

            # Mock page response
            page_response = Mock()
            page_response.status_code = 200
            page_response.text = mock_html_response
            page_response.headers = {"Content-Type": "text/html"}

            # Setup mock to return different responses
            mock_get.side_effect = [robots_response, page_response]

            # Execute crawl
            result = crawl_url(
                base_url=base_url,
                max_depth=1,
                max_pages=10
            )

            # Assert basic structure
            assert "discovered_urls" in result
            assert "total_discovered" in result
            assert "crawl_stats" in result
            assert result["success"] is True

            # Should discover at least the base URL
            assert result["total_discovered"] >= 1

    def test_relevance_scoring(self):
        """Test relevance score calculation."""
        base_domain = "example.com"
        keywords = ["docs", "api", "faq", "support"]

        # Test 1: Same domain + keyword in path (high score)
        score = calculate_relevance_score(
            url="https://example.com/docs/getting-started",
            title="Getting Started - Documentation",
            depth=0,
            base_domain=base_domain,
            keywords=keywords
        )
        assert score >= 0.7  # Same domain (0.4) + keyword (0.3) + no depth penalty

        # Test 2: Different domain (lower score)
        score = calculate_relevance_score(
            url="https://other-site.com/docs",
            title="Documentation",
            depth=0,
            base_domain=base_domain,
            keywords=keywords
        )
        assert score <= 0.4  # Only keyword bonus, no domain match

        # Test 3: Depth penalty
        score_depth_0 = calculate_relevance_score(
            url="https://example.com/docs",
            title="Docs",
            depth=0,
            base_domain=base_domain,
            keywords=keywords
        )
        score_depth_2 = calculate_relevance_score(
            url="https://example.com/docs",
            title="Docs",
            depth=2,
            base_domain=base_domain,
            keywords=keywords
        )
        assert score_depth_0 > score_depth_2  # Depth 0 should score higher

        # Test 4: No keyword match
        score = calculate_relevance_score(
            url="https://example.com/random/page",
            title="Random Page",
            depth=0,
            base_domain=base_domain,
            keywords=keywords
        )
        assert score == 0.4  # Only domain match bonus

    def test_suggested_flag_threshold(self):
        """Test that URLs with score > 0.5 are marked as suggested."""
        base_domain = "example.com"
        keywords = ["docs", "api"]

        # High score URL should be suggested
        high_score = calculate_relevance_score(
            url="https://example.com/docs/api",
            title="API Documentation",
            depth=0,
            base_domain=base_domain,
            keywords=keywords
        )
        assert high_score > 0.5

        # Low score URL should not be suggested
        low_score = calculate_relevance_score(
            url="https://other-site.com/random",
            title="Random",
            depth=3,
            base_domain=base_domain,
            keywords=keywords
        )
        assert low_score <= 0.5

    def test_robots_txt_compliance(self, mock_robots_txt_disallow):
        """Test that crawler respects robots.txt disallow rules."""
        base_url = "https://example.com"

        html_with_disallowed = """
        <html><body>
            <a href="/admin/users">Admin</a>
            <a href="/docs">Docs</a>
            <a href="/private/data">Private</a>
        </body></html>
        """

        with patch('requests.get') as mock_get:
            robots_response = Mock()
            robots_response.status_code = 200
            robots_response.text = mock_robots_txt_disallow

            page_response = Mock()
            page_response.status_code = 200
            page_response.text = html_with_disallowed
            page_response.headers = {"Content-Type": "text/html"}

            mock_get.side_effect = [robots_response, page_response]

            result = crawl_url(
                base_url=base_url,
                max_depth=2,
                max_pages=10
            )

            # Check that disallowed URLs are not in results
            discovered_urls = [item["url"] for item in result["discovered_urls"]]

            # Should not contain disallowed paths
            assert not any("/admin" in url for url in discovered_urls)
            assert not any("/private" in url for url in discovered_urls)

    def test_max_depth_limit(self, mock_html_response, mock_robots_txt):
        """Test that crawler respects max_depth limit."""
        base_url = "https://example.com"

        with patch('requests.get') as mock_get:
            robots_response = Mock()
            robots_response.status_code = 200
            robots_response.text = mock_robots_txt

            page_response = Mock()
            page_response.status_code = 200
            page_response.text = mock_html_response
            page_response.headers = {"Content-Type": "text/html"}

            mock_get.side_effect = [robots_response, page_response]

            result = crawl_url(
                base_url=base_url,
                max_depth=0,  # Should only crawl base URL
                max_pages=10
            )

            # With max_depth=0, should only have base URL or very few results
            assert result["total_discovered"] <= 2

    def test_max_pages_limit(self, mock_robots_txt):
        """Test that crawler respects max_pages limit."""
        base_url = "https://example.com"

        # Create HTML with many links
        many_links_html = """
        <html><body>
        """ + "\n".join([f'<a href="/page{i}">Page {i}</a>' for i in range(100)]) + """
        </body></html>
        """

        with patch('requests.get') as mock_get:
            robots_response = Mock()
            robots_response.status_code = 200
            robots_response.text = mock_robots_txt

            page_response = Mock()
            page_response.status_code = 200
            page_response.text = many_links_html
            page_response.headers = {"Content-Type": "text/html"}

            # Always return the same page
            mock_get.side_effect = lambda *args, **kwargs: robots_response if "robots.txt" in args[0] else page_response

            result = crawl_url(
                base_url=base_url,
                max_depth=2,
                max_pages=10  # Limit to 10 pages
            )

            # Should not exceed max_pages
            assert result["total_discovered"] <= 10

    def test_same_domain_only_filter(self, mock_robots_txt):
        """Test same_domain_only parameter filters external links."""
        base_url = "https://example.com"

        mixed_links_html = """
        <html><body>
            <a href="/internal/page1">Internal 1</a>
            <a href="/internal/page2">Internal 2</a>
            <a href="https://external.com/page">External</a>
            <a href="https://another-site.com/page">Another External</a>
        </body></html>
        """

        with patch('requests.get') as mock_get:
            robots_response = Mock()
            robots_response.status_code = 200
            robots_response.text = mock_robots_txt

            page_response = Mock()
            page_response.status_code = 200
            page_response.text = mixed_links_html
            page_response.headers = {"Content-Type": "text/html"}

            mock_get.side_effect = [robots_response, page_response]

            result = crawl_url(
                base_url=base_url,
                max_depth=1,
                max_pages=10,
                same_domain_only=True
            )

            # All discovered URLs should be from example.com
            for item in result["discovered_urls"]:
                assert "example.com" in item["url"]

    def test_error_handling_network_error(self):
        """Test graceful handling of network errors."""
        base_url = "https://example.com"

        with patch('requests.get') as mock_get:
            # Simulate network error
            mock_get.side_effect = Exception("Network error")

            result = crawl_url(
                base_url=base_url,
                max_depth=1,
                max_pages=10
            )

            # Should return error result, not crash
            assert "error" in result or result["success"] is False

    def test_error_handling_404(self, mock_robots_txt):
        """Test handling of 404 responses."""
        base_url = "https://example.com"

        with patch('requests.get') as mock_get:
            robots_response = Mock()
            robots_response.status_code = 200
            robots_response.text = mock_robots_txt

            page_response = Mock()
            page_response.status_code = 404

            mock_get.side_effect = [robots_response, page_response]

            result = crawl_url(
                base_url=base_url,
                max_depth=1,
                max_pages=10
            )

            # Should handle 404 gracefully
            # Might have no discovered URLs or error message
            assert "discovered_urls" in result or "error" in result

    def test_custom_keywords_filtering(self, mock_robots_txt):
        """Test custom keyword filtering."""
        base_url = "https://example.com"
        custom_keywords = ["pricing", "features", "contact"]

        html_with_keywords = """
        <html><body>
            <a href="/pricing">Pricing</a>
            <a href="/features">Features</a>
            <a href="/blog">Blog</a>
        </body></html>
        """

        with patch('requests.get') as mock_get:
            robots_response = Mock()
            robots_response.status_code = 200
            robots_response.text = mock_robots_txt

            page_response = Mock()
            page_response.status_code = 200
            page_response.text = html_with_keywords
            page_response.headers = {"Content-Type": "text/html"}

            mock_get.side_effect = [robots_response, page_response]

            result = crawl_url(
                base_url=base_url,
                max_depth=1,
                max_pages=10,
                filter_keywords=custom_keywords
            )

            # URLs with keywords should have higher relevance scores
            for item in result["discovered_urls"]:
                if any(kw in item["url"].lower() for kw in custom_keywords):
                    assert item["relevance_score"] > 0.5

    def test_rate_limiting_enforced(self, mock_html_response, mock_robots_txt):
        """Test that crawler enforces 1 request/second rate limit."""
        base_url = "https://example.com"

        with patch('requests.get') as mock_get, \
             patch('time.sleep') as mock_sleep:

            robots_response = Mock()
            robots_response.status_code = 200
            robots_response.text = mock_robots_txt

            page_response = Mock()
            page_response.status_code = 200
            page_response.text = mock_html_response
            page_response.headers = {"Content-Type": "text/html"}

            mock_get.side_effect = [robots_response, page_response, page_response]

            result = crawl_url(
                base_url=base_url,
                max_depth=1,
                max_pages=5
            )

            # Should have called sleep to rate limit (at least once)
            assert mock_sleep.call_count >= 1
            # Should sleep 1 second between requests
            mock_sleep.assert_called_with(1)

    def test_content_preview_extraction(self, mock_robots_txt):
        """Test extraction of content preview from pages."""
        base_url = "https://example.com"

        html_with_content = """
        <html><body>
            <h1>Main Title</h1>
            <p>This is the first paragraph with some content that should be extracted as a preview.</p>
            <p>This is another paragraph.</p>
        </body></html>
        """

        with patch('requests.get') as mock_get:
            robots_response = Mock()
            robots_response.status_code = 200
            robots_response.text = mock_robots_txt

            page_response = Mock()
            page_response.status_code = 200
            page_response.text = html_with_content
            page_response.headers = {"Content-Type": "text/html"}

            mock_get.side_effect = [robots_response, page_response]

            result = crawl_url(
                base_url=base_url,
                max_depth=0,
                max_pages=1
            )

            # Should have content preview
            if result["discovered_urls"]:
                first_url = result["discovered_urls"][0]
                assert "content_preview" in first_url
                assert len(first_url["content_preview"]) > 0

    def test_crawl_statistics(self, mock_html_response, mock_robots_txt):
        """Test that crawl statistics are correctly reported."""
        base_url = "https://example.com"

        with patch('requests.get') as mock_get:
            robots_response = Mock()
            robots_response.status_code = 200
            robots_response.text = mock_robots_txt

            page_response = Mock()
            page_response.status_code = 200
            page_response.text = mock_html_response
            page_response.headers = {"Content-Type": "text/html"}

            mock_get.side_effect = [robots_response, page_response]

            result = crawl_url(
                base_url=base_url,
                max_depth=1,
                max_pages=10
            )

            # Should have statistics
            assert "crawl_stats" in result
            stats = result["crawl_stats"]
            assert "pages_crawled" in stats
            assert "links_found" in stats
            assert stats["pages_crawled"] >= 1
