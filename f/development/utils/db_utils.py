"""
Database Utilities

Shared database connection and helper functions for all Windmill scripts.
Eliminates redundant connection setup across steps.
"""

import wmill
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Dict, Any, Optional


def get_db_params(db_resource: str = "f/development/business_layer_db_postgreSQL") -> Dict[str, Any]:
    """
    Get database connection parameters from Windmill resource.

    Args:
        db_resource: Windmill resource path for database credentials

    Returns:
        Dictionary of connection parameters for psycopg2.connect()
    """
    raw_config = wmill.get_resource(db_resource)
    return {
        "host": raw_config.get("host"),
        "port": raw_config.get("port"),
        "user": raw_config.get("user"),
        "password": raw_config.get("password"),
        "dbname": raw_config.get("dbname"),
        "sslmode": "disable",
    }


@contextmanager
def get_db_connection(db_resource: str = "f/development/business_layer_db_postgreSQL",
                      use_dict_cursor: bool = True):
    """
    Context manager for database connections with automatic cleanup.

    Usage:
        with get_db_connection() as (conn, cur):
            cur.execute("SELECT * FROM users")
            results = cur.fetchall()

    Args:
        db_resource: Windmill resource path for database credentials
        use_dict_cursor: If True, use RealDictCursor for dict-like row access

    Yields:
        Tuple of (connection, cursor)
    """
    db_params = get_db_params(db_resource)
    conn = None
    cur = None

    try:
        conn = psycopg2.connect(**db_params)
        cursor_factory = RealDictCursor if use_dict_cursor else None
        cur = conn.cursor(cursor_factory=cursor_factory)
        yield conn, cur
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def estimate_tokens(text: str) -> int:
    """
    Rough token estimation: ~4 characters per token.
    Used as fallback when actual token counts aren't available.

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count (minimum 1)
    """
    return max(len(text) // 4, 1)


def check_previous_steps(
    context_payload: dict,
    llm_result: Optional[dict] = None,
    send_result: Optional[dict] = None
) -> Optional[Dict[str, Any]]:
    """
    Common validation for checking if previous steps succeeded.

    Args:
        context_payload: Result from Step 1
        llm_result: Result from Step 2 (optional)
        send_result: Result from Step 3 (optional)

    Returns:
        None if all checks pass, or error dict if any step failed
    """
    # Check Step 1
    if not context_payload.get("proceed", False):
        reason = context_payload.get("reason", "Unknown error")
        print(f"Step 1 failed: {reason}")
        return {"success": False, "error": f"Cannot proceed - Step 1 failed: {reason}"}

    # Check Step 2 (if provided)
    if llm_result is not None and "error" in llm_result:
        error = llm_result.get("error", "Unknown error")
        print(f"Step 2 failed: {error}")
        return {"success": False, "error": f"Cannot proceed - Step 2 failed: {error}"}

    # Check Step 3 (if provided)
    if send_result is not None and not send_result.get("success", False):
        error = send_result.get("error", "Message not delivered")
        print(f"Step 3 failed: {error}")
        return {"success": False, "error": f"Cannot proceed - Step 3 failed: {error}"}

    return None  # All checks passed
