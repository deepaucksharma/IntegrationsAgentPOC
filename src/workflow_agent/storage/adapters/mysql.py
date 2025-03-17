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
from .base import BaseAdapter

logger = logging.getLogger(__name__)

class MySQLAdapter(BaseAdapter):
    """MySQL implementation for history storage."""
    
    def __init__(self, connection_string: str):
        """
        Initialize the MySQL adapter.
        
        Args:
            connection_string: MySQL connection string
        """
        if not self._validate_connection_string(connection_string):
            raise ValueError("Invalid connection string")
            
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
    
    async def initialize(self) -> None:
        """Initialize the database schema."""
        # Create tables using SQLAlchemy
        self.Base.metadata.create_all(bind=self.engine)
        
        # Initialize connection pool
        try:
            # Convert SQLAlchemy connection string to aiomysql format
            conn_str = self.connection_string.replace('mysql://', '')
            user_pass, host_port_db = conn_str.split('@')
            if ':' in user_pass:
                user, password = user_pass.split(':')
            else:
                user, password = user_pass, ''
            
            host_port, db = host_port_db.split('/')
            if ':' in host_port:
                host, port = host_port.split(':')
            else:
                host, port = host_port, '3306'
            
            # Create connection pool
            self.pool = await aiomysql.create_pool(
                user=user,
                password=password,
                db=db,
                host=host,
                port=int(port),
                minsize=1,
                maxsize=10
            )
            
            logger.info("Initialized MySQL connection pool")
        except Exception as e:
            logger.error(f"Failed to initialize MySQL pool: {e}")
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
        """Save an execution record to MySQL."""
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute('''
                            INSERT INTO execution_records
                            (target_name, action, success, execution_time, error_message, 
                             system_context, script, output, parameters, transaction_id, user_id, timestamp)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        await conn.commit()
                        record_id = cur.lastrowid
                        logger.info(f"Saved execution record with ID {record_id}")
                        return record_id
            except Exception as e:
                logger.error(f"Failed to save execution record with aiomysql: {e}")
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
    
    async def get_execution_history(
        self,
        target: str,
        action: str,
        limit: int = 10,
        user_id: str = None
    ) -> List[Dict[str, Any]]:
        """Get execution history from MySQL."""
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        query = '''
                            SELECT * FROM execution_records
                            WHERE target_name = %s AND action = %s
                        '''
                        params = [target, action]
                        
                        if user_id:
                            query += " AND user_id = %s"
                            params.append(user_id)
                            
                        query += " ORDER BY timestamp DESC LIMIT %s"
                        params.append(limit)
                        
                        await cur.execute(query, params)
                        rows = await cur.fetchall()
                        
                        history = []
                        for row in rows:
                            history.append({
                                "id": row[0],
                                "target_name": row[1],
                                "action": row[2],
                                "success": bool(row[3]),
                                "execution_time": row[4],
                                "error_message": row[5],
                                "timestamp": row[12],
                                "script": row[7],
                                "output": json.loads(row[8]),
                                "parameters": json.loads(row[9]),
                                "transaction_id": row[10],
                                "user_id": row[11]
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
                    async with conn.cursor() as cur:
                        query = '''
                            SELECT 
                                COUNT(*) as total_executions,
                                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_executions,
                                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_executions,
                                AVG(execution_time) as avg_execution_time,
                                MAX(CASE WHEN success = 1 THEN timestamp ELSE NULL END) as last_success_time,
                                MAX(CASE WHEN success = 0 THEN timestamp ELSE NULL END) as last_failure_time,
                                MAX(timestamp) as last_execution_time
                            FROM execution_records
                            WHERE target_name = %s AND action = %s
                        '''
                        params = [target, action]
                        
                        if user_id:
                            query += " AND user_id = %s"
                            params.append(user_id)
                        
                        await cur.execute(query, params)
                        row = await cur.fetchone()
                        
                        if not row or row[0] == 0:
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
                            "total_executions": row[0],
                            "successful_executions": row[1],
                            "failed_executions": row[2],
                            "avg_execution_time": round(float(row[3]), 2) if row[3] else 0,
                            "success_rate": round((row[1] / row[0]) * 100, 2),
                            "last_execution_time": row[6],
                            "last_success_time": row[4],
                            "last_failure_time": row[5]
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
                    async with conn.cursor() as cur:
                        # Build the WHERE clause
                        where_clauses = []
                        params = []
                        
                        if target:
                            where_clauses.append("target_name = %s")
                            params.append(target)
                        
                        if action:
                            where_clauses.append("action = %s")
                            params.append(action)
                        
                        if user_id:
                            where_clauses.append("user_id = %s")
                            params.append(user_id)
                        
                        if days:
                            where_clauses.append("timestamp < DATE_SUB(NOW(), INTERVAL %s DAY)")
                            params.append(days)
                        
                        # Construct the query
                        query = "DELETE FROM execution_records"
                        if where_clauses:
                            query += " WHERE " + " AND ".join(where_clauses)
                        
                        # Execute the query
                        await cur.execute(query, params)
                        await conn.commit()
                        count = cur.rowcount
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
    
    async def close(self) -> None:
        """Close database connections."""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("Closed MySQL connection pool")