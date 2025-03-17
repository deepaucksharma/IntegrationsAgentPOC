# src/workflow_agent/storage/adapters/__init__.py
import os
import logging
from typing import Optional, Union
from .sqlite import SQLiteAdapter
from .postgres import PostgreSQLAdapter
from .mysql import MySQLAdapter

logger = logging.getLogger(__name__)

def get_adapter(connection_string: Optional[str] = None):
    """
    Get the appropriate database adapter based on environment or connection string.
    
    Args:
        connection_string: Optional database connection string
        
    Returns:
        Database adapter instance
    """
    # Get DB type from environment or derive from connection string
    if connection_string:
        if connection_string.startswith("postgresql://"):
            return PostgreSQLAdapter(connection_string)
        elif connection_string.startswith("mysql://"):
            return MySQLAdapter(connection_string)
        else:
            return SQLiteAdapter(connection_string)
    
    # Check environment variables
    db_type = os.getenv("WORKFLOW_HISTORY_DB_TYPE", "sqlite").lower()
    
    if db_type == "postgresql":
        host = os.getenv("WORKFLOW_HISTORY_DB_HOST", "localhost")
        port = os.getenv("WORKFLOW_HISTORY_DB_PORT", "5432")
        user = os.getenv("WORKFLOW_HISTORY_DB_USER", "postgres")
        password = os.getenv("WORKFLOW_HISTORY_DB_PASS", "postgres")
        db_name = os.getenv("WORKFLOW_HISTORY_DB_NAME", "workflow_history")
        conn_str = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
        return PostgreSQLAdapter(conn_str)
    elif db_type == "mysql":
        host = os.getenv("WORKFLOW_HISTORY_DB_HOST", "localhost")
        port = os.getenv("WORKFLOW_HISTORY_DB_PORT", "3306")
        user = os.getenv("WORKFLOW_HISTORY_DB_USER", "root")
        password = os.getenv("WORKFLOW_HISTORY_DB_PASS", "")
        db_name = os.getenv("WORKFLOW_HISTORY_DB_NAME", "workflow_history")
        conn_str = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"
        return MySQLAdapter(conn_str)
    else:
        # Default to SQLite
        db_path = os.getenv("WORKFLOW_HISTORY_DB", "workflow_history.db")
        return SQLiteAdapter(db_path)

__all__ = [
    "get_adapter",
    "SQLiteAdapter",
    "PostgreSQLAdapter",
    "MySQLAdapter"
]