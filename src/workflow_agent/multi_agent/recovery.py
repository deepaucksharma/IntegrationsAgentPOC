"""
Enhanced recovery system for handling workflow errors with tiered recovery strategies.
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable
import traceback
import time

from ..core.state import WorkflowState
from ..error.exceptions import WorkflowError, RecoveryError

logger = logging.getLogger(__name__)

class RecoveryStrategy:
    """Defines recovery strategies for workflow errors."""
    ROLLBACK = "rollback"  # Roll back all changes
    RETRY = "retry"        # Retry the failed operation
    CONTINUE = "continue"  # Continue to the next step despite error
    ABORT = "abort"        # Abort the workflow without recovery

class WorkflowRecovery:
    """
    Enhanced workflow recovery system with tiered recovery strategies.
    """
    
    def __init__(self, coordinator=None):
        """
        Initialize the recovery system.
        
        Args:
            coordinator: Reference to the coordinator agent
        """
        self.coordinator = coordinator
        self.recovery_handlers = {}
        self.default_strategy = RecoveryStrategy.ROLLBACK
        self.max_retries = 3
        self._retry_counts = {}
        
    def register_error_handler(self, error_type: str, handler: Callable) -> None:
        """
        Register a handler for a specific error type.
        
        Args:
            error_type: Type of error to handle
            handler: Handler function (async)
        """
        self.recovery_handlers[error_type] = handler
        logger.debug(f"Registered handler for error type: {error_type}")
        
    async def handle_error(self, 
                          workflow_id: str, 
                          error: Any, 
                          state: Dict[str, Any],
                          strategy: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle a workflow error with the appropriate recovery strategy.
        
        Args:
            workflow_id: Workflow identifier
            error: Error that occurred
            state: Current workflow state
            strategy: Recovery strategy to use (defaults to automatic selection)
            
        Returns:
            Recovery result with updated state
        """
        error_str = str(error)
        error_type = self._determine_error_type(error)
        
        logger.error(f"Handling error in workflow {workflow_id}: {error_str}")
        
        # Determine recovery strategy if not specified
        if not strategy:
            strategy = self._select_recovery_strategy(error_type, error_str, state)
            
        logger.info(f"Selected recovery strategy for workflow {workflow_id}: {strategy}")
        
        # Execute recovery strategy
        try:
            if strategy == RecoveryStrategy.ROLLBACK:
                return await self._execute_rollback(workflow_id, error, state)
            elif strategy == RecoveryStrategy.RETRY:
                return await self._execute_retry(workflow_id, error, state)
            elif strategy == RecoveryStrategy.CONTINUE:
                return await self._execute_continue(workflow_id, error, state)
            elif strategy == RecoveryStrategy.ABORT:
                return await self._execute_abort(workflow_id, error, state)
            else:
                logger.warning(f"Unknown recovery strategy: {strategy}, falling back to {self.default_strategy}")
                return await self.handle_error(workflow_id, error, state, self.default_strategy)
        except Exception as recovery_error:
            logger.error(f"Error during recovery for workflow {workflow_id}: {recovery_error}")
            return {
                "success": False,
                "recovered": False,
                "strategy": strategy,
                "error": f"Recovery failed: {str(recovery_error)}",
                "original_error": error_str,
                "state": state
            }
    
    def _determine_error_type(self, error: Any) -> str:
        """
        Determine the type of error for recovery selection.
        
        Args:
            error: Error that occurred
            
        Returns:
            Error type string
        """
        if isinstance(error, str):
            # Error is already a string
            if "permission" in error.lower():
                return "permission_error"
            elif "network" in error.lower() or "connection" in error.lower():
                return "network_error"
            elif "timeout" in error.lower():
                return "timeout_error"
            elif "not found" in error.lower():
                return "not_found_error"
            else:
                return "generic_error"
        elif isinstance(error, Exception):
            # Get error class name
            return error.__class__.__name__
        else:
            # Unknown error type
            return "unknown_error"
    
    def _select_recovery_strategy(self, error_type: str, error_str: str, state: Dict[str, Any]) -> str:
        """
        Select the appropriate recovery strategy based on error type and state.
        
        Args:
            error_type: Type of error
            error_str: Error message
            state: Current workflow state
            
        Returns:
            Selected recovery strategy
        """
        # Check for specialized handlers
        if error_type in self.recovery_handlers:
            return RecoveryStrategy.ROLLBACK  # Default to rollback for custom handlers
            
        # Check for retryable errors
        retryable_errors = [
            "network_error", 
            "timeout_error", 
            "ConnectionError", 
            "TimeoutError"
        ]
        
        workflow_id = state.get("workflow_id", "unknown")
        if error_type in retryable_errors:
            # Check retry count
            retry_key = f"{workflow_id}:{error_type}"
            current_retries = self._retry_counts.get(retry_key, 0)
            
            if current_retries < self.max_retries:
                # Increment retry count
                self._retry_counts[retry_key] = current_retries + 1
                return RecoveryStrategy.RETRY
                
        # Check for permission errors (cannot be recovered with retry)
        if error_type == "permission_error" or "permission denied" in error_str.lower():
            return RecoveryStrategy.ROLLBACK
            
        # Check if changes were made that need rollback
        if "changes" in state and state["changes"]:
            return RecoveryStrategy.ROLLBACK
            
        # Default strategy
        return self.default_strategy
    
    async def _execute_rollback(self, workflow_id: str, error: Any, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute rollback recovery strategy.
        
        Args:
            workflow_id: Workflow identifier
            error: Error that occurred
            state: Current workflow state
            
        Returns:
            Rollback result
        """
        logger.info(f"Executing rollback for workflow {workflow_id}")
        
        # Create workflow state if needed
        workflow_state = state
        if not isinstance(state, WorkflowState):
            try:
                workflow_state = WorkflowState(**state)
            except Exception as e:
                logger.warning(f"Could not create WorkflowState: {e}, using dict state")
        
        # Check if there are changes to roll back
        changes = state.get("changes", [])
        if not changes:
            logger.info(f"No changes to roll back for workflow {workflow_id}")
            return {
                "success": True,
                "recovered": True,
                "strategy": RecoveryStrategy.ROLLBACK,
                "message": "No changes to roll back",
                "state": state
            }
            
        # Execute rollback logic
        try:
            # Delegate to coordinator for actual rollback
            if self.coordinator:
                rollback_result = await self.coordinator.rollback_changes(workflow_id, workflow_state)
                
                # Update state with rollback result
                if isinstance(rollback_result, dict) and "state" in rollback_result:
                    updated_state = rollback_result["state"]
                else:
                    # Just clear changes if no state update
                    updated_state = state.copy()
                    updated_state["changes"] = []
                    
                return {
                    "success": True,
                    "recovered": True,
                    "strategy": RecoveryStrategy.ROLLBACK,
                    "message": "Successfully rolled back changes",
                    "state": updated_state
                }
            else:
                logger.error(f"No coordinator available for rollback in workflow {workflow_id}")
                return {
                    "success": False,
                    "recovered": False,
                    "strategy": RecoveryStrategy.ROLLBACK,
                    "error": "No coordinator available for rollback",
                    "state": state
                }
        except Exception as e:
            logger.error(f"Error during rollback for workflow {workflow_id}: {e}")
            return {
                "success": False,
                "recovered": False,
                "strategy": RecoveryStrategy.ROLLBACK,
                "error": f"Rollback failed: {str(e)}",
                "state": state
            }
    
    async def _execute_retry(self, workflow_id: str, error: Any, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute retry recovery strategy.
        
        Args:
            workflow_id: Workflow identifier
            error: Error that occurred
            state: Current workflow state
            
        Returns:
            Retry result
        """
        logger.info(f"Executing retry for workflow {workflow_id}")
        
        # Get current step
        current_step = state.get("current_step")
        if not current_step:
            logger.warning(f"No current step to retry for workflow {workflow_id}")
            return {
                "success": False,
                "recovered": False,
                "strategy": RecoveryStrategy.RETRY,
                "error": "No current step to retry",
                "state": state
            }
            
        # Execute retry logic
        try:
            # Delegate to coordinator for retry
            if self.coordinator:
                # Prepare state for retry
                retry_state = state.copy()
                retry_state["retry_count"] = retry_state.get("retry_count", 0) + 1
                retry_state["last_error"] = str(error)
                
                # Execute retry
                retry_result = await self.coordinator.retry_step(workflow_id, current_step, retry_state)
                
                if isinstance(retry_result, dict) and "state" in retry_result:
                    return {
                        "success": True,
                        "recovered": True,
                        "strategy": RecoveryStrategy.RETRY,
                        "message": f"Successfully retried step: {current_step}",
                        "state": retry_result["state"]
                    }
                else:
                    logger.warning(f"Retry did not return state for workflow {workflow_id}")
                    return {
                        "success": False,
                        "recovered": False,
                        "strategy": RecoveryStrategy.RETRY,
                        "error": "Retry did not return valid state",
                        "state": state
                    }
            else:
                logger.error(f"No coordinator available for retry in workflow {workflow_id}")
                return {
                    "success": False,
                    "recovered": False,
                    "strategy": RecoveryStrategy.RETRY,
                    "error": "No coordinator available for retry",
                    "state": state
                }
        except Exception as e:
            logger.error(f"Error during retry for workflow {workflow_id}: {e}")
            return {
                "success": False,
                "recovered": False,
                "strategy": RecoveryStrategy.RETRY,
                "error": f"Retry failed: {str(e)}",
                "state": state
            }
    
    async def _execute_continue(self, workflow_id: str, error: Any, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute continue recovery strategy.
        
        Args:
            workflow_id: Workflow identifier
            error: Error that occurred
            state: Current workflow state
            
        Returns:
            Continue result
        """
        logger.info(f"Executing continue for workflow {workflow_id}")
        
        # Prepare state for continuation
        continue_state = state.copy()
        continue_state["handled_errors"] = continue_state.get("handled_errors", []) + [str(error)]
        
        # Execute continue logic
        try:
            # Delegate to coordinator for continuation
            if self.coordinator:
                continue_result = await self.coordinator.continue_workflow(workflow_id, continue_state)
                
                if isinstance(continue_result, dict) and "state" in continue_result:
                    return {
                        "success": True,
                        "recovered": True,
                        "strategy": RecoveryStrategy.CONTINUE,
                        "message": "Successfully continued workflow despite error",
                        "state": continue_result["state"]
                    }
                else:
                    logger.warning(f"Continue did not return state for workflow {workflow_id}")
                    return {
                        "success": False,
                        "recovered": False,
                        "strategy": RecoveryStrategy.CONTINUE,
                        "error": "Continue did not return valid state",
                        "state": continue_state
                    }
            else:
                # If no coordinator, just return the updated state
                return {
                    "success": True,
                    "recovered": True,
                    "strategy": RecoveryStrategy.CONTINUE,
                    "message": "Continuing workflow (no coordinator)",
                    "state": continue_state
                }
        except Exception as e:
            logger.error(f"Error during continue for workflow {workflow_id}: {e}")
            return {
                "success": False,
                "recovered": False,
                "strategy": RecoveryStrategy.CONTINUE,
                "error": f"Continue failed: {str(e)}",
                "state": state
            }
    
    async def _execute_abort(self, workflow_id: str, error: Any, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute abort recovery strategy.
        
        Args:
            workflow_id: Workflow identifier
            error: Error that occurred
            state: Current workflow state
            
        Returns:
            Abort result
        """
        logger.info(f"Executing abort for workflow {workflow_id}")
        
        # Prepare state for abortion
        abort_state = state.copy()
        abort_state["aborted"] = True
        abort_state["abort_reason"] = str(error)
        abort_state["status"] = "aborted"
        
        # Execute abort logic
        try:
            # Delegate to coordinator for abort
            if self.coordinator:
                await self.coordinator.abort_workflow(workflow_id, abort_state)
                
            return {
                "success": True,
                "recovered": False,  # Abort is not a recovery
                "strategy": RecoveryStrategy.ABORT,
                "message": "Workflow aborted",
                "state": abort_state
            }
        except Exception as e:
            logger.error(f"Error during abort for workflow {workflow_id}: {e}")
            return {
                "success": False,
                "recovered": False,
                "strategy": RecoveryStrategy.ABORT,
                "error": f"Abort failed: {str(e)}",
                "state": state
            }
    
    def reset_retry_count(self, workflow_id: str, error_type: Optional[str] = None) -> None:
        """
        Reset retry count for a workflow.
        
        Args:
            workflow_id: Workflow identifier
            error_type: Specific error type to reset (None for all)
        """
        if error_type:
            # Reset specific error type
            retry_key = f"{workflow_id}:{error_type}"
            if retry_key in self._retry_counts:
                del self._retry_counts[retry_key]
        else:
            # Reset all error types for this workflow
            keys_to_remove = [key for key in self._retry_counts if key.startswith(f"{workflow_id}:")]
            for key in keys_to_remove:
                del self._retry_counts[key]
