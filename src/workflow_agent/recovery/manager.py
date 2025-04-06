"""
Recovery Manager for handling rollback of failed workflows.
"""
import asyncio
import logging
import os
import tempfile
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..core.state import WorkflowState, Change
from ..error.exceptions import RecoveryError

logger = logging.getLogger(__name__)

class RecoveryManager:
    """
    Manages recovery and rollback operations for workflows.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration."""
        self.config = config
        self.isolation_method = config.get("isolation_method", "direct")
        self.use_recovery = config.get("use_recovery", True)
    
    async def recover(self, state: WorkflowState) -> WorkflowState:
        """
        Recover from a failed workflow by rolling back changes.
        
        Args:
            state: The current workflow state.
            
        Returns:
            Updated workflow state after recovery.
        """
        if not self.use_recovery:
            logger.info("Recovery is disabled, skipping")
            return state.add_warning("Recovery is disabled")
            
        if not state.changes:
            logger.info("No changes to rollback")
            return state.add_message("Nothing to rollback")
            
        logger.info(f"Starting recovery for workflow: {state.execution_id}")
        
        try:
            # Generate rollback script
            rollback_script = await self._generate_rollback_script(state)
            
            if not rollback_script:
                logger.warning("Could not generate rollback script")
                return state.add_warning("Rollback skipped - no rollback actions available")
                
            # Create a temporary file for the rollback script
            with tempfile.NamedTemporaryFile(
                suffix=self._get_script_extension(state),
                delete=False,
                mode='w+'
            ) as script_file:
                script_path = script_file.name
                script_file.write(rollback_script)
                
            try:
                # Make script executable on Unix-like systems
                if os.name != 'nt':
                    os.chmod(script_path, 0o755)
                    
                # Execute rollback script
                logger.info(f"Executing rollback script: {script_path}")
                cmd = self._get_execution_command(script_path, state)
                
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.config.get("execution_timeout", 300)
                    )
                except asyncio.TimeoutError:
                    process.terminate()
                    logger.error("Rollback script execution timed out")
                    return state.add_warning("Rollback timed out").mark_reverted()
                
                # Process results
                stdout_str = stdout.decode() if stdout else ""
                stderr_str = stderr.decode() if stderr else ""
                
                if process.returncode != 0:
                    logger.error(f"Rollback failed: {stderr_str}")
                    return state.add_warning(f"Rollback failed: {stderr_str}").mark_reverted()
                
                # Update state with rollback outcome
                logger.info("Rollback completed successfully")
                new_state = state.add_message("Rollback completed successfully")
                new_state = new_state.evolve(output=None)  # Clear original error output
                return new_state.mark_reverted()
                
            finally:
                # Clean up temporary script file
                try:
                    os.unlink(script_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary script: {e}")
                
        except Exception as e:
            logger.error(f"Error during recovery: {e}", exc_info=True)
            return state.add_warning(f"Recovery failed: {str(e)}")
                
    async def _generate_rollback_script(self, state: WorkflowState) -> Optional[str]:
        """
        Generate a rollback script based on recorded changes.
        
        Args:
            state: The workflow state with changes to revert.
            
        Returns:
            Script content or None if no reversible changes.
        """
        if not state.changes:
            return None
            
        is_windows = state.system_context.get('is_windows', os.name == 'nt')
        script_header = self._get_script_header(is_windows)
        
        revert_commands = []
        for change in reversed(state.changes):
            if not isinstance(change, Change):
                logger.warning(f"Skipping invalid change object: {change}")
                continue
                
            if not change.revertible:
                continue
                
            if change.revert_command:
                revert_commands.append(change.revert_command)
            else:
                # Generate revert command based on change type
                cmd = None
                if change.type == 'file_created':
                    cmd = self._get_file_remove_command(change.target, is_windows)
                elif change.type == 'directory_created':
                    cmd = self._get_directory_remove_command(change.target, is_windows)
                elif change.type == 'package_installed':
                    cmd = self._get_package_revert_command(change.target, is_windows)
                elif change.type == 'service_started':
                    cmd = self._get_service_revert_command(change.target, is_windows)
                    
                if cmd:
                    revert_commands.append(cmd)
        
        if not revert_commands:
            return None
            
        script_footer = self._get_script_footer(is_windows)
        return script_header + "\n".join(revert_commands) + "\n" + script_footer
        
    def _get_script_header(self, is_windows: bool) -> str:
        """Get the script header based on platform."""
        if is_windows:
            return """# Automatic rollback script
$ErrorActionPreference = "Stop"

function Log-Message {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
}

function Log-Error {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: $Message" -ForegroundColor Red
}

Log-Message "Starting rollback operations..."

"""
        else:
            return """#!/bin/bash
# Automatic rollback script
set -e

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

log_message "Starting rollback operations..."

"""
    
    def _get_script_footer(self, is_windows: bool) -> str:
        """Get the script footer based on platform."""
        if is_windows:
            return """
Log-Message "Rollback completed successfully"
"""
        else:
            return """
log_message "Rollback completed successfully"
"""
    
    def _get_script_extension(self, state: WorkflowState) -> str:
        """Get the appropriate script extension."""
        is_windows = state.system_context.get('is_windows', os.name == 'nt')
        return '.ps1' if is_windows else '.sh'
    
    def _get_execution_command(self, script_path: str, state: WorkflowState) -> str:
        """Get the command to execute the script."""
        is_windows = state.system_context.get('is_windows', os.name == 'nt')
        
        if is_windows:
            return f'powershell.exe -ExecutionPolicy Bypass -File "{script_path}"'
        else:
            return f'bash "{script_path}"'
    
    def _get_file_remove_command(self, file_path: str, is_windows: bool) -> str:
        """Generate command to remove a file."""
        if is_windows:
            return f'if (Test-Path "{file_path}") {{ Remove-Item -Path "{file_path}" -Force; Log-Message "Removed file: {file_path}" }} else {{ Log-Message "File not found: {file_path}" }}'
        else:
            return f'if [ -f "{file_path}" ]; then rm -f "{file_path}" && log_message "Removed file: {file_path}"; else log_message "File not found: {file_path}"; fi'
    
    def _get_directory_remove_command(self, dir_path: str, is_windows: bool) -> str:
        """Generate command to remove a directory."""
        if is_windows:
            return f'if (Test-Path -Path "{dir_path}" -PathType Container) {{ Remove-Item -Path "{dir_path}" -Recurse -Force; Log-Message "Removed directory: {dir_path}" }} else {{ Log-Message "Directory not found: {dir_path}" }}'
        else:
            return f'if [ -d "{dir_path}" ]; then rm -rf "{dir_path}" && log_message "Removed directory: {dir_path}"; else log_message "Directory not found: {dir_path}"; fi'
    
    def _get_package_revert_command(self, package: str, is_windows: bool) -> str:
        """Generate command to uninstall a package."""
        if is_windows:
            return f"""
try {{
    if (Get-Command choco -ErrorAction SilentlyContinue) {{
        choco uninstall {package} -y
        Log-Message "Uninstalled package with Chocolatey: {package}"
    }} elseif (Get-Command winget -ErrorAction SilentlyContinue) {{
        winget uninstall {package} --silent
        Log-Message "Uninstalled package with Winget: {package}"
    }} else {{
        $app = Get-WmiObject -Class Win32_Product | Where-Object {{ $_.Name -like "*{package}*" }}
        if ($app) {{
            $app.Uninstall()
            Log-Message "Uninstalled package: {package}"
        }} else {{
            Log-Message "No installation found for {package}"
        }}
    }}
}} catch {{
    Log-Error "Failed to uninstall {package}: $_"
}}"""
        else:
            return f"""
if command -v snap >/dev/null 2>&1 && snap list | grep -q "^{package} "; then
    snap remove {package} && log_message "Uninstalled package with snap: {package}" || log_error "Failed to uninstall {package} with snap"
elif command -v apt-get >/dev/null 2>&1; then
    apt-get remove -y {package} && log_message "Uninstalled package with apt-get: {package}" || log_error "Failed to uninstall {package} with apt-get"
elif command -v yum >/dev/null 2>&1; then
    yum remove -y {package} && log_message "Uninstalled package with yum: {package}" || log_error "Failed to uninstall {package} with yum"
elif command -v dnf >/dev/null 2>&1; then
    dnf remove -y {package} && log_message "Uninstalled package with dnf: {package}" || log_error "Failed to uninstall {package} with dnf"
elif command -v zypper >/dev/null 2>&1; then
    zypper remove -y {package} && log_message "Uninstalled package with zypper: {package}" || log_error "Failed to uninstall {package} with zypper"
elif command -v pacman >/dev/null 2>&1; then
    pacman -R --noconfirm {package} && log_message "Uninstalled package with pacman: {package}" || log_error "Failed to uninstall {package} with pacman"
else
    log_error "No package manager found to uninstall {package}"
fi
"""
    
    def _get_service_revert_command(self, service: str, is_windows: bool) -> str:
        """Generate command to stop a service."""
        if is_windows:
            return f"""
try {{
    if (Get-Service -Name "{service}" -ErrorAction SilentlyContinue) {{
        Stop-Service -Name "{service}" -Force
        Set-Service -Name "{service}" -StartupType Disabled
        Log-Message "Stopped service: {service}"
    }} else {{
        Log-Message "Service not found: {service}"
    }}
}} catch {{
    Log-Error "Failed to stop service {service}: $_"
}}"""
        else:
            return f"""
if systemctl is-active --quiet {service}; then
    systemctl stop {service} && log_message "Stopped service: {service}" || log_error "Failed to stop {service}"
    systemctl disable {service} && log_message "Disabled service: {service}" || log_error "Failed to disable {service}"
elif service {service} status >/dev/null 2>&1; then
    service {service} stop && log_message "Stopped service: {service}" || log_error "Failed to stop {service}"
else
    log_message "Service not found: {service}"
fi
"""
