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
        Extract changes from script output using structured change tracking.
        
        Args:
            output: Script output to parse
            
        Returns:
            List of Change objects
        """
        changes = []
        
        # Look for standardized JSON change indicators
        import re
        import json
        
        # First try to parse JSON change blocks if available
        json_change_blocks = re.findall(r"CHANGE_JSON_BEGIN\s*(.*?)\s*CHANGE_JSON_END", output, re.DOTALL)
        
        for json_block in json_change_blocks:
            try:
                change_data = json.loads(json_block)
                
                # Handle both single change and array of changes
                if isinstance(change_data, list):
                    for item in change_data:
                        self._process_change_item(item, changes)
                else:
                    self._process_change_item(change_data, changes)
                    
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON change block: {json_block[:100]}")
        
        # Fall back to older format if no JSON blocks found
        if not changes:
            # Package installations
            for match in re.finditer(r"CHANGE:PACKAGE_INSTALLED:(\S+)(?::(\S+))?", output):
                package_name = match.group(1)
                version = match.group(2) if len(match.groups()) > 1 else None
                revert_cmd = f"package remove {package_name}" if version else None
                
                changes.append(Change(
                    type="package_installed",
                    target=package_name,
                    revertible=True,
                    revert_command=revert_cmd
                ))
                
            # File creations
            for match in re.finditer(r"CHANGE:FILE_CREATED:(\S+)", output):
                file_path = match.group(1)
                revert_cmd = f"rm -f {file_path}" if '/' in file_path else f"del {file_path}"
                
                changes.append(Change(
                    type="file_created",
                    target=file_path,
                    revertible=True,
                    revert_command=revert_cmd
                ))
                
            # File modifications
            for match in re.finditer(r"CHANGE:FILE_MODIFIED:(\S+)(?::(.+))?", output):
                file_path = match.group(1)
                backup_path = match.group(2) if len(match.groups()) > 1 else None
                
                revert_cmd = None
                if backup_path:
                    if '/' in file_path:
                        revert_cmd = f"cp {backup_path} {file_path}"
                    else:
                        revert_cmd = f"copy {backup_path} {file_path}"
                
                changes.append(Change(
                    type="file_modified",
                    target=file_path,
                    revertible=backup_path is not None,
                    revert_command=revert_cmd
                ))
                
            # Directory creations
            for match in re.finditer(r"CHANGE:DIRECTORY_CREATED:(\S+)", output):
                dir_path = match.group(1)
                revert_cmd = f"rmdir /S /Q {dir_path}" if '\\' in dir_path else f"rm -rf {dir_path}"
                
                changes.append(Change(
                    type="directory_created",
                    target=dir_path,
                    revertible=True,
                    revert_command=revert_cmd
                ))
                
            # Service operations
            for match in re.finditer(r"CHANGE:SERVICE_(\w+):(\S+)", output):
                operation = match.group(1).lower()
                service_name = match.group(2)
                
                revert_cmd = None
                if operation == "started":
                    revert_cmd = f"service {service_name} stop"
                elif operation == "enabled":
                    revert_cmd = f"service {service_name} disable"
                elif operation == "installed":
                    revert_cmd = f"service {service_name} uninstall"
                
                changes.append(Change(
                    type=f"service_{operation}",
                    target=service_name,
                    revertible=operation in ["started", "enabled", "installed"],
                    revert_command=revert_cmd
                ))
                
            # Configuration changes
            for match in re.finditer(r"CHANGE:CONFIG_MODIFIED:(\S+)(?::(.+))?", output):
                config_path = match.group(1)
                backup_path = match.group(2) if len(match.groups()) > 1 else None
                
                revert_cmd = None
                if backup_path:
                    if '/' in config_path:
                        revert_cmd = f"cp {backup_path} {config_path}"
                    else:
                        revert_cmd = f"copy {backup_path} {config_path}"
                
                changes.append(Change(
                    type="config_modified",
                    target=config_path,
                    revertible=backup_path is not None,
                    revert_command=revert_cmd
                ))
                
            # Generic changes (catch-all)
            for match in re.finditer(r"CHANGE:(\w+):(\S+)(?::(.+))?", output):
                change_type = match.group(1).lower()
                target = match.group(2)
                revert_info = match.group(3) if len(match.groups()) > 2 else None
                
                # Skip already processed change types
                if change_type in ["package_installed", "file_created", "file_modified", 
                                "directory_created", "service_started", "service_enabled",
                                "service_installed", "config_modified"]:
                    continue
                
                changes.append(Change(
                    type=change_type,
                    target=target,
                    revertible=revert_info is not None,
                    revert_command=revert_info
                ))
        
        return changes
    
    def _process_change_item(self, item: Dict[str, Any], changes_list: List[Change]) -> None:
        """
        Process a single change item and add it to the changes list.
        
        Args:
            item: Change item data
            changes_list: List to add the change to
        """
        if not isinstance(item, dict) or "type" not in item or "target" not in item:
            logger.warning(f"Invalid change item format: {item}")
            return
            
        try:
            # Convert dictionary to Change object
            change = Change(
                type=item["type"],
                target=item["target"],
                revertible=item.get("revertible", False),
                revert_command=item.get("revert_command")
            )
            changes_list.append(change)
        except Exception as e:
            logger.error(f"Error processing change item: {e}")
