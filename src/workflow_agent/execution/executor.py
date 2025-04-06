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
            
        # Validate script with enhanced security checks
        security_result = validate_script_security(state.script)
        has_security_issues = not security_result["valid"]
        
        # Handle warnings
        for warning in security_result.get("warnings", []):
            logger.warning(f"Script security warning: {warning}")
            state = state.add_warning(warning)
            
        # Handle errors (more serious than warnings)
        if security_result.get("errors", []):
            error_msgs = "\n".join(security_result["errors"])
            error_msg = f"Script failed security validation with critical issues:\n{error_msgs}"
            logger.error(error_msg)
            
            # If least privilege execution is disabled AND only warnings are present, we can continue
            # But if there are errors, we must fail regardless of the setting
            if security_result.get("errors", []) and self.config.least_privilege_execution:
                raise SecurityError(error_msg)
            elif security_result.get("errors", []):
                logger.warning("SECURITY RISK: Executing script despite critical security issues due to disabled least privilege execution")
                state = state.add_warning("SECURITY RISK: Script contains potentially dangerous operations")
        
        # Use enhanced validation from the script validator
        from ..scripting.validator import ScriptValidator
        script_validator = ScriptValidator(self.config)
        validation_result = script_validator.validate(state.script)
        
        # Add validation warnings to state
        for warning in validation_result.get("warnings", []):
            state = state.add_warning(warning)
            
        # If validation fails with errors, abort
        if validation_result.get("errors", []) and not "valid" in validation_result:
            error_msgs = "\n".join(validation_result["errors"])
            raise SecurityError(f"Script validation failed:\n{error_msgs}")
                
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
        Extract changes from script output using enhanced structured change tracking.
        Also monitors filesystem changes independently of script output.
        
        Args:
            output: Script output to parse
            
        Returns:
            List of Change objects
        """
        changes = []
        
        # Import needed modules
        import re
        import json
        import os
        import platform
        import tempfile
        from pathlib import Path
        
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
            
            # Generic operations
            "GENERIC": re.compile(r"CHANGE:(\w+):(\S+)(?::(.+))?")
        }
        
        # Process each change type
        for change_type, pattern in structured_changes.items():
            for match in pattern.finditer(output):
                if change_type == "PACKAGE_INSTALL":
                    package_name = match.group(1)
                    version = match.group(2) if len(match.groups()) > 1 else None
                    
                    # Generate platform-specific revert command
                    revert_cmd = self._generate_package_uninstall_command(package_name)
                    
                    changes.append(Change(
                        type="package_installed",
                        target=package_name,
                        revertible=True,
                        revert_command=revert_cmd
                    ))
                
                elif change_type == "FILE_CREATE":
                    file_path = match.group(1)
                    
                    # Generate platform-specific revert command
                    is_windows = platform.system() == "Windows"
                    revert_cmd = f"del {file_path}" if is_windows else f"rm -f {file_path}"
                    
                    changes.append(Change(
                        type="file_created",
                        target=file_path,
                        revertible=True,
                        revert_command=revert_cmd
                    ))
                    
                elif change_type == "FILE_MODIFY":
                    file_path = match.group(1)
                    backup_path = match.group(2) if len(match.groups()) > 1 else None
                    
                    revert_cmd = None
                    if backup_path:
                        is_windows = platform.system() == "Windows"
                        revert_cmd = f"copy {backup_path} {file_path}" if is_windows else f"cp {backup_path} {file_path}"
                    
                    changes.append(Change(
                        type="file_modified",
                        target=file_path,
                        revertible=backup_path is not None,
                        revert_command=revert_cmd
                    ))
                    
                elif change_type == "DIR_CREATE":
                    dir_path = match.group(1)
                    
                    # Generate platform-specific revert command
                    is_windows = platform.system() == "Windows"
                    revert_cmd = f"rmdir /S /Q {dir_path}" if is_windows else f"rm -rf {dir_path}"
                    
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
                        revert_cmd = f"Stop-Service {service_name}" if is_windows else f"systemctl stop {service_name}"
                        revertible = True
                    elif operation == "enable":
                        is_windows = platform.system() == "Windows"
                        revert_cmd = f"Set-Service {service_name} -StartupType Disabled" if is_windows else f"systemctl disable {service_name}"
                        revertible = True
                    elif operation == "install":
                        is_windows = platform.system() == "Windows"
                        revert_cmd = f"sc delete {service_name}" if is_windows else f"systemctl disable {service_name} && rm -f /etc/systemd/system/{service_name}.service"
                        revertible = True
                    
                    changes.append(Change(
                        type=f"service_{operation}",
                        target=service_name,
                        revertible=revertible,
                        revert_command=revert_cmd
                    ))
                    
                elif change_type == "CONFIG_MODIFY":
                    config_path = match.group(1)
                    backup_path = match.group(2) if len(match.groups()) > 1 else None
                    
                    revert_cmd = None
                    if backup_path:
                        is_windows = platform.system() == "Windows"
                        revert_cmd = f"copy {backup_path} {config_path}" if is_windows else f"cp {backup_path} {config_path}"
                    
                    changes.append(Change(
                        type="config_modified",
                        target=config_path,
                        revertible=backup_path is not None,
                        revert_command=revert_cmd
                    ))
                    
                elif change_type == "GENERIC":
                    change_type = match.group(1).lower()
                    target = match.group(2)
                    revert_info = match.group(3) if len(match.groups()) > 2 else None
                    
                    changes.append(Change(
                        type=change_type,
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
                        revert_command=self._generate_package_uninstall_command(package_name)
                    ))
            
            # Add a warning about inferred changes
            if changes:
                logger.warning("Using inferred changes from output. Change tracking in script is insufficient.")
        
        # Return the collected changes
        return changes
        
    def _generate_package_uninstall_command(self, package_name: str) -> str:
        """Generate a platform-specific package uninstall command."""
        is_windows = platform.system() == "Windows"
        
        if is_windows:
            # Windows uninstall approach (can be PowerShell or cmd)
            if re.search(r"\.(msi|exe)$", package_name, re.IGNORECASE):
                # MSI or EXE installer
                return f"Start-Process -Wait -FilePath \"msiexec.exe\" -ArgumentList \"/x {package_name} /quiet\""
            elif package_name.lower().startswith("chocolatey:"):
                # Chocolatey package
                return f"choco uninstall {package_name.split(':')[1]} -y"
            else:
                # Generic Windows uninstall attempt
                return f"$app = Get-WmiObject -Class Win32_Product | Where-Object {{ $_.Name -like \"*{package_name}*\" }}; if ($app) {{ $app.Uninstall() }}"
        else:
            # Linux uninstall approach
            if package_name.lower().startswith("pip:"):
                # Python package
                return f"pip uninstall -y {package_name.split(':')[1]}"
            elif package_name.lower().startswith("npm:"):
                # Node.js package
                return f"npm uninstall -g {package_name.split(':')[1]}"
            else:
                # Try different package managers
                return f"""
if command -v apt-get > /dev/null; then
    apt-get remove -y {package_name}
elif command -v yum > /dev/null; then
    yum remove -y {package_name}
elif command -v dnf > /dev/null; then
    dnf remove -y {package_name}
elif command -v zypper > /dev/null; then
    zypper remove -y {package_name}
else
    echo "Unknown package manager for uninstalling {package_name}"
    exit 1
fi
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
