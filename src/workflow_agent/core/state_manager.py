"""
Centralized state management with persistence, history tracking, and state transitions.
"""
import logging
import json
import time
import asyncio
from typing import Dict, Any, Optional, List, Union, Callable, Awaitable
from datetime import datetime
from pathlib import Path
import uuid
import sqlite3
from contextlib import contextmanager

from .state import WorkflowState, WorkflowStage, WorkflowStatus, Change
from ..error.handler import ErrorHandler, handle_safely
from ..error.exceptions import StateError

logger = logging.getLogger(__name__)

class StateManager:
    """
    Centralized manager for workflow state with persistence and tracking capabilities.
    Provides methods for creating, updating, loading, and persisting workflow states.
    """
    
    def __init__(self, storage_path: Optional[str] = None, max_history: int = 100):
        """
        Initialize the state manager.
        
        Args:
            storage_path: Path to store state data (None for in-memory only)
            max_history: Maximum number of historical states to keep
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self.max_history = max_history
        self._in_memory_states: Dict[str, List[WorkflowState]] = {}
        self._active_states: Dict[str, WorkflowState] = {}
        
        # Initialize storage if path provided
        if self.storage_path:
            self._initialize_storage()
            
        logger.debug("StateManager initialized")
    
    def _initialize_storage(self) -> None:
        """Initialize the storage database."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Create states table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflow_states (
                    state_id TEXT PRIMARY KEY,
                    transaction_id TEXT NOT NULL,
                    parent_state_id TEXT,
                    action TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    integration_type TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    state_data TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 0
                );
                """)
                
                # Create index for transaction lookup
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transaction_id
                ON workflow_states (transaction_id);
                """)
                
                # Create index for active states
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_is_active
                ON workflow_states (is_active);
                """)
                
                conn.commit()
                logger.debug(f"State storage initialized at {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to initialize state storage: {e}")
            raise StateError(f"Failed to initialize state storage: {e}")
    
    @contextmanager
    def _get_db_connection(self):
        """Get a database connection with context manager."""
        if not self.storage_path:
            raise StateError("No storage path configured")
            
        conn = None
        try:
            conn = sqlite3.connect(str(self.storage_path))
            conn.row_factory = sqlite3.Row
            yield conn
        finally:
            if conn:
                conn.close()
    
    @handle_safely
    def create_state(
        self, 
        action: str,
        target_name: str,
        integration_type: str,
        parameters: Optional[Dict[str, Any]] = None,
        template_data: Optional[Dict[str, Any]] = None,
        system_context: Optional[Dict[str, Any]] = None,
        transaction_id: Optional[str] = None
    ) -> WorkflowState:
        """
        Create a new workflow state.
        
        Args:
            action: Action to perform
            target_name: Target name
            integration_type: Integration type
            parameters: Optional parameters
            template_data: Optional template data
            system_context: Optional system context
            transaction_id: Optional transaction ID (generated if not provided)
            
        Returns:
            New workflow state
        """
        # Create the state
        state = WorkflowState(
            action=action,
            target_name=target_name,
            integration_type=integration_type,
            parameters=parameters or {},
            template_data=template_data or {},
            system_context=system_context or {},
            transaction_id=transaction_id
        )
        
        # Add to active states
        self._active_states[str(state.transaction_id)] = state
        
        # Add to history
        if state.transaction_id not in self._in_memory_states:
            self._in_memory_states[state.transaction_id] = []
        self._in_memory_states[state.transaction_id].append(state)
        
        # Trim history if needed
        if len(self._in_memory_states[state.transaction_id]) > self.max_history:
            self._in_memory_states[state.transaction_id] = self._in_memory_states[state.transaction_id][-self.max_history:]
        
        # Persist state if storage configured
        if self.storage_path:
            self._persist_state(state, is_active=True)
            
        logger.debug(f"Created new state for transaction {state.transaction_id}")
        return state
    
    @handle_safely
    def update_state(self, state: WorkflowState) -> WorkflowState:
        """
        Update an existing state.
        
        Args:
            state: Updated workflow state
            
        Returns:
            The updated state
            
        Raises:
            StateError: If transaction not found
        """
        transaction_id = state.transaction_id
        
        if not transaction_id:
            raise StateError("Cannot update state without transaction_id")
            
        # Update active state
        self._active_states[transaction_id] = state
        
        # Add to history
        if transaction_id not in self._in_memory_states:
            self._in_memory_states[transaction_id] = []
        self._in_memory_states[transaction_id].append(state)
        
        # Trim history if needed
        if len(self._in_memory_states[transaction_id]) > self.max_history:
            self._in_memory_states[transaction_id] = self._in_memory_states[transaction_id][-self.max_history:]
        
        # Persist state if storage configured
        if self.storage_path:
            self._persist_state(state, is_active=True)
            
        logger.debug(f"Updated state for transaction {transaction_id}")
        return state
    
    @handle_safely
    def get_active_state(self, transaction_id: str) -> Optional[WorkflowState]:
        """
        Get the active state for a transaction.
        
        Args:
            transaction_id: Transaction ID
            
        Returns:
            Active workflow state or None if not found
        """
        # Check in-memory first
        if transaction_id in self._active_states:
            return self._active_states[transaction_id]
            
        # Try to load from storage
        if self.storage_path:
            try:
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                    SELECT state_data FROM workflow_states 
                    WHERE transaction_id = ? AND is_active = 1
                    """, (transaction_id,))
                    
                    row = cursor.fetchone()
                    if row:
                        state_data = json.loads(row['state_data'])
                        state = WorkflowState.parse_obj(state_data)
                        
                        # Cache in memory
                        self._active_states[transaction_id] = state
                        return state
            except Exception as e:
                logger.error(f"Failed to load active state for transaction {transaction_id}: {e}")
                
        return None
    
    @handle_safely
    def get_state_history(self, transaction_id: str) -> List[WorkflowState]:
        """
        Get the history of states for a transaction.
        
        Args:
            transaction_id: Transaction ID
            
        Returns:
            List of historical workflow states
        """
        # Check in-memory first
        if transaction_id in self._in_memory_states:
            return self._in_memory_states[transaction_id]
            
        # Try to load from storage
        states = []
        if self.storage_path:
            try:
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                    SELECT state_data FROM workflow_states 
                    WHERE transaction_id = ?
                    ORDER BY created_at
                    """, (transaction_id,))
                    
                    for row in cursor.fetchall():
                        state_data = json.loads(row['state_data'])
                        state = WorkflowState.parse_obj(state_data)
                        states.append(state)
                        
                # Cache in memory
                self._in_memory_states[transaction_id] = states
            except Exception as e:
                logger.error(f"Failed to load state history for transaction {transaction_id}: {e}")
                
        return states
    
    @handle_safely
    def complete_transaction(self, transaction_id: str, status: WorkflowStatus) -> Optional[WorkflowState]:
        """
        Mark a transaction as completed.
        
        Args:
            transaction_id: Transaction ID
            status: Final status
            
        Returns:
            Final workflow state or None if not found
        """
        state = self.get_active_state(transaction_id)
        if not state:
            logger.warning(f"Cannot complete transaction {transaction_id}: no active state found")
            return None
            
        # Update status
        final_state = state.evolve(status=status)
        
        # Update state
        self.update_state(final_state)
        
        # Mark as inactive in storage
        if self.storage_path:
            try:
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                    UPDATE workflow_states 
                    SET is_active = 0
                    WHERE transaction_id = ?
                    """, (transaction_id,))
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to mark transaction {transaction_id} as inactive: {e}")
                
        # Remove from active states
        if transaction_id in self._active_states:
            del self._active_states[transaction_id]
            
        logger.debug(f"Completed transaction {transaction_id} with status {status}")
        return final_state
    
    @handle_safely
    def _persist_state(self, state: WorkflowState, is_active: bool = True) -> None:
        """
        Persist a state to storage.
        
        Args:
            state: Workflow state to persist
            is_active: Whether the state is active
        """
        if not self.storage_path:
            return
            
        try:
            # Convert state to JSON
            state_data = state.model_dump()
            
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # First, check if state already exists
                cursor.execute("""
                SELECT state_id FROM workflow_states 
                WHERE state_id = ?
                """, (str(state.state_id),))
                
                if cursor.fetchone():
                    # Update existing state
                    cursor.execute("""
                    UPDATE workflow_states 
                    SET transaction_id = ?,
                        parent_state_id = ?,
                        action = ?,
                        target_name = ?,
                        integration_type = ?,
                        stage = ?,
                        status = ?,
                        state_data = ?,
                        is_active = ?
                    WHERE state_id = ?
                    """, (
                        state.transaction_id,
                        str(state.parent_state_id) if state.parent_state_id else None,
                        state.action,
                        state.target_name,
                        state.integration_type,
                        state.current_stage,
                        state.status,
                        json.dumps(state_data),
                        1 if is_active else 0,
                        str(state.state_id)
                    ))
                else:
                    # Insert new state
                    cursor.execute("""
                    INSERT INTO workflow_states (
                        state_id,
                        transaction_id,
                        parent_state_id,
                        action,
                        target_name,
                        integration_type,
                        stage,
                        status,
                        created_at,
                        state_data,
                        is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(state.state_id),
                        state.transaction_id,
                        str(state.parent_state_id) if state.parent_state_id else None,
                        state.action,
                        state.target_name,
                        state.integration_type,
                        state.current_stage,
                        state.status,
                        state.created_at.isoformat(),
                        json.dumps(state_data),
                        1 if is_active else 0
                    ))
                    
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist state {state.state_id}: {e}")
    
    @handle_safely
    def get_active_transactions(self) -> List[str]:
        """
        Get a list of active transaction IDs.
        
        Returns:
            List of active transaction IDs
        """
        # Start with in-memory active states
        transaction_ids = list(self._active_states.keys())
        
        # Add from storage if configured
        if self.storage_path:
            try:
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                    SELECT DISTINCT transaction_id FROM workflow_states 
                    WHERE is_active = 1
                    """)
                    
                    for row in cursor.fetchall():
                        transaction_id = row['transaction_id']
                        if transaction_id not in transaction_ids:
                            transaction_ids.append(transaction_id)
            except Exception as e:
                logger.error(f"Failed to get active transactions: {e}")
                
        return transaction_ids
    
    @handle_safely
    def cleanup_old_transactions(self, days_to_keep: int = 30) -> int:
        """
        Clean up old transactions from storage.
        
        Args:
            days_to_keep: Number of days to keep transactions
            
        Returns:
            Number of transactions cleaned up
        """
        if not self.storage_path:
            return 0
            
        try:
            cutoff_date = datetime.now() - datetime.timedelta(days=days_to_keep)
            cutoff_str = cutoff_date.isoformat()
            
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get transaction IDs to clean up
                cursor.execute("""
                SELECT DISTINCT transaction_id FROM workflow_states 
                WHERE created_at < ? AND is_active = 0
                """, (cutoff_str,))
                
                transaction_ids = [row['transaction_id'] for row in cursor.fetchall()]
                
                # Delete transactions
                for transaction_id in transaction_ids:
                    cursor.execute("""
                    DELETE FROM workflow_states 
                    WHERE transaction_id = ?
                    """, (transaction_id,))
                    
                    # Remove from in-memory storage
                    if transaction_id in self._in_memory_states:
                        del self._in_memory_states[transaction_id]
                        
                conn.commit()
                
                logger.info(f"Cleaned up {len(transaction_ids)} old transactions")
                return len(transaction_ids)
                
        except Exception as e:
            logger.error(f"Failed to clean up old transactions: {e}")
            return 0
    
    @handle_safely
    def apply_state_transition(
        self, 
        state: WorkflowState, 
        transition: Union[Callable[[WorkflowState], WorkflowState], str, Dict[str, Any]]
    ) -> WorkflowState:
        """
        Apply a transition to a state.
        
        Args:
            state: Current workflow state
            transition: Transition to apply:
                - Function that takes and returns a WorkflowState
                - String method name to call on the state
                - Dict of attributes to update
                
        Returns:
            Updated workflow state
            
        Raises:
            StateError: If transition is invalid
        """
        if callable(transition):
            # Function transition
            new_state = transition(state)
        elif isinstance(transition, str):
            # Method name transition
            if not hasattr(state, transition) or not callable(getattr(state, transition)):
                raise StateError(f"Invalid state transition method: {transition}")
                
            method = getattr(state, transition)
            new_state = method()
        elif isinstance(transition, dict):
            # Attribute update transition
            new_state = state.evolve(**transition)
        else:
            raise StateError(f"Invalid state transition type: {type(transition)}")
            
        # Update the state
        return self.update_state(new_state)
    
    async def wait_for_state_condition(
        self, 
        transaction_id: str, 
        condition: Callable[[WorkflowState], bool],
        timeout_seconds: float = 60.0,
        poll_interval_seconds: float = 0.5
    ) -> Optional[WorkflowState]:
        """
        Wait for a state to meet a condition.
        
        Args:
            transaction_id: Transaction ID
            condition: Function that takes a state and returns True when condition is met
            timeout_seconds: Maximum time to wait in seconds
            poll_interval_seconds: How often to check the condition
            
        Returns:
            State that meets the condition or None if timed out
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            # Get current state
            state = self.get_active_state(transaction_id)
            
            if state and condition(state):
                return state
                
            # Wait before checking again
            await asyncio.sleep(poll_interval_seconds)
            
        return None
