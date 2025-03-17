# src/workflow_agent/storage/adapters/mysql.py
import json
import datetime
import asyncio
import logging
from typing import Dict, Any, List, Optional
import aiomysql
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..models import ExecutionRecord

logger = logging.getLogger(__name__)

class MySQLAdapter:
    """MySQL implementation for history storage."""
    
    def __init__(self, connection_string: str):
        """
        Initialize the MySQL adapter.
        
        Args:
            connection_string: MySQL connection string
        """
        self.connection_string = connection_string
        
        # For aiomysql (async)
        self.pool = None
        
        # For SQLAlchemy (sync)
        self.engine = create_engine(connection_string)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Import ExecutionRecord model from parent module to avoid circular imports
        from ..models import Base
        self.Base = Base
        self.ExecutionRecord = ExecutionRecord
    
    async def initialize(self):
        """Initialize the database schema."""
        # Create tables using SQLAlchemy
        self.Base.metadata.create_all(bind=self.engine)
        
        # Initialize connection pool
        try:
            # Parse connection string
            # Example format: mysql+pymysql://user:password@host:port/dbname
            conn_str = self.connection_string.replace('mysql+pymysql://', '')
            user_pass, host_port_db = conn_str.split('@')
            if ':' in user_pass:
                user, password = user_pass.split(':')
            else:
                user, password = user_pass, ''
            
            host_port, db = host_port_db.split('/')
            if ':' in host_port:
                host, port = host_port.split(':')
                port = int(port)
            else:
                host, port = host_port, 3306
            
            # Create connection pool
            self.pool = await aiomysql.create_pool(
                host=host,
                port=port,
                user=user,
                password=password,
                db=db,
                autocommit=True
            )
            
            logger.info("Initialized MySQL connection pool")
        except Exception as e:
            logger.error(f"Failed to initialize MySQL pool: {e}")
            # Fall back to synchronous operations
            self.pool = None
    
    # Implement methods similar to PostgreSQLAdapter
    
    async def close(self):
        """Close database connections."""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("Closed MySQL connection pool")