from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging
import re
from datetime import datetime
from sqlalchemy import func
from ..models import ExecutionRecord

logger = logging.getLogger(__name__)

class BaseAdapter(ABC):
    """Base class for database adapters."""
    
    def _validate_connection_string(self, connection_string: str) -> bool:
        """
        Validate the connection string format.
        
        Args:
            connection_string: Database connection string
            
        Returns:
            bool: True if connection string is valid, False otherwise
        """
        if not connection_string:
            return False
            
        # Check for common connection string patterns
        patterns = [
            r'^postgresql://',  # PostgreSQL
            r'^mysql://',       # MySQL
            r'^sqlite:///',     # SQLite
            r'^sqlite://',      # SQLite (alternative)
            r'^sqlite3://'      # SQLite3
        ]
        
        return any(re.match(pattern, connection_string) for pattern in patterns)
    
    def _get_connection_params(self, connection_string: str) -> Dict[str, str]:
        """
        Extract connection parameters from connection string.
        
        Args:
            connection_string: Database connection string
            
        Returns:
            Dict[str, str]: Dictionary of connection parameters
        """
        params = {}
        
        # Remove protocol prefix
        conn_str = re.sub(r'^[a-zA-Z]+://', '', connection_string)
        
        # Split into user:pass@host:port/dbname format
        if '@' in conn_str:
            user_pass, host_port_db = conn_str.split('@')
            if ':' in user_pass:
                params['user'], params['password'] = user_pass.split(':')
            else:
                params['user'] = user_pass
                params['password'] = ''
            
            if '/' in host_port_db:
                host_port, params['database'] = host_port_db.split('/')
                if ':' in host_port:
                    params['host'], params['port'] = host_port.split(':')
                else:
                    params['host'] = host_port
                    params['port'] = '5432'  # Default PostgreSQL port
        else:
            # SQLite format
            params['database'] = conn_str
            
        return params
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the database schema."""
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def get_execution_history(
        self,
        target: str = None,
        action: str = None,
        limit: int = 100,
        user_id: str = None,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> List[Dict[str, Any]]:
        """
        Get execution history with optional filters.
        
        Args:
            target: Optional target name filter
            action: Optional action name filter
            limit: Maximum number of records to return
            user_id: Optional user ID filter
            start_time: Optional start time filter
            end_time: Optional end time filter
            
        Returns:
            List of execution records
        """
        pass
    
    @abstractmethod
    async def get_execution_statistics(
        self,
        target: str,
        action: str,
        user_id: str = None
    ) -> Dict[str, Any]:
        """
        Get execution statistics for a specific target and action.
        
        Args:
            target: Target name
            action: Action name
            user_id: Optional user ID
            
        Returns:
            Dictionary containing execution statistics
        """
        pass
    
    @abstractmethod
    async def clear_history(
        self,
        target: str = None,
        action: str = None,
        user_id: str = None,
        before_time: datetime = None
    ) -> int:
        """
        Clear execution history with optional filters.
        
        Args:
            target: Optional target name filter
            action: Optional action name filter
            user_id: Optional user ID filter
            before_time: Optional time filter (clear records before this time)
            
        Returns:
            Number of records cleared
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close database connections."""
        pass 