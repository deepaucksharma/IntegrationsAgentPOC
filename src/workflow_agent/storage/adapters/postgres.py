    # src/workflow_agent/storage/adapters/postgres.py
import json
import datetime
import asyncio
import logging
from typing import Dict, Any, List, Optional
import asyncpg
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..models import ExecutionRecord

logger = logging.getLogger(__name__)

class PostgreSQLAdapter:
    """PostgreSQL implementation for history storage."""
    
    def __init__(self, connection_string: str):
        """
        Initialize the PostgreSQL adapter.
        
        Args:
            connection_string: PostgreSQL connection string
        """
        self.connection_string = connection_string
        
        # For asyncpg (async)
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
            # Convert SQLAlchemy connection string to asyncpg format
            conn_str = self.connection_string.replace('postgresql://', '')
            user_pass, host_port_db = conn_str.split('@')
            if ':' in user_pass:
                user, password = user_pass.split(':')
            else:
                user, password = user_pass, ''
            
            host_port, db = host_port_db.split('/')
            if ':' in host_port:
                host, port = host_port.split(':')
            else:
                host, port = host_port, '5432'
            
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                user=user,
                password=password,
                database=db,
                host=host,
                port=port
            )
            
            logger.info("Initialized PostgreSQL connection pool")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            # Fall back to synchronous operations
            self.pool = None
    
    async def save_execution(
        self,
        target_name: str,
        action: str,
        success: bool,
        execution_time: int,
        error_message: Optional[str],
        system_context: dict,
        script: str,
        output: dict = None,
        parameters: dict = None,
        transaction_id: str = None,
        user_id: str = None
    ) -> int:
        """
        Save an execution record to PostgreSQL.
        
        Args:
            target_name: Name of the target system
            action: Action performed
            success: Whether the execution was successful
            execution_time: Time taken for execution in milliseconds
            error_message: Error message if execution failed
            system_context: System context information
            script: Script that was executed
            output: Output from script execution
            parameters: Parameters used for execution
            transaction_id: ID for tracking related operations
            user_id: ID of user who initiated the execution
            
        Returns:
            ID of the saved record
        """
        # Use asyncpg if pool is available, otherwise fall back to SQLAlchemy
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    result = await conn.fetchrow('''
                        INSERT INTO execution_records
                        (target_name, action, success, execution_time, error_message, 
                         system_context, script, output, parameters, transaction_id, user_id, timestamp)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        RETURNING id
                    ''', 
                    target_name, 
                    action, 
                    success, 
                    execution_time, 
                    error_message, 
                    json.dumps(system_context), 
                    script, 
                    json.dumps(output) if output else "{}", 
                    json.dumps(parameters) if parameters else "{}",
                    transaction_id,
                    user_id,
                    datetime.datetime.utcnow()
                    )
                    
                    record_id = result['id']
                    logger.info(f"Saved execution record with ID {record_id}")
                    return record_id
            except Exception as e:
                logger.error(f"Failed to save execution record with asyncpg: {e}")
                return await self._save_execution_sqlalchemy(
                    target_name, action, success, execution_time, error_message,
                    system_context, script, output, parameters, transaction_id, user_id
                )
        else:
            return await self._save_execution_sqlalchemy(
                target_name, action, success, execution_time, error_message,
                system_context, script, output, parameters, transaction_id, user_id
            )
    
    async def _save_execution_sqlalchemy(
        self,
        target_name: str,
        action: str,
        success: bool,
        execution_time: int,
        error_message: Optional[str],
        system_context: dict,
        script: str,
        output: dict = None,
        parameters: dict = None,
        transaction_id: str = None,
        user_id: str = None
    ) -> int:
        """Save execution record using SQLAlchemy."""
        # Run synchronous SQLAlchemy in a thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.save_execution_sync,
            target_name, action, success, execution_time, error_message,
            system_context, script, output, parameters, transaction_id, user_id
        )
    
    def save_execution_sync(
        self,
        target_name: str,
        action: str,
        success: bool,
        execution_time: int,
        error_message: Optional[str],
        system_context: dict,
        script: str,
        output: dict = None,
        parameters: dict = None,
        transaction_id: str = None,
        user_id: str = None
    ) -> int:
        """Synchronous version of save_execution using SQLAlchemy."""
        session = self.SessionLocal()
        try:
            record = self.ExecutionRecord(
                target_name=target_name,
                action=action,
                success=success,
                execution_time=execution_time,
                error_message=error_message,
                system_context=json.dumps(system_context),
                script=script,
                output=json.dumps(output) if output else "{}",
                parameters=json.dumps(parameters) if parameters else "{}",
                transaction_id=transaction_id,
                user_id=user_id
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            logger.info(f"Saved execution record with ID {record.id}")
            return record.id
        except Exception as e:
            logger.error(f"Failed to save execution record: {e}")
            session.rollback()
            raise e
        finally:
            session.close()
    
    # Additional methods would be implemented here, similar to SQLiteAdapter
    
    async def close(self):
        """Close database connections."""
        if self.pool:
            await self.pool.close()
            logger.info("Closed PostgreSQL connection pool")