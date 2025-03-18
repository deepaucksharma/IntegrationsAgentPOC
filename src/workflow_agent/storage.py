import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

class HistoryManager:
    """Manages workflow execution history with database support."""
    
    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or os.getenv(
            "WORKFLOW_DB_URL", 
            "sqlite+aiosqlite:///workflow_history.db"
        )
        self._engine = None
        self._session_factory = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize database connection and check driver support."""
        if self._initialized:
            return
            
        try:
            # Check if required database driver is installed
            if self.connection_string.startswith("postgresql"):
                try:
                    import asyncpg
                    logger.info("PostgreSQL driver (asyncpg) available")
                except ImportError:
                    logger.warning("PostgreSQL driver not installed, falling back to SQLite")
                    self.connection_string = "sqlite+aiosqlite:///workflow_history.db"
            
            elif self.connection_string.startswith("mysql"):
                try:
                    import aiomysql
                    logger.info("MySQL driver (aiomysql) available")
                except ImportError:
                    logger.warning("MySQL driver not installed, falling back to SQLite")
                    self.connection_string = "sqlite+aiosqlite:///workflow_history.db"
            
            # Create async engine
            self._engine = create_async_engine(
                self.connection_string,
                echo=False,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10
            )
            
            # Create session factory
            self._session_factory = sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Test connection
            async with self._engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            
            self._initialized = True
            logger.info(f"Database connection initialized successfully: {self.connection_string}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            raise
    
    async def close(self) -> None:
        """Close database connection."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._initialized = False
            logger.info("Database connection closed")
    
    async def get_session(self) -> AsyncSession:
        """Get a database session."""
        if not self._initialized:
            await self.initialize()
        return self._session_factory()
    
    async def record_execution(self, execution_data: Dict[str, Any]) -> None:
        """Record a workflow execution."""
        async with await self.get_session() as session:
            try:
                # Add timestamp if not provided
                if "timestamp" not in execution_data:
                    execution_data["timestamp"] = datetime.utcnow()
                
                # Insert execution record
                await session.execute(
                    text("""
                        INSERT INTO workflow_executions 
                        (transaction_id, action, target_name, parameters, result, timestamp)
                        VALUES (:transaction_id, :action, :target_name, :parameters, :result, :timestamp)
                    """),
                    execution_data
                )
                await session.commit()
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to record execution: {e}")
                raise
    
    async def get_execution_history(self, 
                                  target_name: Optional[str] = None,
                                  days: int = 30) -> List[Dict[str, Any]]:
        """Get execution history with optional filtering."""
        async with await self.get_session() as session:
            try:
                query = """
                    SELECT * FROM workflow_executions 
                    WHERE timestamp >= :start_date
                """
                params = {
                    "start_date": datetime.utcnow() - timedelta(days=days)
                }
                
                if target_name:
                    query += " AND target_name = :target_name"
                    params["target_name"] = target_name
                
                query += " ORDER BY timestamp DESC"
                
                result = await session.execute(text(query), params)
                return [dict(row) for row in result]
                
            except Exception as e:
                logger.error(f"Failed to get execution history: {e}")
                raise
    
    async def auto_prune_history(self, days: int) -> None:
        """Automatically prune old execution records."""
        async with await self.get_session() as session:
            try:
                await session.execute(
                    text("""
                        DELETE FROM workflow_executions 
                        WHERE timestamp < :cutoff_date
                    """),
                    {"cutoff_date": datetime.utcnow() - timedelta(days=days)}
                )
                await session.commit()
                logger.info(f"Pruned execution history older than {days} days")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to prune history: {e}")
                raise 