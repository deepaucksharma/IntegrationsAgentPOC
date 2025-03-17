import os
import json
import datetime
import logging
from typing import Any, Dict, List, Optional, Union, Tuple
import asyncio
import aiosqlite
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, Text, DateTime, MetaData, Table, select, func, and_, desc, delete
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from ..shared.config import merge_configs

logger = logging.getLogger(__name__)

# Get DB path and type from environment
DB_PATH = os.getenv("WORKFLOW_HISTORY_DB", "workflow_history.db")
DB_TYPE = os.getenv("WORKFLOW_HISTORY_DB_TYPE", "sqlite")

# Determine connection string based on DB type
if DB_TYPE.lower() == "sqlite":
    DB_CONNECTION = f"sqlite:///{DB_PATH}"
elif DB_TYPE.lower() == "postgresql":
    DB_HOST = os.getenv("WORKFLOW_HISTORY_DB_HOST", "localhost")
    DB_PORT = os.getenv("WORKFLOW_HISTORY_DB_PORT", "5432")
    DB_USER = os.getenv("WORKFLOW_HISTORY_DB_USER", "postgres")
    DB_PASS = os.getenv("WORKFLOW_HISTORY_DB_PASS", "postgres")
    DB_NAME = os.getenv("WORKFLOW_HISTORY_DB_NAME", "workflow_history")
    DB_CONNECTION = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
elif DB_TYPE.lower() == "mysql":
    DB_HOST = os.getenv("WORKFLOW_HISTORY_DB_HOST", "localhost")
    DB_PORT = os.getenv("WORKFLOW_HISTORY_DB_PORT", "3306")
    DB_USER = os.getenv("WORKFLOW_HISTORY_DB_USER", "root")
    DB_PASS = os.getenv("WORKFLOW_HISTORY_DB_PASS", "")
    DB_NAME = os.getenv("WORKFLOW_HISTORY_DB_NAME", "workflow_history")
    DB_CONNECTION = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    logger.warning(f"Unsupported database type: {DB_TYPE}, falling back to SQLite")
    DB_CONNECTION = f"sqlite:///{DB_PATH}"

logger.info(f"Using database connection: {DB_CONNECTION.split('@')[-1]}")

# Create engine with appropriate settings
if DB_TYPE.lower() == "sqlite":
    engine = create_engine(
        DB_CONNECTION, 
        echo=False, 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
else:
    engine = create_engine(
        DB_CONNECTION,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800
    )

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class ExecutionRecord(Base):
    __tablename__ = "execution_records"

    id = Column(Integer, primary_key=True, index=True)
    target_name = Column(String(255), index=True)
    action = Column(String(50), index=True)
    success = Column(Boolean, default=False)
    execution_time = Column(Integer)  # in milliseconds
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    system_context = Column(Text)  # JSON string
    script = Column(Text)
    output = Column(Text)         # JSON string
    parameters = Column(Text)     # JSON string
    transaction_id = Column(String(36), nullable=True)  # For tracking related operations
    user_id = Column(String(50), nullable=True)  # Who initiated the execution

# Create tables if they don't exist.
Base.metadata.create_all(bind=engine)

# Expose a session class for history usage.
Session = SessionLocal

# Configure the async SQLite database for improved concurrency
async def init_async_db():
    """Initialize the async SQLite database."""
    db_path = Path(DB_PATH)
    
    # Create parent directories if they don't exist
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create table if it doesn't exist
    async with aiosqlite.connect(DB_PATH) as db:
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

# Initialize the async database
if DB_TYPE.lower() == "sqlite":
    # Run the async initialization
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(init_async_db())
        else:
            loop.run_until_complete(init_async_db())
    except RuntimeError:
        # If no event loop is available, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(init_async_db())

async def async_save_execution(
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
    Asynchronously save an execution record to the database.
    
    Args:
        target_name: Name of the target system
        action: Action performed (install, remove, etc.)
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
    if DB_TYPE.lower() == "sqlite":
        try:
            async with aiosqlite.connect(DB_PATH) as db:
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
    else:
        # For non-SQLite databases, use SQLAlchemy
        try:
            record = ExecutionRecord(
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
            session = SessionLocal()
            try:
                session.add(record)
                session.commit()
                session.refresh(record)
                logger.info(f"Saved execution record with ID {record.id}")
                return record.id
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Failed to save execution record: {e}")
            raise e

def save_execution(
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
    Save an execution record to the database (synchronous version).
    
    Args:
        target_name: Name of the target system
        action: Action performed (install, remove, etc.)
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
    session = SessionLocal()
    try:
        record = ExecutionRecord(
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

async def async_get_execution_history(target: str, action: str, limit: int = 10, user_id: str = None) -> List[Dict[str, Any]]:
    """
    Asynchronously retrieve the most recent execution records for a given target and action.
    
    Args:
        target: Target name to filter by
        action: Action to filter by
        limit: Maximum number of records to return
        user_id: Optional user ID to filter by
        
    Returns:
        List of execution records
    """
    if DB_TYPE.lower() == "sqlite":
        try:
            async with aiosqlite.connect(DB_PATH) as db:
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
    else:
        # For non-SQLite databases, use SQLAlchemy
        try:
            session = SessionLocal()
            try:
                query = session.query(ExecutionRecord).filter(
                    ExecutionRecord.target_name == target,
                    ExecutionRecord.action == action
                )
                
                if user_id:
                    query = query.filter(ExecutionRecord.user_id == user_id)
                    
                records = query.order_by(ExecutionRecord.timestamp.desc()).limit(limit).all()
                
                history = []
                for rec in records:
                    history.append({
                        "id": rec.id,
                        "target_name": rec.target_name,
                        "action": rec.action,
                        "success": rec.success,
                        "execution_time": rec.execution_time,
                        "error_message": rec.error_message,
                        "timestamp": rec.timestamp.isoformat(),
                        "script": rec.script,
                        "output": json.loads(rec.output),
                        "parameters": json.loads(rec.parameters),
                        "transaction_id": rec.transaction_id,
                        "user_id": rec.user_id
                    })
                return history
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error retrieving execution history: {e}")
            return []

def get_execution_history(target: str, action: str, limit: int = 10, user_id: str = None) -> List[Dict[str, Any]]:
    """
    Retrieve the most recent execution records for a given target and action.
    
    Args:
        target: Target name to filter by
        action: Action to filter by
        limit: Maximum number of records to return
        user_id: Optional user ID to filter by
        
    Returns:
        List of execution records
    """
    session = SessionLocal()
    try:
        query = session.query(ExecutionRecord).filter(
            ExecutionRecord.target_name == target,
            ExecutionRecord.action == action
        )
        
        if user_id:
            query = query.filter(ExecutionRecord.user_id == user_id)
            
        records = query.order_by(ExecutionRecord.timestamp.desc()).limit(limit).all()
        
        history = []
        for rec in records:
            history.append({
                "id": rec.id,
                "target_name": rec.target_name,
                "action": rec.action,
                "success": rec.success,
                "execution_time": rec.execution_time,
                "error_message": rec.error_message,
                "timestamp": rec.timestamp.isoformat(),
                "script": rec.script,
                "output": json.loads(rec.output),
                "parameters": json.loads(rec.parameters),
                "transaction_id": rec.transaction_id,
                "user_id": rec.user_id
            })
        return history
    except Exception as e:
        logger.error(f"Error retrieving execution history: {e}")
        return []
    finally:
        session.close()

def get_execution_statistics(target: str, action: str, user_id: str = None) -> Dict[str, Any]:
    """
    Compute statistics from the execution records.
    
    Args:
        target: Target name to filter by
        action: Action to filter by
        user_id: Optional user ID to filter by
        
    Returns:
        Dictionary with execution statistics
    """
    session = SessionLocal()
    try:
        query = session.query(ExecutionRecord).filter(
            ExecutionRecord.target_name == target,
            ExecutionRecord.action == action
        )
        
        if user_id:
            query = query.filter(ExecutionRecord.user_id == user_id)
            
        records = query.all()
        total = len(records)
        
        if total == 0:
            return {"total_executions": 0, "success_rate": 0.0, "average_execution_time": 0, "common_errors": []}
        
        successes = [r for r in records if r.success]
        success_rate = len(successes) / total
        avg_time = sum(r.execution_time for r in records) / total

        # Gather common errors (as a simple frequency count)
        error_freq = {}
        for r in records:
            if r.error_message:
                error_msg = r.error_message[:100]
                error_freq[error_msg] = error_freq.get(error_msg, 0) + 1
                
        common_errors = [{"message": msg, "count": count} for msg, count in error_freq.items()]
        common_errors.sort(key=lambda x: x["count"], reverse=True)

        # Calculate success trend (last 10 vs previous 10)
        recent = query.order_by(ExecutionRecord.timestamp.desc()).limit(10).all()
        recent_success_rate = len([r for r in recent if r.success]) / len(recent) if recent else 0
        
        older = query.order_by(ExecutionRecord.timestamp.desc()).offset(10).limit(10).all()
        older_success_rate = len([r for r in older if r.success]) / len(older) if older else 0
        
        success_trend = recent_success_rate - older_success_rate if older else 0

        return {
            "total_executions": total,
            "success_rate": success_rate,
            "average_execution_time": avg_time,
            "success_trend": success_trend,
            "last_execution": records[0].timestamp.isoformat() if records else None,
            "common_errors": common_errors
        }
    except Exception as e:
        logger.error(f"Error computing execution statistics: {e}")
        return {}
    finally:
        session.close()

async def async_clear_history(target: str = None, action: str = None, days: int = None, user_id: str = None) -> int:
    """
    Asynchronously clear execution history from the database.
    
    Args:
        target: Optional target name to filter by
        action: Optional action to filter by
        days: Optional number of days to keep (older records will be deleted)
        user_id: Optional user ID to filter by
        
    Returns:
        Number of records deleted
    """
    if DB_TYPE.lower() == "sqlite":
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                query = 'DELETE FROM execution_records WHERE 1=1'
                params = []
                
                if target:
                    query += " AND target_name = ?"
                    params.append(target)
                    
                if action:
                    query += " AND action = ?"
                    params.append(action)
                    
                if days:
                    cutoff_date = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
                    query += " AND timestamp < ?"
                    params.append(cutoff_date)
                    
                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)
                    
                cursor = await db.execute(query, params)
                await db.commit()
                count = cursor.rowcount
                logger.info(f"Cleared {count} execution records.")
                return count
        except Exception as e:
            logger.error(f"Error clearing execution history: {e}")
            return 0
    else:
        # For non-SQLite databases, use SQLAlchemy
        try:
            session = SessionLocal()
            try:
                query = session.query(ExecutionRecord)
                
                if target:
                    query = query.filter(ExecutionRecord.target_name == target)
                    
                if action:
                    query = query.filter(ExecutionRecord.action == action)
                    
                if days:
                    cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)
                    query = query.filter(ExecutionRecord.timestamp < cutoff_date)
                    
                if user_id:
                    query = query.filter(ExecutionRecord.user_id == user_id)
                    
                count = query.delete(synchronize_session=False)
                session.commit()
                logger.info(f"Cleared {count} execution records.")
                return count
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error clearing execution history: {e}")
            return 0

def clear_history(target: str = None, action: str = None, days: int = None, user_id: str = None) -> int:
    """
    Clear execution history from the database.
    
    Args:
        target: Optional target name to filter by
        action: Optional action to filter by
        days: Optional number of days to keep (older records will be deleted)
        user_id: Optional user ID to filter by
        
    Returns:
        Number of records deleted
    """
    session = SessionLocal()
    try:
        query = session.query(ExecutionRecord)
        
        if target:
            query = query.filter(ExecutionRecord.target_name == target)
            
        if action:
            query = query.filter(ExecutionRecord.action == action)
            
        if days:
            cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)
            query = query.filter(ExecutionRecord.timestamp < cutoff_date)
            
        if user_id:
            query = query.filter(ExecutionRecord.user_id == user_id)
            
        count = query.delete(synchronize_session=False)
        session.commit()
        logger.info(f"Cleared {count} execution records.")
        return count
    except Exception as e:
        logger.error(f"Error clearing execution history: {e}")
        session.rollback()
        return 0
    finally:
        session.close()

def auto_prune_history(days: int = 90) -> None:
    """
    Automatically prune old history records.
    
    Args:
        days: Number of days to keep (older records will be deleted)
    """
    try:
        count = clear_history(days=days)
        logger.info(f"Auto-pruned {count} execution records older than {days} days.")
    except Exception as e:
        logger.error(f"Error auto-pruning execution history: {e}")

def get_transaction_history(transaction_id: str) -> List[Dict[str, Any]]:
    """
    Get all records associated with a transaction.
    
    Args:
        transaction_id: Transaction ID to filter by
        
    Returns:
        List of execution records
    """
    session = SessionLocal()
    try:
        records = session.query(ExecutionRecord).filter(
            ExecutionRecord.transaction_id == transaction_id
        ).order_by(ExecutionRecord.timestamp.asc()).all()
        
        history = []
        for rec in records:
            history.append({
                "id": rec.id,
                "target_name": rec.target_name,
                "action": rec.action,
                "success": rec.success,
                "execution_time": rec.execution_time,
                "error_message": rec.error_message,
                "timestamp": rec.timestamp.isoformat(),
                "script": rec.script,
                "output": json.loads(rec.output),
                "parameters": json.loads(rec.parameters),
                "transaction_id": rec.transaction_id,
                "user_id": rec.user_id
            })
        return history
    except Exception as e:
        logger.error(f"Error retrieving transaction history: {e}")
        return []
    finally:
        session.close()