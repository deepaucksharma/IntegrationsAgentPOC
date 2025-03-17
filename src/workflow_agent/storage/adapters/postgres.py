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
from .base import BaseAdapter
from .base_sql import BaseSQLAdapter
from ...error.exceptions import DatabaseError

logger = logging.getLogger(__name__)

class PostgreSQLAdapter(BaseSQLAdapter):
    """PostgreSQL implementation for history storage."""
    
    def __init__(self, connection_string: str):
        """
        Initialize the PostgreSQL adapter.
        
        Args:
            connection_string: PostgreSQL connection string
        """
        if not self._validate_connection_string(connection_string):
            raise ValueError("Invalid connection string")
            
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
    
    async def initialize(self) -> None:
        """Initialize the database schema."""
        # Create tables using SQLAlchemy
        self.Base.metadata.create_all(bind=self.engine)
        
        # Initialize connection pool
        await self._initialize_pool()
    
    async def _initialize_pool(self) -> None:
        """Initialize the PostgreSQL connection pool."""
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
                port=port,
                min_size=1,
                max_size=10
            )
            
            logger.info("Initialized PostgreSQL connection pool")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            raise DatabaseError(f"Failed to initialize PostgreSQL pool: {str(e)}")
    
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
        """Save an execution record to PostgreSQL."""
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
    
    async def _save_execution_async(
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
        """Save execution record using asyncpg."""
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
    
    async def get_execution_history(
        self,
        target: str,
        action: str,
        limit: int = 10,
        user_id: str = None
    ) -> List[Dict[str, Any]]:
        """Get execution history from PostgreSQL."""
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    query = '''
                        SELECT * FROM execution_records
                        WHERE target_name = $1 AND action = $2
                    '''
                    params = [target, action]
                    
                    if user_id:
                        query += " AND user_id = $3"
                        params.append(user_id)
                        
                    query += " ORDER BY timestamp DESC LIMIT $" + str(len(params) + 1)
                    params.append(limit)
                    
                    rows = await conn.fetch(query, *params)
                    
                    history = []
                    for row in rows:
                        history.append({
                            "id": row['id'],
                            "target_name": row['target_name'],
                            "action": row['action'],
                            "success": row['success'],
                            "execution_time": row['execution_time'],
                            "error_message": row['error_message'],
                            "timestamp": row['timestamp'],
                            "script": row['script'],
                            "output": json.loads(row['output']),
                            "parameters": json.loads(row['parameters']),
                            "transaction_id": row['transaction_id'],
                            "user_id": row['user_id']
                        })
                    return history
            except Exception as e:
                logger.error(f"Error retrieving execution history: {e}")
                return []
        else:
            # Fall back to SQLAlchemy
            session = self.SessionLocal()
            try:
                query = self.ExecutionRecord.query.filter_by(
                    target_name=target,
                    action=action
                )
                if user_id:
                    query = query.filter_by(user_id=user_id)
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
                logger.error(f"Error retrieving execution history: {e}")
                return []
            finally:
                session.close()
    
    async def _get_execution_history_async(
        self,
        target: str = None,
        action: str = None,
        limit: int = 100,
        user_id: str = None,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> List[Dict[str, Any]]:
        """Get execution history using asyncpg."""
        async with self.pool.acquire() as conn:
            query = '''
                SELECT * FROM execution_records
                WHERE 1=1
            '''
            params = []
            param_count = 1
            
            if target:
                query += f" AND target_name = ${param_count}"
                params.append(target)
                param_count += 1
            
            if action:
                query += f" AND action = ${param_count}"
                params.append(action)
                param_count += 1
            
            if user_id:
                query += f" AND user_id = ${param_count}"
                params.append(user_id)
                param_count += 1
            
            if start_time:
                query += f" AND timestamp >= ${param_count}"
                params.append(start_time)
                param_count += 1
            
            if end_time:
                query += f" AND timestamp <= ${param_count}"
                params.append(end_time)
                param_count += 1
            
            query += f" ORDER BY timestamp DESC LIMIT ${param_count}"
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            
            return [{
                "id": row['id'],
                "target_name": row['target_name'],
                "action": row['action'],
                "success": row['success'],
                "execution_time": row['execution_time'],
                "error_message": row['error_message'],
                "timestamp": row['timestamp'],
                "script": row['script'],
                "output": json.loads(row['output']),
                "parameters": json.loads(row['parameters']),
                "transaction_id": row['transaction_id'],
                "user_id": row['user_id']
            } for row in rows]
    
    async def get_execution_statistics(
        self,
        target: str,
        action: str,
        user_id: str = None
    ) -> Dict[str, Any]:
        """Get execution statistics for a specific target and action."""
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    query = '''
                        SELECT 
                            COUNT(*) as total_executions,
                            SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as successful_executions,
                            SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failed_executions,
                            AVG(execution_time) as avg_execution_time,
                            MAX(CASE WHEN success = true THEN timestamp ELSE NULL END) as last_success_time,
                            MAX(CASE WHEN success = false THEN timestamp ELSE NULL END) as last_failure_time,
                            MAX(timestamp) as last_execution_time
                        FROM execution_records
                        WHERE target_name = $1 AND action = $2
                    '''
                    params = [target, action]
                    
                    if user_id:
                        query += " AND user_id = $3"
                        params.append(user_id)
                    
                    row = await conn.fetchrow(query, *params)
                    
                    if not row or row['total_executions'] == 0:
                        return {
                            "total_executions": 0,
                            "successful_executions": 0,
                            "failed_executions": 0,
                            "avg_execution_time": 0,
                            "success_rate": 0,
                            "last_execution_time": None,
                            "last_success_time": None,
                            "last_failure_time": None
                        }
                    
                    return {
                        "total_executions": row['total_executions'],
                        "successful_executions": row['successful_executions'],
                        "failed_executions": row['failed_executions'],
                        "avg_execution_time": round(float(row['avg_execution_time']), 2) if row['avg_execution_time'] else 0,
                        "success_rate": round((row['successful_executions'] / row['total_executions']) * 100, 2),
                        "last_execution_time": row['last_execution_time'],
                        "last_success_time": row['last_success_time'],
                        "last_failure_time": row['last_failure_time']
                    }
            except Exception as e:
                logger.error(f"Error retrieving execution statistics: {e}")
                return {
                    "total_executions": 0,
                    "successful_executions": 0,
                    "failed_executions": 0,
                    "avg_execution_time": 0,
                    "success_rate": 0,
                    "last_execution_time": None,
                    "last_success_time": None,
                    "last_failure_time": None
                }
        else:
            # Fall back to SQLAlchemy
            session = self.SessionLocal()
            try:
                query = self.ExecutionRecord.query.filter_by(
                    target_name=target,
                    action=action
                )
                if user_id:
                    query = query.filter_by(user_id=user_id)
                
                records = query.all()
                if not records:
                    return {
                        "total_executions": 0,
                        "successful_executions": 0,
                        "failed_executions": 0,
                        "avg_execution_time": 0,
                        "success_rate": 0,
                        "last_execution_time": None,
                        "last_success_time": None,
                        "last_failure_time": None
                    }
                
                total = len(records)
                successful = sum(1 for r in records if r.success)
                failed = total - successful
                avg_time = sum(r.execution_time for r in records) / total if total > 0 else 0
                
                last_success = max((r.timestamp for r in records if r.success), default=None)
                last_failure = max((r.timestamp for r in records if not r.success), default=None)
                last_execution = max(r.timestamp for r in records)
                
                return {
                    "total_executions": total,
                    "successful_executions": successful,
                    "failed_executions": failed,
                    "avg_execution_time": round(avg_time, 2),
                    "success_rate": round((successful / total) * 100, 2),
                    "last_execution_time": last_execution,
                    "last_success_time": last_success,
                    "last_failure_time": last_failure
                }
            except Exception as e:
                logger.error(f"Error retrieving execution statistics: {e}")
                return {
                    "total_executions": 0,
                    "successful_executions": 0,
                    "failed_executions": 0,
                    "avg_execution_time": 0,
                    "success_rate": 0,
                    "last_execution_time": None,
                    "last_success_time": None,
                    "last_failure_time": None
                }
            finally:
                session.close()
    
    async def clear_history(
        self,
        target: str = None,
        action: str = None,
        days: int = None,
        user_id: str = None
    ) -> int:
        """Clear execution history records."""
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    # Build the WHERE clause
                    where_clauses = []
                    params = []
                    param_count = 1
                    
                    if target:
                        where_clauses.append(f"target_name = ${param_count}")
                        params.append(target)
                        param_count += 1
                    
                    if action:
                        where_clauses.append(f"action = ${param_count}")
                        params.append(action)
                        param_count += 1
                    
                    if user_id:
                        where_clauses.append(f"user_id = ${param_count}")
                        params.append(user_id)
                        param_count += 1
                    
                    if days:
                        where_clauses.append(f"timestamp < NOW() - INTERVAL '${param_count} days'")
                        params.append(days)
                        param_count += 1
                    
                    # Construct the query
                    query = "DELETE FROM execution_records"
                    if where_clauses:
                        query += " WHERE " + " AND ".join(where_clauses)
                    
                    # Execute the query
                    result = await conn.execute(query, *params)
                    count = int(result.split()[-1])
                    logger.info(f"Cleared {count} execution records")
                    return count
            except Exception as e:
                logger.error(f"Error clearing execution history: {e}")
                return 0
        else:
            # Fall back to SQLAlchemy
            session = self.SessionLocal()
            try:
                query = self.ExecutionRecord.query
                
                if target:
                    query = query.filter_by(target_name=target)
                if action:
                    query = query.filter_by(action=action)
                if user_id:
                    query = query.filter_by(user_id=user_id)
                if days:
                    query = query.filter(
                        self.ExecutionRecord.timestamp < datetime.datetime.utcnow() - datetime.timedelta(days=days)
                    )
                
                count = query.delete()
                session.commit()
                logger.info(f"Cleared {count} execution records")
                return count
            except Exception as e:
                logger.error(f"Error clearing execution history: {e}")
                session.rollback()
                return 0
            finally:
                session.close()
    
    async def _clear_history_async(
        self,
        target: str = None,
        action: str = None,
        user_id: str = None,
        before_time: datetime = None
    ) -> int:
        """Clear history using asyncpg."""
        async with self.pool.acquire() as conn:
            query = '''
                DELETE FROM execution_records
                WHERE 1=1
            '''
            params = []
            param_count = 1
            
            if target:
                query += f" AND target_name = ${param_count}"
                params.append(target)
                param_count += 1
            
            if action:
                query += f" AND action = ${param_count}"
                params.append(action)
                param_count += 1
            
            if user_id:
                query += f" AND user_id = ${param_count}"
                params.append(user_id)
                param_count += 1
            
            if before_time:
                query += f" AND timestamp < ${param_count}"
                params.append(before_time)
            
            result = await conn.execute(query, *params)
            count = int(result.split()[-1])
            logger.info(f"Cleared {count} history records")
            return count
    
    async def close(self) -> None:
        """Close database connections."""
        if self.pool:
            await self.pool.close()
            logger.info("Closed PostgreSQL connection pool")
    
    async def _close_pool(self) -> None:
        """Close the PostgreSQL connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Closed PostgreSQL connection pool")