"""Base SQL adapter implementation with common functionality."""
import json
import datetime
import asyncio
import logging
from abc import abstractmethod
from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..models import ExecutionRecord, Base
from .base import BaseAdapter
from ...error.exceptions import DatabaseError

logger = logging.getLogger(__name__)

class BaseSQLAdapter(BaseAdapter):
    """Base class for SQL database adapters with common functionality."""
    
    def __init__(self, connection_string: str):
        """Initialize the SQL adapter."""
        if not self._validate_connection_string(connection_string):
            raise ValueError("Invalid connection string")
            
        self.connection_string = connection_string
        self.pool = None
        self.engine = create_engine(connection_string)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.Base = Base
        self.ExecutionRecord = ExecutionRecord
    
    async def initialize(self) -> None:
        """Initialize the database schema."""
        try:
            # Create tables using SQLAlchemy
            self.Base.metadata.create_all(bind=self.engine)
            await self._initialize_pool()
            logger.info("Initialized database connection")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise DatabaseError(f"Database initialization failed: {str(e)}")
    
    @abstractmethod
    async def _initialize_pool(self) -> None:
        """Initialize the connection pool. Must be implemented by subclasses."""
        pass
    
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
        """Save an execution record with fallback to sync if async fails."""
        if self.pool:
            try:
                return await self._save_execution_async(
                    target_name, action, success, execution_time, error_message,
                    system_context, script, output, parameters, transaction_id, user_id
                )
            except Exception as e:
                logger.error(f"Async save failed, falling back to sync: {e}")
        
        return await self._save_execution_sync(
            target_name, action, success, execution_time, error_message,
            system_context, script, output, parameters, transaction_id, user_id
        )
    
    @abstractmethod
    async def _save_execution_async(self, **kwargs) -> int:
        """Save execution record using async driver. Must be implemented by subclasses."""
        pass
    
    async def _save_execution_sync(self, **kwargs) -> int:
        """Save execution record using SQLAlchemy in a thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._save_execution_sqlalchemy, **kwargs)
    
    def _save_execution_sqlalchemy(
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
            raise DatabaseError(f"Failed to save execution record: {str(e)}")
        finally:
            session.close()
    
    async def get_execution_history(
        self,
        target: str = None,
        action: str = None,
        limit: int = 100,
        user_id: str = None,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> List[Dict[str, Any]]:
        """Get execution history with optional filters."""
        if self.pool:
            try:
                return await self._get_execution_history_async(
                    target, action, limit, user_id, start_time, end_time
                )
            except Exception as e:
                logger.error(f"Async history retrieval failed, falling back to sync: {e}")
        
        return await self._get_execution_history_sync(
            target, action, limit, user_id, start_time, end_time
        )
    
    @abstractmethod
    async def _get_execution_history_async(self, **kwargs) -> List[Dict[str, Any]]:
        """Get execution history using async driver. Must be implemented by subclasses."""
        pass
    
    async def _get_execution_history_sync(self, **kwargs) -> List[Dict[str, Any]]:
        """Get execution history using SQLAlchemy in a thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_execution_history_sqlalchemy, **kwargs)
    
    def _get_execution_history_sqlalchemy(
        self,
        target: str = None,
        action: str = None,
        limit: int = 100,
        user_id: str = None,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> List[Dict[str, Any]]:
        """Synchronous version of get_execution_history using SQLAlchemy."""
        session = self.SessionLocal()
        try:
            query = self.ExecutionRecord.query
            
            if target:
                query = query.filter_by(target_name=target)
            if action:
                query = query.filter_by(action=action)
            if user_id:
                query = query.filter_by(user_id=user_id)
            if start_time:
                query = query.filter(self.ExecutionRecord.timestamp >= start_time)
            if end_time:
                query = query.filter(self.ExecutionRecord.timestamp <= end_time)
            
            records = query.order_by(self.ExecutionRecord.timestamp.desc()).limit(limit).all()
            
            return [{
                "id": record.id,
                "target_name": record.target_name,
                "action": record.action,
                "success": record.success,
                "execution_time": record.execution_time,
                "error_message": record.error_message,
                "timestamp": record.timestamp,
                "script": record.script,
                "output": json.loads(record.output),
                "parameters": json.loads(record.parameters),
                "transaction_id": record.transaction_id,
                "user_id": record.user_id
            } for record in records]
        except Exception as e:
            logger.error(f"Failed to retrieve execution history: {e}")
            raise DatabaseError(f"Failed to retrieve execution history: {str(e)}")
        finally:
            session.close()
    
    async def clear_history(
        self,
        target: str = None,
        action: str = None,
        user_id: str = None,
        before_time: datetime = None
    ) -> int:
        """Clear execution history with optional filters."""
        if self.pool:
            try:
                return await self._clear_history_async(target, action, user_id, before_time)
            except Exception as e:
                logger.error(f"Async history clearing failed, falling back to sync: {e}")
        
        return await self._clear_history_sync(target, action, user_id, before_time)
    
    @abstractmethod
    async def _clear_history_async(self, **kwargs) -> int:
        """Clear history using async driver. Must be implemented by subclasses."""
        pass
    
    async def _clear_history_sync(self, **kwargs) -> int:
        """Clear history using SQLAlchemy in a thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._clear_history_sqlalchemy, **kwargs)
    
    def _clear_history_sqlalchemy(
        self,
        target: str = None,
        action: str = None,
        user_id: str = None,
        before_time: datetime = None
    ) -> int:
        """Synchronous version of clear_history using SQLAlchemy."""
        session = self.SessionLocal()
        try:
            query = self.ExecutionRecord.query
            
            if target:
                query = query.filter_by(target_name=target)
            if action:
                query = query.filter_by(action=action)
            if user_id:
                query = query.filter_by(user_id=user_id)
            if before_time:
                query = query.filter(self.ExecutionRecord.timestamp < before_time)
            
            count = query.delete()
            session.commit()
            logger.info(f"Cleared {count} history records")
            return count
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
            session.rollback()
            raise DatabaseError(f"Failed to clear history: {str(e)}")
        finally:
            session.close()
    
    async def close(self) -> None:
        """Close database connections."""
        try:
            if self.pool:
                await self._close_pool()
            self.engine.dispose()
            logger.info("Closed database connections")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
            raise DatabaseError(f"Failed to close database connections: {str(e)}")
    
    @abstractmethod
    async def _close_pool(self) -> None:
        """Close the connection pool. Must be implemented by subclasses."""
        pass 