import logging
from typing import Optional
from .base import BaseAdapter
from .postgres import PostgreSQLAdapter
from .mysql import MySQLAdapter
from .sqlite import SQLiteAdapter

logger = logging.getLogger(__name__)

def create_adapter(connection_string: str) -> BaseAdapter:
    """
    Create a database adapter based on the connection string.
    
    Args:
        connection_string: Database connection string
        
    Returns:
        BaseAdapter: An instance of the appropriate database adapter
        
    Raises:
        ValueError: If the connection string is invalid or unsupported
    """
    if not connection_string:
        raise ValueError("Connection string cannot be empty")
    
    # Check connection string format
    if connection_string.startswith('postgresql://'):
        return PostgreSQLAdapter(connection_string)
    elif connection_string.startswith('mysql://'):
        return MySQLAdapter(connection_string)
    elif connection_string.startswith('sqlite://') or connection_string.startswith('sqlite3://'):
        return SQLiteAdapter(connection_string)
    else:
        raise ValueError(f"Unsupported database connection string format: {connection_string}") 