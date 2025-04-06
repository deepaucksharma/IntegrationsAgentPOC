"""
Script execution with change tracking and security validation.
"""
import logging
import os
import tempfile
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from ..error.exceptions import ExecutionError, SecurityError
from ..core.state import WorkflowState, Change, OutputData, WorkflowStatus
from ..config.configuration import WorkflowConfiguration, validate_script_security
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
            
        # Validate script security
        security_result = validate_script_security(state.script)
        if not security_result["valid"]:
            warnings = "\n".join(security_result["warnings"])
            error_msg = f"Script failed security validation:\n{warnings}"
            logger.error(error_msg)
            
            # If least privilege execution is disabled, we can allow the execution
            # with warnings
            if not self.config.least_privilege_execution:
                logger.warning("Executing script despite security warnings due to disabled least privilege execution")
                state = state.add_warning(error_msg)
            else:
                raise SecurityError(error_msg)
                
        # Create isolation strategy
        isolation_method = state.isolation_method or self.config.isolation_method
        isolation = IsolationFactory.create(isolation_method, self.config)
        
        logger.info(f"Executing script with {isolation.get_name()} isolation")
        
        # Mark state as running
        state = state.mark_running()
        
        try:
            # Execute the script
            output = await isolation.execute(
                state.script,
                state.parameters,
                None  # Use default working directory
            )
            
            # Update state with execution results
            state = state.set_output(output)
            
            # Check exit code
            if output.exit_code != 0:
                logger.error(f"Script execution failed with exit code {output.exit_code}")
                return state.set_error(f"Script execution failed with exit code {output.exit_code}")
                
            # Extract and track changes
            changes = self._extract_changes(output.stdout)
            for change in changes:
                state = state.add_change(change)
                
            # Update metrics
            state = state.evolve(
                metrics=state.metrics.model_copy(update={
                    "end_time": time.time(),
                    "duration": output.duration
                })
            )
            
            # Mark as completed
            return state.mark_completed()
            
        except asyncio.TimeoutError:
            logger.error("Script execution timed out")
            return state.set_error("Script execution timed out")
        except Exception as e:
            logger.error(f"Error during script execution: {e}", exc_info=True)
            return state.set_error(f"Error during script execution: {str(e)}")
            
    def _extract_changes(self, output: str) -> List[Change]:
        """
        Extract changes from script output.
        
        Args:
            output: Script output to parse
            
        Returns:
            List of Change objects
        """
        changes = []
        
        # Look for standardized change indicators
        import re
        
        # Package installations
        for match in re.finditer(r"CHANGE:PACKAGE_INSTALLED:(\S+)", output):
            package_name = match.group(1)
            changes.append(Change(
                type="package_installed",
                target=package_name,
                revertible=True
            ))
            
        # File creations
        for match in re.finditer(r"CHANGE:FILE_CREATED:(\S+)", output):
            file_path = match.group(1)
            changes.append(Change(
                type="file_created",
                target=file_path,
                revertible=True
            ))
            
        # Directory creations
        for match in re.finditer(r"CHANGE:DIRECTORY_CREATED:(\S+)", output):
            dir_path = match.group(1)
            changes.append(Change(
                type="directory_created",
                target=dir_path,
                revertible=True
            ))
            
        # Service operations
        for match in re.finditer(r"CHANGE:SERVICE_(\w+):(\S+)", output):
            operation = match.group(1).lower()
            service_name = match.group(2)
            changes.append(Change(
                type=f"service_{operation}",
                target=service_name,
                revertible=operation in ["started", "enabled"]
            ))
            
        return changes
