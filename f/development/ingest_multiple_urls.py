"""
Batch URL Ingestion for Knowledge Base

This script ingests multiple URLs in batch, checking quota for each one
and creating knowledge_source records. It then triggers async processing
via RAG_process_documents.

Usage:
Called by the API server or frontend when user wants to ingest multiple
URLs discovered by the web crawler.

Features:
- Quota checking per URL
- Graceful handling of partial failures
- Async processing trigger
- Detailed per-URL status reporting
"""

import wmill
import psycopg2
from typing import Dict, List, Any
from datetime import datetime


def main(
    chatbot_id: str,
    urls: List[str],
    db_resource: str = "f/development/business_layer_db_postgreSQL"
) -> Dict[str, Any]:
    """
    Ingest multiple URLs in batch.

    For each URL:
    1. Check quota using check_knowledge_quota
    2. Create knowledge_source record (status: pending)
    3. Trigger RAG_process_documents async

    Args:
        chatbot_id: ID of the chatbot
        urls: List of URLs to ingest
        db_resource: Database resource path

    Returns:
        {
            "total_urls": int,
            "successful": int,
            "failed": int,
            "results": [
                {
                    "url": str,
                    "success": bool,
                    "knowledge_source_id": str (if success),
                    "job_id": str (if success),
                    "error": str (if failed),
                    "quota_info": dict
                }
            ]
        }
    """

    # Get database credentials
    raw_config = wmill.get_resource(db_resource)
    db_params = {
        "host": raw_config.get("host"),
        "port": raw_config.get("port"),
        "user": raw_config.get("user"),
        "password": raw_config.get("password"),
        "dbname": raw_config.get("dbname"),
        "sslmode": "disable",
    }

    results = []
    successful = 0
    failed = 0

    for url in urls:
        try:
            # Check quota for this URL
            quota_check = wmill.run_script_by_path(
                "f/development/utils/check_knowledge_quota",
                args={
                    "chatbot_id": chatbot_id,
                    "source_type": "url",
                    "file_size_mb": 0.0,  # Will be calculated during processing
                    "db_resource": db_resource
                }
            )

            if not quota_check.get("allowed", False):
                # Quota exceeded
                results.append({
                    "url": url,
                    "success": False,
                    "error": f"Quota exceeded: {quota_check.get('quota_type')}",
                    "quota_info": quota_check
                })
                failed += 1
                continue

            # Create knowledge_source record
            conn = psycopg2.connect(**db_params)
            cur = conn.cursor()

            try:
                cur.execute("""
                    INSERT INTO knowledge_sources (
                        chatbot_id,
                        source_type,
                        source_url,
                        status,
                        created_at,
                        updated_at
                    ) VALUES (%s, 'url', %s, 'pending', NOW(), NOW())
                    RETURNING id
                """, (chatbot_id, url))

                knowledge_source_id = cur.fetchone()[0]
                conn.commit()

                # Trigger async RAG processing
                job_id = wmill.run_script_by_path_async(
                    "f/development/RAG_process_documents",
                    args={
                        "knowledge_source_id": str(knowledge_source_id),
                        "db_resource": db_resource
                    }
                )

                results.append({
                    "url": url,
                    "success": True,
                    "knowledge_source_id": str(knowledge_source_id),
                    "job_id": job_id,
                    "quota_info": quota_check
                })
                successful += 1

                print(f"✓ Queued processing for {url} (source_id: {knowledge_source_id}, job: {job_id})")

            finally:
                cur.close()
                conn.close()

        except Exception as e:
            results.append({
                "url": url,
                "success": False,
                "error": str(e)
            })
            failed += 1
            print(f"✗ Failed to process {url}: {e}")

    return {
        "total_urls": len(urls),
        "successful": successful,
        "failed": failed,
        "results": results,
        "timestamp": datetime.now().isoformat()
    }
