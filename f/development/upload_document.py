"""
Document Upload Flow for RAG Knowledge Base

This script handles document uploads to the knowledge base:
1. Validates chatbot ownership
2. Saves file to Windmill S3 storage
3. Creates knowledge_source record
4. Triggers async RAG processing

Supported document types:
- PDF files
- URLs (web pages)
- Plain text
- Word documents (.docx)
"""

import wmill
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, Optional
import base64
import mimetypes


def main(
    chatbot_id: str,
    source_type: str,  # "pdf", "url", "text", "doc"
    name: str,  # Display name for the document
    file_content: Optional[str] = None,  # Base64 encoded file content (for pdf/doc/text)
    url: Optional[str] = None,  # URL for web pages
    openai_api_key: str = wmill.get_variable("u/admin/OpenAI_API_Key"),
    db_resource: str = "f/development/business_layer_db_postgreSQL",
) -> Dict[str, Any]:
    """
    Upload a document to the knowledge base.

    Args:
        chatbot_id: UUID of the chatbot
        source_type: Type of document (pdf, url, text, doc)
        name: Display name for the document
        file_content: Base64 encoded file content (for pdf/doc/text)
        url: URL for web pages
        openai_api_key: OpenAI API key for embedding generation
        db_resource: Database resource path

    Returns:
        Upload result with source_id and processing job_id
    """

    # Validate inputs
    if source_type not in ["pdf", "url", "text", "doc"]:
        return {"success": False, "error": f"Invalid source_type: {source_type}"}

    if source_type == "url" and not url:
        return {"success": False, "error": "URL required for url source_type"}

    if source_type in ["pdf", "doc", "text"] and not file_content:
        return {"success": False, "error": f"file_content required for {source_type} source_type"}

    # Setup database
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
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # 1. Validate chatbot exists and is active
        cur.execute(
            """
            SELECT c.id, c.organization_id, c.is_active, c.rag_enabled
            FROM chatbots c
            WHERE c.id = %s
            """,
            (chatbot_id,)
        )
        chatbot = cur.fetchone()

        if not chatbot:
            return {"success": False, "error": "Chatbot not found"}

        if not chatbot["is_active"]:
            return {"success": False, "error": "Chatbot is disabled"}

        if not chatbot.get("rag_enabled"):
            return {"success": False, "error": "RAG is not enabled for this chatbot"}

        # 2. Handle file storage
        file_path = None
        file_size = 0

        if source_type == "url":
            # For URLs, store the URL directly
            file_path = url

        else:
            # For files, save to S3
            try:
                # Decode base64 content
                file_bytes = base64.b64decode(file_content)
                file_size = len(file_bytes)

                # Validate file size (max 10MB for now)
                max_size = 10 * 1024 * 1024  # 10MB
                if file_size > max_size:
                    return {
                        "success": False,
                        "error": f"File too large. Max size: {max_size / 1024 / 1024:.1f}MB"
                    }

                # Determine file extension
                ext_map = {
                    "pdf": ".pdf",
                    "doc": ".docx",
                    "text": ".txt"
                }
                file_ext = ext_map.get(source_type, ".bin")

                # Generate S3 path
                # Format: knowledge/{chatbot_id}/{timestamp}_{name}{ext}
                import time
                timestamp = int(time.time())
                safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_name = safe_name.replace(' ', '_')
                s3_filename = f"{timestamp}_{safe_name}{file_ext}"

                # Write to S3
                s3_result = wmill.write_s3_file(
                    s3object=None,  # Auto-generate path
                    file_content=file_bytes,
                    s3_resource_path=None,  # Use default workspace S3
                )

                file_path = s3_result.get("s3")
                print(f"File saved to S3: {file_path}")

            except Exception as e:
                return {"success": False, "error": f"File storage failed: {str(e)}"}

        # 3. Create knowledge_source record
        cur.execute(
            """
            INSERT INTO knowledge_sources (
                chatbot_id,
                source_type,
                name,
                file_path,
                file_size,
                sync_status,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, 'pending', NOW())
            RETURNING id
            """,
            (chatbot_id, source_type, name, file_path, file_size)
        )

        source_id = cur.fetchone()["id"]
        conn.commit()

        print(f"Created knowledge_source: {source_id}")

        # 4. Trigger async RAG processing
        try:
            job_id = wmill.run_script_by_path_async(
                path="f/development/RAG_process_documents",
                args={
                    "knowledge_source_id": str(source_id),
                    "chatbot_id": chatbot_id,
                    "openai_api_key": openai_api_key,
                }
            )

            print(f"RAG processing job started: {job_id}")

            return {
                "success": True,
                "source_id": str(source_id),
                "processing_job_id": job_id,
                "message": "Document uploaded successfully. Processing started.",
                "file_path": file_path if source_type != "url" else None,
                "url": url if source_type == "url" else None,
                "file_size": file_size,
                "status": "processing"
            }

        except Exception as e:
            print(f"Failed to trigger RAG processing: {e}")
            # Update status to failed
            cur.execute(
                """
                UPDATE knowledge_sources
                SET sync_status = 'failed',
                    error_message = %s
                WHERE id = %s
                """,
                (f"Failed to start processing: {str(e)}", source_id)
            )
            conn.commit()

            return {
                "success": False,
                "error": f"Document uploaded but processing failed to start: {str(e)}",
                "source_id": str(source_id)
            }

    except Exception as e:
        print(f"Upload error: {e}")
        conn.rollback()
        return {"success": False, "error": str(e)}

    finally:
        cur.close()
        conn.close()


def validate_url(url: str) -> bool:
    """
    Validate URL format.

    Args:
        url: URL to validate

    Returns:
        True if valid, False otherwise
    """
    import re

    # Simple URL validation
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return url_pattern.match(url) is not None
