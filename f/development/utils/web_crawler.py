"""
Web Crawler with Auto-Discovery and Relevance Scoring

This utility crawls a website starting from a base URL, discovers linked pages,
and scores them by relevance for knowledge base ingestion. It implements the
hybrid approach: auto-discover + manual selection.

Usage:
Called by the API server or frontend when user wants to crawl a website
for knowledge base ingestion.

Features:
- Respects robots.txt
- Rate limiting (1 request/second)
- Relevance scoring algorithm
- Depth-based crawling
- Same-domain restriction
"""

import time
import urllib.parse
import urllib.robotparser
from typing import Dict, List, Any, Set
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup


def main(
    base_url: str,
    max_depth: int = 2,
    max_pages: int = 50,
    same_domain_only: bool = True,
    filter_keywords: List[str] = None
) -> Dict[str, Any]:
    """
    Discover links from a base URL and score them by relevance.

    Args:
        base_url: Starting URL (e.g., https://example.com)
        max_depth: How many levels deep to crawl (default: 2)
        max_pages: Maximum pages to discover (default: 50)
        same_domain_only: Only crawl pages on same domain (default: True)
        filter_keywords: Keywords to boost relevance (e.g., ['faq', 'docs'])

    Returns:
        {
            "discovered_urls": [
                {
                    "url": str,
                    "title": str,
                    "relevance_score": float,  # 0-1
                    "depth": int,
                    "content_preview": str,  # first 200 chars
                    "suggested": bool  # auto-selected if score > 0.5
                },
                ...
            ],
            "total_discovered": int,
            "crawl_time_seconds": float,
            "base_domain": str,
            "robots_txt_respected": bool
        }
    """

    start_time = time.time()

    # Parse base URL
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc

    # Default keywords that indicate valuable content
    if filter_keywords is None:
        filter_keywords = [
            'faq', 'docs', 'documentation', 'support', 'help',
            'about', 'guide', 'tutorial', 'api', 'reference'
        ]

    # Check robots.txt
    robots_txt_respected = True
    robot_parser = urllib.robotparser.RobotFileParser()
    robots_url = f"{parsed_base.scheme}://{parsed_base.netloc}/robots.txt"

    try:
        robot_parser.set_url(robots_url)
        robot_parser.read()
    except Exception as e:
        print(f"Warning: Could not read robots.txt from {robots_url}: {e}")
        robots_txt_respected = False

    # Data structures for crawling
    discovered_urls: List[Dict[str, Any]] = []
    visited: Set[str] = set()
    to_visit: List[tuple] = [(base_url, 0)]  # (url, depth)

    print(f"Starting crawl of {base_url} (max_depth={max_depth}, max_pages={max_pages})")

    while to_visit and len(discovered_urls) < max_pages:
        current_url, current_depth = to_visit.pop(0)

        # Skip if already visited
        if current_url in visited:
            continue

        # Skip if too deep
        if current_depth > max_depth:
            continue

        # Check robots.txt
        if robots_txt_respected and not robot_parser.can_fetch("*", current_url):
            print(f"Skipping {current_url} (blocked by robots.txt)")
            continue

        visited.add(current_url)

        # Fetch page with rate limiting
        try:
            time.sleep(1)  # Rate limit: 1 request/second

            response = requests.get(
                current_url,
                headers={'User-Agent': 'FastBots.ai Knowledge Crawler/1.0'},
                timeout=10,
                allow_redirects=True
            )
            response.raise_for_status()

            # Only process HTML pages
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                print(f"Skipping {current_url} (not HTML: {content_type})")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract page info
            title = soup.find('title')
            title_text = title.string.strip() if title else urlparse(current_url).path

            # Get content preview (first 200 chars of visible text)
            content_preview = ""
            for text in soup.stripped_strings:
                content_preview += text + " "
                if len(content_preview) >= 200:
                    break
            content_preview = content_preview[:200].strip()

            # Calculate relevance score
            relevance_score = calculate_relevance_score(
                current_url,
                title_text,
                current_depth,
                base_domain,
                filter_keywords
            )

            # Add to discovered URLs
            discovered_urls.append({
                "url": current_url,
                "title": title_text,
                "relevance_score": round(relevance_score, 2),
                "depth": current_depth,
                "content_preview": content_preview,
                "suggested": relevance_score > 0.5
            })

            print(f"✓ Discovered: {current_url} (score: {relevance_score:.2f}, depth: {current_depth})")

            # Find links to crawl next (only if not at max depth)
            if current_depth < max_depth:
                for link in soup.find_all('a', href=True):
                    absolute_url = urljoin(current_url, link['href'])

                    # Normalize URL (remove fragments)
                    parsed_url = urlparse(absolute_url)
                    normalized_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                    if parsed_url.query:
                        normalized_url += f"?{parsed_url.query}"

                    # Skip if already visited or queued
                    if normalized_url in visited:
                        continue

                    # Check same domain restriction
                    if same_domain_only and urlparse(normalized_url).netloc != base_domain:
                        continue

                    # Skip common non-content URLs
                    if should_skip_url(normalized_url):
                        continue

                    # Add to queue
                    to_visit.append((normalized_url, current_depth + 1))

        except requests.RequestException as e:
            print(f"Error fetching {current_url}: {e}")
            continue
        except Exception as e:
            print(f"Unexpected error processing {current_url}: {e}")
            continue

    # Sort by relevance score (highest first)
    discovered_urls.sort(key=lambda x: x['relevance_score'], reverse=True)

    crawl_time = time.time() - start_time

    return {
        "discovered_urls": discovered_urls,
        "total_discovered": len(discovered_urls),
        "crawl_time_seconds": round(crawl_time, 2),
        "base_domain": base_domain,
        "robots_txt_respected": robots_txt_respected
    }


def calculate_relevance_score(
    url: str,
    title: str,
    depth: int,
    base_domain: str,
    keywords: List[str]
) -> float:
    """
    Calculate relevance score for a URL.

    Scoring algorithm:
    - Same domain: +0.4
    - Keywords in path: +0.3
    - Depth penalty: -0.1 per level
    - Response time bonus: +0.1 (not implemented here, would need timing)

    Returns:
        Score between 0 and 1
    """
    score = 0.0

    # Same domain bonus
    parsed = urlparse(url)
    if parsed.netloc == base_domain:
        score += 0.4

    # Keywords in URL path or title
    url_lower = url.lower()
    title_lower = title.lower()

    for keyword in keywords:
        if keyword in url_lower or keyword in title_lower:
            score += 0.3
            break  # Only count once

    # Depth penalty
    score -= (depth * 0.1)

    # Ensure score is between 0 and 1
    return max(0.0, min(1.0, score))


def should_skip_url(url: str) -> bool:
    """
    Check if URL should be skipped (non-content pages).

    Returns:
        True if URL should be skipped
    """
    url_lower = url.lower()

    skip_patterns = [
        '/login', '/signin', '/signup', '/register',
        '/cart', '/checkout', '/account', '/profile',
        '/admin', '/wp-admin', '/dashboard',
        '.pdf', '.jpg', '.png', '.gif', '.zip', '.mp4',
        'javascript:', 'mailto:', 'tel:',
        '#', '/search?', '/tag/', '/category/',
        '/page/', '/wp-content/', '/wp-includes/'
    ]

    for pattern in skip_patterns:
        if pattern in url_lower:
            return True

    return False
