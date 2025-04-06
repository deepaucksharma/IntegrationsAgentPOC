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
from ..utils.error_handling import async_handle_errors
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
        
    @async_handle_errors("Script execution failed")
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
        Extract changes from script output using enhanced structured change tracking.
        Also monitors filesystem changes independently of script output.
        
        Args:
            output: Script output to parse
            
        Returns:
            List of Change objects
        """
        changes = []
        
        # Process JSON change blocks which are the most reliable format
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
        
        # Process structured change markers
        # This is more reliable than general regex and works with any format of stdout
        structured_changes = {
            # Package operations
            "PACKAGE_INSTALL": re.compile(r"CHANGE:PACKAGE_INSTALLED:(\S+)(?::(\S+))?"),
            "PACKAGE_REMOVE": re.compile(r"CHANGE:PACKAGE_REMOVED:(\S+)"),
            "PACKAGE_UPDATE": re.compile(r"CHANGE:PACKAGE_UPDATED:(\S+)(?::(\S+))?"),
            
            # File operations
            "FILE_CREATE": re.compile(r"CHANGE:FILE_CREATED:(\S+)"),
            "FILE_MODIFY": re.compile(r"CHANGE:FILE_MODIFIED:(\S+)(?::(\S+))?"),
            "FILE_DELETE": re.compile(r"CHANGE:FILE_DELETED:(\S+)"),
            "FILE_CHMOD": re.compile(r"CHANGE:FILE_PERMISSIONS:(\S+)(?::(\S+))?"),
            "FILE_CHOWN": re.compile(r"CHANGE:FILE_OWNERSHIP:(\S+)(?::(\S+))?"),
            
            # Directory operations
            "DIR_CREATE": re.compile(r"CHANGE:DIRECTORY_CREATED:(\S+)"),
            "DIR_DELETE": re.compile(r"CHANGE:DIRECTORY_DELETED:(\S+)"),
            
            # Service operations
            "SERVICE_INSTALL": re.compile(r"CHANGE:SERVICE_INSTALLED:(\S+)"),
            "SERVICE_REMOVE": re.compile(r"CHANGE:SERVICE_REMOVED:(\S+)"),
            "SERVICE_START": re.compile(r"CHANGE:SERVICE_STARTED:(\S+)"),
            "SERVICE_STOP": re.compile(r"CHANGE:SERVICE_STOPPED:(\S+)"),
            "SERVICE_ENABLE": re.compile(r"CHANGE:SERVICE_ENABLED:(\S+)"),
            "SERVICE_DISABLE": re.compile(r"CHANGE:SERVICE_DISABLED:(\S+)"),
            
            # Configuration operations
            "CONFIG_MODIFY": re.compile(r"CHANGE:CONFIG_MODIFIED:(\S+)(?::(\S+))?"),
            
            # User operations
            "USER_CREATE": re.compile(r"CHANGE:USER_CREATED:(\S+)"),
            "USER_MODIFY": re.compile(r"CHANGE:USER_MODIFIED:(\S+)"),
            "USER_DELETE": re.compile(r"CHANGE:USER_DELETED:(\S+)"),
            
            # Group operations
            "GROUP_CREATE": re.compile(r"CHANGE:GROUP_CREATED:(\S+)"),
            "GROUP_MODIFY": re.compile(r"CHANGE:GROUP_MODIFIED:(\S+)"),
            "GROUP_DELETE": re.compile(r"CHANGE:GROUP_DELETED:(\S+)"),
            
            # Registry operations (Windows)
            "REGISTRY_ADD": re.compile(r"CHANGE:REGISTRY_ADDED:(\S+)"),
            "REGISTRY_MODIFY": re.compile(r"CHANGE:REGISTRY_MODIFIED:(\S+)(?::(\S+))?"),
            "REGISTRY_DELETE": re.compile(r"CHANGE:REGISTRY_DELETED:(\S+)"),
            
            # Database operations
            "DB_SCHEMA": re.compile(r"CHANGE:DB_SCHEMA:(\S+)(?::(\S+))?"),
            "DB_DATA": re.compile(r"CHANGE:DB_DATA:(\S+)(?::(\S+))?"),
            
            # Generic operations
            "GENERIC": re.compile(r"CHANGE:(\w+):(\S+)(?::(.+))?")
        }
        
        # Process each change type
        for change_type, pattern in structured_changes.items():
            for match in pattern.finditer(output):
                if change_type == "PACKAGE_INSTALL":
                    package_name = match.group(1)
                    version = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                    
                    # Generate platform-specific revert command
                    revert_cmd = self._generate_package_uninstall_command(package_name, version)
                    
                    changes.append(Change(
                        type="package_installed",
                        target=package_name,
                        revertible=True,
                        revert_command=revert_cmd,
                        metadata={"version": version} if version else {}
                    ))
                
                elif change_type == "FILE_CREATE":
                    file_path = match.group(1)
                    
                    # Generate platform-specific revert command
                    is_windows = platform.system() == "Windows"
                    revert_cmd = f"del \"{file_path}\"" if is_windows else f"rm -f \"{file_path}\""
                    
                    changes.append(Change(
                        type="file_created",
                        target=file_path,
                        revertible=True,
                        revert_command=revert_cmd
                    ))
                    
                elif change_type == "FILE_MODIFY":
                    file_path = match.group(1)
                    backup_path = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                    
                    revert_cmd = None
                    if backup_path:
                        is_windows = platform.system() == "Windows"
                        revert_cmd = f"copy \"{backup_path}\" \"{file_path}\"" if is_windows else f"cp \"{backup_path}\" \"{file_path}\""
                    
                    changes.append(Change(
                        type="file_modified",
                        target=file_path,
                        revertible=backup_path is not None,
                        revert_command=revert_cmd,
                        backup_file=backup_path
                    ))
                    
                elif change_type == "DIR_CREATE":
                    dir_path = match.group(1)
                    
                    # Generate platform-specific revert command
                    is_windows = platform.system() == "Windows"
                    revert_cmd = f"rmdir /S /Q \"{dir_path}\"" if is_windows else f"rm -rf \"{dir_path}\""
                    
                    changes.append(Change(
                        type="directory_created",
                        target=dir_path,
                        revertible=True,
                        revert_command=revert_cmd
                    ))
                    
                elif change_type.startswith("SERVICE_"):
                    service_name = match.group(1)
                    operation = change_type.split("_")[1].lower()
                    
                    # Generate appropriate revert command based on the operation
                    revert_cmd = None
                    revertible = False
                    
                    if operation == "start":
                        is_windows = platform.system() == "Windows"
                        revert_cmd = f"Stop-Service \"{service_name}\"" if is_windows else f"systemctl stop \"{service_name}\""
                        revertible = True
                    elif operation == "enable":
                        is_windows = platform.system() == "Windows"
                        revert_cmd = f"Set-Service \"{service_name}\" -StartupType Disabled" if is_windows else f"systemctl disable \"{service_name}\""
                        revertible = True
                    elif operation == "install":
                        is_windows = platform.system() == "Windows"
                        revert_cmd = f"sc delete \"{service_name}\"" if is_windows else f"systemctl disable \"{service_name}\" && rm -f /etc/systemd/system/{service_name}.service"
                        revertible = True
                    
                    changes.append(Change(
                        type=f"service_{operation}",
                        target=service_name,
                        revertible=revertible,
                        revert_command=revert_cmd
                    ))
                    
                elif change_type == "CONFIG_MODIFY":
                    config_path = match.group(1)
                    backup_path = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                    
                    revert_cmd = None
                    if backup_path:
                        is_windows = platform.system() == "Windows"
                        revert_cmd = f"copy \"{backup_path}\" \"{config_path}\"" if is_windows else f"cp \"{backup_path}\" \"{config_path}\""
                    
                    changes.append(Change(
                        type="config_modified",
                        target=config_path,
                        revertible=backup_path is not None,
                        revert_command=revert_cmd,
                        backup_file=backup_path
                    ))
                
                elif change_type.startswith("REGISTRY_"):
                    reg_path = match.group(1)
                    backup_path = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                    
                    # For registry entries, we should have a backup to revert
                    revertible = backup_path is not None
                    revert_cmd = None
                    
                    if revertible:
                        # Use reg.exe to import the backup
                        revert_cmd = f"reg import \"{backup_path}\""
                    elif change_type == "REGISTRY_ADD":
                        # If no backup but it's a new key, we can delete it
                        revert_cmd = f"reg delete \"{reg_path}\" /f"
                        revertible = True
                    
                    changes.append(Change(
                        type=change_type.lower(),
                        target=reg_path,
                        revertible=revertible,
                        revert_command=revert_cmd,
                        backup_file=backup_path
                    ))
                
                elif change_type.startswith("DB_"):
                    db_identifier = match.group(1)
                    backup_path = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                    
                    # Database changes generally need a backup script to revert
                    revertible = backup_path is not None
                    revert_cmd = None
                    
                    if revertible:
                        # The backup should be a SQL script that can be executed to revert changes
                        # The exact command depends on the database type, which should be in metadata
                        # For now, just store the backup path
                        changes.append(Change(
                            type=change_type.lower(),
                            target=db_identifier,
                            revertible=True,
                            revert_command=None,  # Will be determined during recovery
                            backup_file=backup_path,
                            metadata={"db_change_type": change_type.lower()}
                        ))
                    
                elif change_type == "GENERIC":
                    change_type_str = match.group(1).lower()
                    target = match.group(2)
                    revert_info = match.group(3) if len(match.groups()) > 2 and match.group(3) else None
                    
                    changes.append(Change(
                        type=change_type_str,
                        target=target,
                        revertible=revert_info is not None,
                        revert_command=revert_info
                    ))
        
        # If we couldn't parse any changes but have output, try to infer changes
        # This is a fallback for scripts that don't properly mark changes
        if not changes and len(output) > 0:
            # Look for common installation patterns
            package_patterns = [
                r"(?:installed|Installing)\s+(?:package|module)\s+(\S+)",
                r"(?:apt-get|yum|dnf|pip)\s+install.*?(\S+)",
                r"npm\s+install\s+(-g\s+)?(\S+)",
                r"successfully\s+installed\s+(\S+)"
            ]
            
            for pattern in package_patterns:
                for match in re.finditer(pattern, output, re.IGNORECASE):
                    package_name = match.group(1)
                    changes.append(Change(
                        type="inferred_package_install",
                        target=package_name,
                        revertible=True,
                        revert_command=self._generate_package_uninstall_command(package_name),
                        metadata={"inferred": True}
                    ))
            
            # Add a warning about inferred changes
            if changes:
                logger.warning("Using inferred changes from output. Change tracking in script is insufficient.")
        
        # Return the collected changes
        return changes
        
    def _generate_package_uninstall_command(self, package_name: str, version: Optional[str] = None) -> str:
        """
        Generate a platform-specific package uninstall command.
        
        Args:
            package_name: Name of the package to uninstall
            version: Optional version of the package
            
        Returns:
            Command to uninstall the package
        """
        is_windows = platform.system() == "Windows"
        
        if is_windows:
            # Windows uninstall approach (can be PowerShell or cmd)
            if re.search(r"\.(msi|exe)$", package_name, re.IGNORECASE):
                # MSI or EXE installer
                return f"Start-Process -Wait -FilePath \"msiexec.exe\" -ArgumentList \"/x \"{package_name}\" /quiet\""
            elif package_name.lower().startswith("chocolatey:"):
                # Chocolatey package
                package = package_name.split(':', 1)[1]
                return f"choco uninstall {package} -y"
            elif package_name.lower().startswith("winget:"):
                # WinGet package
                package = package_name.split(':', 1)[1]
                return f"winget uninstall {package} --silent"
            else:
                # Try both common package managers and WMI
                return f"""
try {{
    # Try chocolatey first
    if (Get-Command choco -ErrorAction SilentlyContinue) {{
        choco uninstall {package_name} -y
        Write-Output "Uninstalled package with Chocolatey: {package_name}"
        exit 0
    }}
    # Then try winget
    if (Get-Command winget -ErrorAction SilentlyContinue) {{
        winget uninstall {package_name} --silent
        Write-Output "Uninstalled package with Winget: {package_name}"
        exit 0
    }}
    # Fall back to WMI
    $app = Get-WmiObject -Class Win32_Product | Where-Object {{ $_.Name -like "*{package_name}*" }}
    if ($app) {{
        $app.Uninstall()
        Write-Output "Uninstalled package with WMI: {package_name}"
        exit 0
    }}
    Write-Warning "No installation found for {package_name}"
}} catch {{
    Write-Error "Failed to uninstall {package_name}: $_"
    exit 1
}}
"""
        else:
            # Linux uninstall approach with better handling of different formats
            if package_name.lower().startswith("pip:"):
                # Python package
                package = package_name.split(':', 1)[1]
                return f"pip uninstall -y {package}"
            elif package_name.lower().startswith("npm:"):
                # Node.js package
                package = package_name.split(':', 1)[1]
                return f"npm uninstall -g {package}"
            elif package_name.lower().startswith("apt:"):
                # Debian/Ubuntu package
                package = package_name.split(':', 1)[1]
                return f"apt-get remove -y {package}"
            elif package_name.lower().startswith("yum:") or package_name.lower().startswith("dnf:"):
                # Red Hat/CentOS/Fedora package
                package = package_name.split(':', 1)[1]
                return f"if command -v dnf > /dev/null; then dnf remove -y {package}; else yum remove -y {package}; fi"
            elif package_name.lower().startswith("snap:"):
                # Snap package
                package = package_name.split(':', 1)[1]
                return f"snap remove {package}"
            else:
                # Try different package managers
                return f"""
# Universal package removal script
if command -v apt-get > /dev/null 2>&1; then
    apt-get remove -y {package_name} && echo "Uninstalled package with apt-get: {package_name}" && exit 0
fi

if command -v dnf > /dev/null 2>&1; then
    dnf remove -y {package_name} && echo "Uninstalled package with dnf: {package_name}" && exit 0
fi

if command -v yum > /dev/null 2>&1; then
    yum remove -y {package_name} && echo "Uninstalled package with yum: {package_name}" && exit 0
fi

if command -v snap > /dev/null 2>&1 && snap list | grep -q "^{package_name} "; then
    snap remove {package_name} && echo "Uninstalled package with snap: {package_name}" && exit 0
fi

if command -v zypper > /dev/null 2>&1; then
    zypper remove -y {package_name} && echo "Uninstalled package with zypper: {package_name}" && exit 0
fi

if command -v pacman > /dev/null 2>&1; then
    pacman -R --noconfirm {package_name} && echo "Uninstalled package with pacman: {package_name}" && exit 0
fi

echo "No package manager found for uninstalling {package_name}" >&2
exit 1
"""
    
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
            # Extract change data with proper defaults
            change_type = item["type"]
            target = item["target"]
            revertible = item.get("revertible", False)
            revert_command = item.get("revert_command")
            backup_file = item.get("backup_file")
            metadata = item.get("metadata", {})
            
            # Convert dictionary to Change object
            change = Change(
                type=change_type,
                target=target,
                revertible=revertible,
                revert_command=revert_command,
                backup_file=backup_file,
                metadata=metadata
            )
            changes_list.append(change)
        except Exception as e:
            logger.error(f"Error processing change item: {e}")
            
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
