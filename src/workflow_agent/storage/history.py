"""History storage for workflow agent."""
import logging
import json
import asyncio
import sqlite3
import time
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class HistoryManager:
    """Manages execution history for the workflow agent."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or "workflow_history.db"
        self.connection = None
        self._lock = asyncio.Lock()
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        if config and "configurable" in config:
            configurable = config["configurable"]
            if "db_connection_string" in configurable:
                self.db_path = configurable["db_connection_string"]
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        async with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS execution_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    execution_time INTEGER NOT NULL,
                    error_message TEXT,
                    script TEXT NOT NULL,
                    output TEXT,
                    parameters TEXT,
                    transaction_id TEXT,
                    user_id TEXT,
                    timestamp INTEGER NOT NULL
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_execution_history_target_action
                ON execution_history (target_name, action)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_execution_history_transaction_id
                ON execution_history (transaction_id)
            ''')
    
    async def close(self) -> None:
        async with self._lock:
            if self.connection:
                self.connection.close()
                self.connection = None
    
    async def cleanup(self) -> None:
        await self.close()
    
    @asynccontextmanager
    async def _get_connection(self):
        async with self._lock:
            if not self.connection:
                self.connection = sqlite3.connect(self.db_path)
                self.connection.row_factory = sqlite3.Row
            try:
                yield self.connection
            finally:
                pass
    
    async def save_execution(
        self,
        target_name: str,
        action: str,
        success: bool,
        execution_time: int,
        script: str,
        error_message: Optional[str] = None,
        output: Optional[Union[str, Dict[str, Any]]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        transaction_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> int:
        if isinstance(output, dict):
            output = json.dumps(output)
        parameters_json = json.dumps(parameters) if parameters else None
        try:
            async with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO execution_history
                    (target_name, action, success, execution_time, error_message, script, output,
                     parameters, transaction_id, user_id, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    target_name,
                    action,
                    success,
                    execution_time,
                    error_message,
                    script,
                    output,
                    parameters_json,
                    transaction_id,
                    user_id,
                    int(time.time())
                ))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to save execution record: {e}")
            raise
    
    async def auto_prune_history(self, days: int) -> int:
        if days <= 0:
            return 0
        cutoff = int(time.time() - days * 86400)
        try:
            async with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM execution_history WHERE timestamp < ?", (cutoff,))
                count = cursor.fetchone()[0]
                if count == 0:
                    return 0
                cursor.execute("DELETE FROM execution_history WHERE timestamp < ?", (cutoff,))
                conn.commit()
                return count
        except Exception as e:
            logger.error(f"Failed to prune history: {e}")
            return 0