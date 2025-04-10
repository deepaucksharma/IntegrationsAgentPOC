"""
Script execution with change tracking and security validation.
"""
import logging
import os
import tempfile
import asyncio
import time
import re
import json
import shutil
import platform
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime

from ..error.exceptions import ExecutionError, SecurityError
from ..core.state import WorkflowState, Change, OutputData, WorkflowStatus
from ..config.configuration import WorkflowConfiguration, validate_script_security
from ..utils.subprocess_utils import async_secure_shell_execute
from ..error.handler import ErrorHandler, handle_safely_async
from .isolation import IsolationFactory, IsolationStrategy

logger = logging.getLogger(__name__)

class ScriptExecutor:
    """Handles script execution with security and change tracking."""
    
    def __init__(self, config: WorkflowConfiguration):
        """
        Initialize the script executor with configuration.
        
        Args:
            config: Workflow configuration
        """
        self.config = config
        self._context = {}  # Execution context for integration execution
        
    @handle_safely_async
    async def execute(self, state: WorkflowState) -> WorkflowState:
        """
        Execute a script contained in the workflow state.
        
        Args:
            state: Workflow state with script to execute
            
        Returns:
            Updated workflow state with execution results
            
        Raises:
            ExecutionError: If script execution fails
            SecurityError: If script fails security validation
        """
        if not state.script:
            logger.error("No script provided for execution")
            return state.set_error("No script provided for execution")
            
        # Validate script with enhanced security checks
        validation_state = await self._validate_script_security(state)
        if validation_state.has_error:
            return validation_state
        
        # Create isolation strategy
        isolation_method = state.isolation_method or self.config.isolation_method
        isolation = IsolationFactory.create(isolation_method, self.config)
        
        logger.info(f"Executing script with {isolation.get_name()} isolation")
        
        # Mark state as running
        execution_state = validation_state.mark_running()
        
        try:
            # Execute the script
            start_time = datetime.now()
            output = await isolation.execute(
                execution_state.script,
                execution_state.parameters,
                None  # Use default working directory
            )
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Update state with execution results
            result_state = execution_state.set_output(output)
            
            # Check exit code
            if output.exit_code != 0:
                error_msg = f"Script execution failed with exit code {output.exit_code}"
                logger.error(error_msg)
                if output.stderr:
                    logger.error(f"Error output: {output.stderr[:500]}")
                return result_state.set_error(error_msg)
                
            # Extract and track changes
            changes = self._extract_changes(output.stdout)
            change_state = result_state
            for change in changes:
                change_state = change_state.add_change(change)
                
            # Update metrics
            metrics_state = change_state.evolve(
                metrics=change_state.metrics.model_copy(update={
                    "end_time": datetime.now(),
                    "duration": execution_time
                })
            )
            
            # Mark as completed
            completed_state = metrics_state.mark_completed()
            logger.info(f"Script execution completed successfully with {len(changes)} changes tracked")
            
            return completed_state
            
        except asyncio.TimeoutError:
            error_msg = "Script execution timed out"
            logger.error(error_msg)
            return execution_state.set_error(error_msg)
        except Exception as e:
            error_msg = f"Error during script execution: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return execution_state.set_error(error_msg)
    
    async def _validate_script_security(self, state: WorkflowState) -> WorkflowState:
        """
        Validate script security with enhanced checks.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with warnings or errors
        """
        # Start with current state
        current_state = state
        
        # Validate script with enhanced security checks
        security_result = validate_script_security(state.script)
        
        # Handle warnings
        warning_state = current_state
        for warning in security_result.get("warnings", []):
            logger.warning(f"Script security warning: {warning}")
            warning_state = warning_state.add_warning(warning)
            
        # Handle errors (more serious than warnings)
        if security_result.get("errors", []):
            error_msgs = "\n".join(security_result["errors"])
            error_msg = f"Script failed security validation with critical issues:\n{error_msgs}"
            logger.error(error_msg)
            
            # If least privilege execution is enabled, fail on any security error
            if self.config.least_privilege_execution:
                return warning_state.set_error(error_msg)
            
            # Otherwise, add a warning and continue but only for non-critical issues
            critical_patterns = ["rm -rf /", "format", "shutdown", "reboot"]
            critical_issue = any(pattern in error_msg.lower() for pattern in critical_patterns)
            
            if critical_issue:
                return warning_state.set_error(
                    f"Script contains critical security violations that cannot be bypassed: {error_msg}"
                )
                
            logger.warning("SECURITY RISK: Executing script despite security issues due to disabled least privilege execution")
            return warning_state.add_warning("SECURITY RISK: Script contains potentially dangerous operations")
        
        # Use enhanced validation from the script validator
        from ..scripting.validator import ScriptValidator
        script_validator = ScriptValidator(self.config)
        validation_result = script_validator.validate(state.script)
        
        # Add validation warnings to state
        validation_state = warning_state
        for warning in validation_result.get("warnings", []):
            validation_state = validation_state.add_warning(warning)
            
        # If validation fails with errors, abort
        if validation_result.get("errors", []) and not validation_result.get("valid", False):
            error_msgs = "\n".join(validation_result["errors"])
            return validation_state.set_error(f"Script validation failed:\n{error_msgs}")
        
        # If we reach here, script is valid (or warnings were bypassed)
        return validation_state
            
    def _extract_changes(self, output: str) -> List[Change]:
        """
        Extract changes from script output using the consolidated ChangeTracker.
        
        Args:
            output: Script output to parse
            
        Returns:
            List of Change objects
        """
        # Import and use the consolidated ChangeTracker
        from .change_tracker import ChangeTracker
        tracker = ChangeTracker()
        return tracker.extract_changes(output)
            
    # Integration Execution Methods
    
    async def execute_integration(self, integration: Any, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an integration action.
        
        Args:
            integration: Integration instance
            action: Action to perform (e.g., 'install', 'verify', 'uninstall')
            params: Parameters for the action
            
        Returns:
            Dictionary with execution results
            
        Raises:
            IntegrationExecutionError: If execution fails
        """
        try:
            if not hasattr(integration, action):
                from ..error.exceptions import IntegrationExecutionError
                raise IntegrationExecutionError(f"Action {action} not supported by integration")
                
            method = getattr(integration, action)
            result = await method(params)
            
            if not isinstance(result, dict):
                from ..error.exceptions import IntegrationExecutionError
                raise IntegrationExecutionError("Integration action must return a dictionary")
                
            return result
            
        except Exception as e:
            from ..error.exceptions import IntegrationExecutionError
            raise IntegrationExecutionError(f"Execution failed: {str(e)}")
            
    def set_context(self, key: str, value: Any) -> None:
        """Set execution context value."""
        self._context[key] = value
        
    def get_context(self, key: str, default: Any = None) -> Any:
        """Get execution context value."""
        return self._context.get(key, default)
