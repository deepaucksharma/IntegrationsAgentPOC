# src/workflow_agent/storage/history.py
import os
import logging
from typing import Dict, Any, List, Optional, Union
from .models import ExecutionRecord
from .adapters import get_adapter, SQLiteAdapter, PostgreSQLAdapter, MySQLAdapter

logger = logging.getLogger(__name__)

class HistoryManager:
    """Manages execution history records across different database backends."""
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize the history manager.
        
        Args:
            connection_string: Optional database connection string
        """
        self.adapter = get_adapter(connection_string)
        
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the history storage.
        
        Args:
            config: Optional configuration dictionary
        """
        if config and "configurable" in config and "db_connection_string" in config["configurable"]:
            self.adapter = get_adapter(config["configurable"]["db_connection_string"])
        await self.adapter.initialize()
        
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
        Save an execution record.
        
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
        return await self.adapter.save_execution(
            target_name=target_name,
            action=action,
            success=success,
            execution_time=execution_time,
            error_message=error_message,
            system_context=system_context,
            script=script,
            output=output,
            parameters=parameters,
            transaction_id=transaction_id,
            user_id=user_id
        )
    
    async def get_execution_history(
        self,
        target: str,
        action: str,
        limit: int = 10,
        user_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get execution history for a specific target and action.
        
        Args:
            target: Target name to filter by
            action: Action to filter by
            limit: Maximum number of records to return
            user_id: Optional user ID to filter by
            
        Returns:
            List of execution records
        """
        return await self.adapter.get_execution_history(
            target=target,
            action=action,
            limit=limit,
            user_id=user_id
        )
    
    async def get_execution_statistics(
        self,
        target: str,
        action: str,
        user_id: str = None
    ) -> Dict[str, Any]:
        """
        Get statistics for a specific target and action.
        
        Args:
            target: Target name to filter by
            action: Action to filter by
            user_id: Optional user ID to filter by
            
        Returns:
            Dictionary with execution statistics
        """
        return await self.adapter.get_execution_statistics(
            target=target,
            action=action,
            user_id=user_id
        )
    
    async def clear_history(
        self,
        target: str = None,
        action: str = None,
        days: int = None,
        user_id: str = None
    ) -> int:
        """
        Clear execution history.
        
        Args:
            target: Optional target name to filter by
            action: Optional action to filter by
            days: Optional number of days to keep (older records will be deleted)
            user_id: Optional user ID to filter by
            
        Returns:
            Number of records deleted
        """
        return await self.adapter.clear_history(
            target=target,
            action=action,
            days=days,
            user_id=user_id
        )
    
    async def get_transaction_history(self, transaction_id: str) -> List[Dict[str, Any]]:
        """
        Get all records for a specific transaction.
        
        Args:
            transaction_id: Transaction ID to filter by
            
        Returns:
            List of execution records
        """
        return await self.adapter.get_transaction_history(transaction_id)
    
    async def auto_prune_history(self, days: int = 90) -> None:
        """
        Automatically prune old history records.
        
        Args:
            days: Number of days to keep (older records will be deleted)
        """
        if days > 0:
            count = await self.adapter.clear_history(days=days)
            logger.info(f"Auto-pruned {count} execution records older than {days} days.")
    
    async def close(self):
        """Close database connections."""
        await self.adapter.close()
    
    # Synchronous versions for backward compatibility
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
        return self.adapter.save_execution_sync(
            target_name=target_name,
            action=action,
            success=success,
            execution_time=execution_time,
            error_message=error_message,
            system_context=system_context,
            script=script,
            output=output,
            parameters=parameters,
            transaction_id=transaction_id,
            user_id=user_id
        )
    
    def get_execution_history_sync(
        self,
        target: str,
        action: str,
        limit: int = 10,
        user_id: str = None
    ) -> List[Dict[str, Any]]:
        """Synchronous version of get_execution_history."""
        return self.adapter.get_execution_history_sync(
            target=target,
            action=action,
            limit=limit,
            user_id=user_id
        )
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.close()