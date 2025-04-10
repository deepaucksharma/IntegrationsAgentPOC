"""
Consolidated change tracking module for execution results.
This centralizes the change tracking functionality previously embedded in the executor.
"""
import re
import json
import logging
import platform
from typing import Dict, Any, List, Optional

from ..core.state import Change

logger = logging.getLogger(__name__)

class ChangeTracker:
    """
    Centralized change tracking functionality for script execution.
    Extracts and standardizes changes from script output.
    """
    
    def __init__(self):
        """Initialize the change tracker."""
        self._platform_info = {
            "is_windows": platform.system() == "Windows",
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version()
        }
    
    def extract_changes(self, output: str) -> List[Change]:
        """
        Extract changes from script output using enhanced structured change tracking.
        Processes both structured JSON blocks and simple change markers.
        
        Args:
            output: Script output to parse
            
        Returns:
            List of Change objects
        """
        changes = []
        
        # Step 1: Process JSON change blocks - the most reliable format
        self._process_json_changes(output, changes)
        
        # Step 2: Process structured change markers
        self._process_structured_changes(output, changes)
        
        # Step 3: If no changes detected, try to infer from output
        if not changes and len(output) > 0:
            changes.extend(self._infer_changes_from_output(output))
        
        # Log the detected changes
        logger.info(f"Extracted {len(changes)} changes from script output")
        return changes
    
    def _process_json_changes(self, output: str, changes_list: List[Change]) -> None:
        """
        Process JSON change blocks in script output.
        
        Args:
            output: Script output to parse
            changes_list: List to add extracted changes to
        """
        # Find JSON blocks marked with CHANGE_JSON_BEGIN and CHANGE_JSON_END
        json_change_blocks = re.findall(r"CHANGE_JSON_BEGIN\s*(.*?)\s*CHANGE_JSON_END", output, re.DOTALL)
        
        for json_block in json_change_blocks:
            try:
                change_data = json.loads(json_block)
                
                # Handle both single change and array of changes
                if isinstance(change_data, list):
                    for item in change_data:
                        self._process_change_item(item, changes_list)
                else:
                    self._process_change_item(change_data, changes_list)
                    
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON change block: {json_block[:100]}")
    
    def _process_change_item(self, item: Dict[str, Any], changes_list: List[Change]) -> None:
        """
        Process a single change item from JSON and add it to the changes list.
        
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
    
    def _process_structured_changes(self, output: str, changes_list: List[Change]) -> None:
        """
        Process structured change markers in script output.
        
        Args:
            output: Script output to parse
            changes_list: List to add extracted changes to
        """
        # Define patterns for different change types
        change_patterns = {
            # File operations
            r"CHANGE:FILE_CREATED:(\S+)": lambda match: self._create_file_change("file_created", match[0]),
            r"CHANGE:FILE_MODIFIED:(\S+)(?::(\S+))?": lambda match: self._create_file_change("file_modified", match[0], match[1] if len(match) > 1 else None),
            r"CHANGE:FILE_DELETED:(\S+)": lambda match: self._create_file_change("file_deleted", match[0]),
            r"CHANGE:FILE_PERMISSIONS:(\S+)(?::(\S+))?": lambda match: self._create_file_change("file_permissions_changed", match[0], match[1] if len(match) > 1 else None),
            r"CHANGE:FILE_OWNERSHIP:(\S+)(?::(\S+))?": lambda match: self._create_file_change("file_ownership_changed", match[0], match[1] if len(match) > 1 else None),
            
            # Directory operations
            r"CHANGE:DIRECTORY_CREATED:(\S+)": lambda match: self._create_directory_change("directory_created", match[0]),
            r"CHANGE:DIRECTORY_DELETED:(\S+)": lambda match: self._create_directory_change("directory_deleted", match[0]),
            
            # Package operations
            r"CHANGE:PACKAGE_INSTALLED:(\S+)(?::(\S+))?": lambda match: self._create_package_change("package_installed", match[0], match[1] if len(match) > 1 else None),
            r"CHANGE:PACKAGE_REMOVED:(\S+)": lambda match: self._create_package_change("package_removed", match[0]),
            r"CHANGE:PACKAGE_UPDATED:(\S+)(?::(\S+))?": lambda match: self._create_package_change("package_updated", match[0], match[1] if len(match) > 1 else None),
            
            # Service operations
            r"CHANGE:SERVICE_INSTALLED:(\S+)": lambda match: self._create_service_change("service_installed", match[0]),
            r"CHANGE:SERVICE_REMOVED:(\S+)": lambda match: self._create_service_change("service_removed", match[0]),
            r"CHANGE:SERVICE_STARTED:(\S+)": lambda match: self._create_service_change("service_started", match[0]),
            r"CHANGE:SERVICE_STOPPED:(\S+)": lambda match: self._create_service_change("service_stopped", match[0]),
            r"CHANGE:SERVICE_ENABLED:(\S+)": lambda match: self._create_service_change("service_enabled", match[0]),
            r"CHANGE:SERVICE_DISABLED:(\S+)": lambda match: self._create_service_change("service_disabled", match[0]),
            
            # Configuration operations
            r"CHANGE:CONFIG_MODIFIED:(\S+)(?::(\S+))?": lambda match: self._create_config_change("config_modified", match[0], match[1] if len(match) > 1 else None),
            
            # Registry operations (Windows)
            r"CHANGE:REGISTRY_ADDED:(\S+)": lambda match: self._create_registry_change("registry_added", match[0]),
            r"CHANGE:REGISTRY_MODIFIED:(\S+)(?::(\S+))?": lambda match: self._create_registry_change("registry_modified", match[0], match[1] if len(match) > 1 else None),
            r"CHANGE:REGISTRY_DELETED:(\S+)": lambda match: self._create_registry_change("registry_deleted", match[0]),
            
            # Generic catch-all
            r"CHANGE:(\w+):(\S+)(?::(.+))?": lambda match: self._create_generic_change(match[0].lower(), match[1], match[2] if len(match) > 2 else None)
        }
        
        # Process each pattern
        for pattern, handler in change_patterns.items():
            for match in re.finditer(pattern, output):
                try:
                    change = handler(match.groups())
                    if change:
                        changes_list.append(change)
                except Exception as e:
                    logger.error(f"Error processing change with pattern {pattern}: {e}")
    
    def _infer_changes_from_output(self, output: str) -> List[Change]:
        """
        Attempt to infer changes from unstructured output.
        This is a fallback when no explicit change markers are present.
        
        Args:
            output: Script output to parse
            
        Returns:
            List of inferred changes
        """
        changes = []
        
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
                changes.append(self._create_package_change(
                    "inferred_package_install", 
                    package_name, 
                    None,
                    metadata={"inferred": True}
                ))
        
        # Look for file operations
        file_patterns = [
            (r"(?:created|creating)\s+(?:file|config)\s+(\S+)", "inferred_file_created"),
            (r"(?:copied|copying)\s+(?:file)\s+.*?to\s+(\S+)", "inferred_file_created"),
            (r"(?:removed|removing)\s+(?:file)\s+(\S+)", "inferred_file_deleted")
        ]
        
        for pattern, change_type in file_patterns:
            for match in re.finditer(pattern, output, re.IGNORECASE):
                file_path = match.group(1)
                changes.append(self._create_file_change(
                    change_type,
                    file_path,
                    None,
                    metadata={"inferred": True}
                ))
        
        # Add a warning about inferred changes
        if changes:
            logger.warning("Using inferred changes from output. Change tracking in script is insufficient.")
        
        return changes
    
    def _create_file_change(
        self, 
        change_type: str, 
        file_path: str, 
        backup_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Change:
        """
        Create a file-related change object.
        
        Args:
            change_type: Type of change
            file_path: Path to the file
            backup_path: Optional path to backup file
            metadata: Optional additional metadata
            
        Returns:
            Change object
        """
        is_windows = self._platform_info["is_windows"]
        revert_cmd = None
        revertible = False
        
        if change_type == "file_created":
            revert_cmd = f'del "{file_path}"' if is_windows else f'rm -f "{file_path}"'
            revertible = True
        elif change_type == "file_modified" and backup_path:
            revert_cmd = f'copy "{backup_path}" "{file_path}"' if is_windows else f'cp "{backup_path}" "{file_path}"'
            revertible = True
        elif change_type == "file_permissions_changed" and backup_path:
            # For permissions, backup would contain original permissions info
            revert_cmd = f'icacls "{file_path}" /restore "{backup_path}"' if is_windows else f'chmod --reference="{backup_path}" "{file_path}"'
            revertible = True
            
        return Change(
            type=change_type,
            target=file_path,
            revertible=revertible,
            revert_command=revert_cmd,
            backup_file=backup_path if change_type != "file_created" else None,
            metadata=metadata or {}
        )
    
    def _create_directory_change(
        self, 
        change_type: str, 
        dir_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Change:
        """
        Create a directory-related change object.
        
        Args:
            change_type: Type of change
            dir_path: Path to the directory
            metadata: Optional additional metadata
            
        Returns:
            Change object
        """
        is_windows = self._platform_info["is_windows"]
        revert_cmd = None
        revertible = False
        
        if change_type == "directory_created":
            revert_cmd = f'rmdir /S /Q "{dir_path}"' if is_windows else f'rm -rf "{dir_path}"'
            revertible = True
            
        return Change(
            type=change_type,
            target=dir_path,
            revertible=revertible,
            revert_command=revert_cmd,
            metadata=metadata or {}
        )
    
    def _create_package_change(
        self, 
        change_type: str, 
        package_name: str, 
        version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Change:
        """
        Create a package-related change object.
        
        Args:
            change_type: Type of change
            package_name: Name of the package
            version: Optional package version
            metadata: Optional additional metadata
            
        Returns:
            Change object
        """
        revert_cmd = None
        revertible = False
        
        if change_type == "package_installed":
            revert_cmd = self._generate_package_uninstall_command(package_name, version)
            revertible = True
            
        # Create metadata
        change_metadata = metadata or {}
        if version:
            change_metadata["version"] = version
            
        return Change(
            type=change_type,
            target=package_name,
            revertible=revertible,
            revert_command=revert_cmd,
            metadata=change_metadata
        )
    
    def _create_service_change(
        self, 
        change_type: str, 
        service_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Change:
        """
        Create a service-related change object.
        
        Args:
            change_type: Type of change
            service_name: Name of the service
            metadata: Optional additional metadata
            
        Returns:
            Change object
        """
        is_windows = self._platform_info["is_windows"]
        revert_cmd = None
        revertible = False
        
        if change_type == "service_started":
            revert_cmd = f'Stop-Service "{service_name}"' if is_windows else f'systemctl stop "{service_name}"'
            revertible = True
        elif change_type == "service_enabled":
            revert_cmd = f'Set-Service "{service_name}" -StartupType Disabled' if is_windows else f'systemctl disable "{service_name}"'
            revertible = True
        elif change_type == "service_installed":
            if is_windows:
                revert_cmd = f'sc delete "{service_name}"'
            else:
                revert_cmd = f'systemctl disable "{service_name}" && ' \
                           f'systemctl stop "{service_name}" && ' \
                           f'rm -f /etc/systemd/system/{service_name}.service'
            revertible = True
            
        return Change(
            type=change_type,
            target=service_name,
            revertible=revertible,
            revert_command=revert_cmd,
            metadata=metadata or {}
        )
    
    def _create_config_change(
        self, 
        change_type: str, 
        config_path: str, 
        backup_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Change:
        """
        Create a configuration-related change object.
        
        Args:
            change_type: Type of change
            config_path: Path to the configuration file
            backup_path: Optional path to backup file
            metadata: Optional additional metadata
            
        Returns:
            Change object
        """
        is_windows = self._platform_info["is_windows"]
        revert_cmd = None
        revertible = False
        
        if backup_path:
            revert_cmd = f'copy "{backup_path}" "{config_path}"' if is_windows else f'cp "{backup_path}" "{config_path}"'
            revertible = True
            
        return Change(
            type=change_type,
            target=config_path,
            revertible=revertible,
            revert_command=revert_cmd,
            backup_file=backup_path,
            metadata=metadata or {}
        )
    
    def _create_registry_change(
        self, 
        change_type: str, 
        registry_path: str, 
        backup_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Change:
        """
        Create a registry-related change object (Windows-specific).
        
        Args:
            change_type: Type of change
            registry_path: Registry path
            backup_path: Optional path to backup file
            metadata: Optional additional metadata
            
        Returns:
            Change object
        """
        revert_cmd = None
        revertible = False
        
        if change_type == "registry_added":
            revert_cmd = f'reg delete "{registry_path}" /f'
            revertible = True
        elif backup_path:
            revert_cmd = f'reg import "{backup_path}"'
            revertible = True
            
        return Change(
            type=change_type,
            target=registry_path,
            revertible=revertible,
            revert_command=revert_cmd,
            backup_file=backup_path,
            metadata=metadata or {}
        )
    
    def _create_generic_change(
        self, 
        change_type: str, 
        target: str, 
        revert_info: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Change:
        """
        Create a generic change object for any other change type.
        
        Args:
            change_type: Type of change
            target: Target of the change
            revert_info: Optional revert command or information
            metadata: Optional additional metadata
            
        Returns:
            Change object
        """
        return Change(
            type=change_type,
            target=target,
            revertible=revert_info is not None,
            revert_command=revert_info,
            metadata=metadata or {}
        )
    
    def _generate_package_uninstall_command(self, package_name: str, version: Optional[str] = None) -> str:
        """
        Generate a platform-specific package uninstall command.
        
        Args:
            package_name: Name of the package
            version: Optional version of the package
            
        Returns:
            Command to uninstall the package
        """
        is_windows = self._platform_info["is_windows"]
        
        if is_windows:
            # Windows uninstall approach (can be PowerShell or cmd)
            if re.search(r"\.(msi|exe)$", package_name, re.IGNORECASE):
                # MSI or EXE installer
                return f'Start-Process -Wait -FilePath "msiexec.exe" -ArgumentList "/x \\"{package_name}\\" /quiet"'
            elif package_name.lower().startswith("chocolatey:"):
                # Chocolatey package
                package = package_name.split(':', 1)[1]
                return f'choco uninstall {package} -y'
            elif package_name.lower().startswith("winget:"):
                # WinGet package
                package = package_name.split(':', 1)[1]
                return f'winget uninstall {package} --silent'
            else:
                # Try both common package managers and WMI
                return f"""
try {{
    # Try chocolatey first
    if (Get-Command choco -ErrorAction SilentlyContinue) {{
        choco uninstall {package_name} -y
        exit 0
    }}
    # Then try winget
    if (Get-Command winget -ErrorAction SilentlyContinue) {{
        winget uninstall {package_name} --silent
        exit 0
    }}
    # Fall back to WMI
    $app = Get-WmiObject -Class Win32_Product | Where-Object {{ $_.Name -like "*{package_name}*" }}
    if ($app) {{
        $app.Uninstall()
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
    apt-get remove -y {package_name} && exit 0
fi

if command -v dnf > /dev/null 2>&1; then
    dnf remove -y {package_name} && exit 0
fi

if command -v yum > /dev/null 2>&1; then
    yum remove -y {package_name} && exit 0
fi

if command -v snap > /dev/null 2>&1 && snap list | grep -q "^{package_name} "; then
    snap remove {package_name} && exit 0
fi

if command -v zypper > /dev/null 2>&1; then
    zypper remove -y {package_name} && exit 0
fi

if command -v pacman > /dev/null 2>&1; then
    pacman -R --noconfirm {package_name} && exit 0
fi

echo "No package manager found for uninstalling {package_name}" >&2
exit 1
"""
