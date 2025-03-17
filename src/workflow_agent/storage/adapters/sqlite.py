# src/workflow_agent/storage/adapters/sqlite.py
import os
import json
import aiosqlite
import datetime
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

class SQLiteAdapter:
    """SQLite implementation for history storage."""
    
    def __init__(self, db_path: str):
        """
        Initialize the SQLite adapter.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path).expanduser()
        
        # Create parent directories if they don't exist
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize SQLAlchemy engine and session
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Import ExecutionRecord model from parent module to avoid circular imports
        from ..models import Base, ExecutionRecord
        self.Base = Base
        self.ExecutionRecord = ExecutionRecord
    
    async def initialize(self):
        """Initialize the database schema."""
        # Create tables using SQLAlchemy
        self.Base.metadata.create_all(bind=self.engine)
        
        # Initialize async SQLite connection
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS execution_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_name TEXT,
                    action TEXT,
                    success INTEGER,
                    execution_time INTEGER,
                    error_message TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    system_context TEXT,
                    script TEXT,
                    output TEXT,
                    parameters TEXT,
                    transaction_id TEXT,
                    user_id TEXT
                )
            ''')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_target_name ON execution_records(target_name)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_action ON execution_records(action)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON execution_records(timestamp)')
            await db.commit()
            
        logger.info(f"Initialized SQLite database at {self.db_path}")
    
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
        Save an execution record to SQLite.
        
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
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute('''
                    INSERT INTO execution_records
                    (target_name, action, success, execution_time, error_message, 
                     system_context, script, output, parameters, transaction_id, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    target_name, 
                    action, 
                    1 if success else 0, 
                    execution_time, 
                    error_message, 
                    json.dumps(system_context), 
                    script, 
                    json.dumps(output) if output else "{}", 
                    json.dumps(parameters) if parameters else "{}",
                    transaction_id,
                    user_id
                ))
                await db.commit()
                record_id = cursor.lastrowid
                logger.info(f"Saved execution record with ID {record_id}")
                return record_id
        except Exception as e:
            logger.error(f"Failed to save execution record: {e}")
            raise e
    
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
        """Synchronous version of save_execution."""
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
    
    # Implement other methods similarly to the other adapter classes...
    async def get_execution_history(
        self,
        target: str,
        action: str,
        limit: int = 10,
        user_id: str = None
    ) -> List[Dict[str, Any]]:
        """Get execution history from SQLite."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                query = '''
                    SELECT * FROM execution_records
                    WHERE target_name = ? AND action = ?
                '''
                params = [target, action]
                
                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)
                    
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor = await db.execute(query, params)
                rows = await cursor.fetchall()
                
                history = []
                for row in rows:
                    history.append({
                        "id": row["id"],
                        "target_name": row["target_name"],
                        "action": row["action"],
                        "success": bool(row["success"]),
                        "execution_time": row["execution_time"],
                        "error_message": row["error_message"],
                        "timestamp": row["timestamp"],
                        "script": row["script"],
                        "output": json.loads(row["output"]),
                        "parameters": json.loads(row["parameters"]),
                        "transaction_id": row["transaction_id"],
                        "user_id": row["user_id"]
                    })
                return history
        except Exception as e:
            logger.error(f"Error retrieving execution history: {e}")
            return []
    
    # Additional methods would be implemented here
    
    async def close(self):
        """Close database connections."""
        # SQLite doesn't need explicit cleanup for async connections
        pass