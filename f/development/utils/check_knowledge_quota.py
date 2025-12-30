"""
Knowledge Base Quota Enforcement

This utility checks if an organization has remaining quota before
allowing new knowledge sources to be added. It prevents abuse and
controls costs by enforcing configurable per-tier limits.

Usage:
Called by upload_document.py and web_crawler.py before creating
new knowledge sources.
"""

import wmill
import psycopg2
from typing import Dict, Any


def main(
    chatbot_id: str,
    source_type: str,  # 'pdf', 'url', 'doc'
    file_size_mb: float = 0.0,
    db_resource: str = "f/development/business_layer_db_postgreSQL"
) -> Dict[str, Any]:
    """
    Check if organization has quota to add new knowledge source.

    Args:
        chatbot_id: ID of the chatbot
        source_type: Type of source ('pdf', 'url', 'doc')
        file_size_mb: Size of file in MB
        db_resource: Database resource path

    Returns:
        {
            "allowed": bool,
            "quota_type": str,  # which limit was hit (if not allowed)
            "current": int,     # current usage
            "max": int,         # max allowed
            "remaining": int    # how many more can be added
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

    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()

    try:
        # Get organization quota limits and current usage
        cur.execute("""
            SELECT
                o.id as organization_id,
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
            WHERE c.id = %s
        """, (chatbot_id,))

        row = cur.fetchone()
        if not row:
            return {
                "allowed": False,
                "quota_type": "CHATBOT_NOT_FOUND",
                "current": 0,
                "max": 0,
                "remaining": 0
            }

        (org_id, max_pdfs, max_urls, max_daily_ingestions, max_storage,
         current_pdfs, current_urls, current_storage, today_ingestions) = row

        # Convert Decimal types to float for arithmetic operations
        current_storage = float(current_storage)

        # Check storage limit
        if current_storage + file_size_mb > max_storage:
            return {
                "allowed": False,
                "quota_type": "STORAGE_LIMIT_EXCEEDED",
                "current": int(current_storage),
                "max": max_storage,
                "remaining": max(0, int(max_storage - current_storage))
            }

        # Check daily ingestion limit
        if today_ingestions >= max_daily_ingestions:
            return {
                "allowed": False,
                "quota_type": "DAILY_INGESTION_LIMIT_EXCEEDED",
                "current": today_ingestions,
                "max": max_daily_ingestions,
                "remaining": 0
            }

        # Check source type specific limits
        if source_type in ('pdf', 'doc'):
            if current_pdfs >= max_pdfs:
                return {
                    "allowed": False,
                    "quota_type": "PDF_LIMIT_EXCEEDED",
                    "current": current_pdfs,
                    "max": max_pdfs,
                    "remaining": 0
                }
            remaining = max_pdfs - current_pdfs

        elif source_type == 'url':
            if current_urls >= max_urls:
                return {
                    "allowed": False,
                    "quota_type": "URL_LIMIT_EXCEEDED",
                    "current": current_urls,
                    "max": max_urls,
                    "remaining": 0
                }
            remaining = max_urls - current_urls

        else:
            # Unknown source type - allow but warn
            remaining = 999

        # All checks passed
        return {
            "allowed": True,
            "quota_type": None,
            "current": current_pdfs if source_type in ('pdf', 'doc') else current_urls,
            "max": max_pdfs if source_type in ('pdf', 'doc') else max_urls,
            "remaining": remaining
        }

    finally:
        cur.close()
        conn.close()
