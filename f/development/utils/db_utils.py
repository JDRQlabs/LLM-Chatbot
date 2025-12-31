"""
Database Utilities

Shared database connection and helper functions for Windmill scripts.
Eliminates redundant connection setup across steps.

NOTE: This module requires wmill and psycopg2-binary.
For pure Python helpers with no dependencies, use flow_utils.py instead.
"""

import wmill
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Dict, Any


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
