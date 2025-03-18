from dataclasses import dataclass
from typing import Optional, Dict, Any
import os
import asyncio
import tempfile
import logging
import re

logger = logging.getLogger(__name__)

@dataclass
class Change:
    type: str
    target: str
    revertible: bool = True
    revert_command: Optional[str] = None

async def perform_rollback(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Performs a rollback of changes based on the workflow state and configuration.
    
    Args:
        state: The current workflow state.
        config: Optional configuration overrides.
            
    Returns:
        Dict containing the rollback result with keys:
        - status: 'success', 'warning', or 'error'
        - message: Description of the result
        - output: Command output (if successful)
        - error: Detailed error information (if failed)
    """
    if not state:
        logger.error("Cannot perform rollback: Invalid workflow state")
        return {"status": "error", "message": "Invalid workflow state"}

    logger.info(f"Starting rollback for action: {state.action}, target: {state.target_name}")
    
    if not state.changes and not state.legacy_changes:
        logger.info("No changes to rollback")
        return {"status": "success", "message": "Nothing to rollback"}
    
    try:
        # Build a rollback script based on the recorded changes
        rollback_script = await self._generate_rollback_script(state)
        
        if not rollback_script:
            logger.warning("Could not generate rollback script")
            return {
                "status": "warning", 
                "message": "Rollback skipped - no rollback actions available"
            }
        
        # Create a temporary file for the rollback script
        fd, script_path = tempfile.mkstemp(suffix=self._get_script_extension(state))
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(rollback_script)
            
            # Make the script executable on Unix systems
            if os.name != 'nt':
                os.chmod(script_path, 0o755)
            
            # Execute the rollback script with timeout
            logger.info(f"Executing rollback script: {script_path}")
            cmd = self._get_execution_command(script_path, state)
            
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)  # 5 minute timeout
            except asyncio.TimeoutError:
                process.terminate()
                logger.error("Rollback script execution timed out")
                return {
                    "status": "error",
                    "message": "Rollback timed out after 5 minutes",
                    "error": "Script execution timeout"
                }
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error during rollback"
                logger.error(f"Rollback failed: {error_msg}")
                return {
                    "status": "error", 
                    "message": f"Rollback failed: {error_msg}",
                    "error": error_msg,
                    "output": stdout.decode() if stdout else ""
                }
            
            logger.info("Rollback completed successfully")
            return {
                "status": "success", 
                "message": "Rollback completed successfully",
                "output": stdout.decode() if stdout else ""
            }
            
        finally:
            # Clean up temporary script file
            try:
                os.unlink(script_path)
            except Exception as e:
                logger.warning(f"Failed to remove temporary script: {e}")
        
    except Exception as e:
        logger.error(f"Error during rollback: {e}", exc_info=True)
        return {
            "status": "error", 
            "message": f"Rollback failed: {str(e)}",
            "error": str(e)
        } 

def _generate_uninstall_command(self, target: str, is_windows: bool) -> Optional[str]:
    """
    Generate an uninstall command based on the target and platform.
    
    Args:
        target: The target package/application to uninstall
        is_windows: Boolean indicating if running on Windows
        
    Returns:
        str: Uninstall command or None if no suitable command can be generated
    """
    if is_windows:
        # Check if it's a package ID (e.g. ProductCode)
        if re.match(r'^{[A-F0-9-]+}$', target, re.IGNORECASE):
            return f'try {{ Start-Process -Wait -NoNewWindow -FilePath "msiexec.exe" -ArgumentList "/x {target} /quiet" }} catch {{ Log-Error "Failed to uninstall {target}: $_" }}'
        
        # Check for common installer types
        target_lower = target.lower()
        if target_lower.endswith(('.msi', '.exe', '.appx', '.msix')):
            if target_lower.endswith('.msi'):
                return f'try {{ Start-Process -Wait -NoNewWindow -FilePath "msiexec.exe" -ArgumentList "/x {target} /quiet" }} catch {{ Log-Error "Failed to uninstall {target}: $_" }}'
            elif target_lower.endswith(('.appx', '.msix')):
                return f'try {{ Get-AppxPackage *{target}* | Remove-AppxPackage }} catch {{ Log-Error "Failed to uninstall {target}: $_" }}'
            else:
                return f'try {{ Start-Process -Wait -NoNewWindow -FilePath "{target}" -ArgumentList "/uninstall /quiet" }} catch {{ Log-Error "Failed to uninstall {target}: $_" }}'
        
        # Try multiple package managers
        return f"""
try {{
    if (Get-Command choco -ErrorAction SilentlyContinue) {{
        choco uninstall {target} -y
    }} elseif (Get-Command winget -ErrorAction SilentlyContinue) {{
        winget uninstall {target} --silent
    }} else {{
        $app = Get-WmiObject -Class Win32_Product | Where-Object {{ $_.Name -like "*{target}*" }}
        if ($app) {{
            $app.Uninstall()
        }} else {{
            Log-Error "No package manager or installation found for {target}"
        }}
    }}
}} catch {{
    Log-Error "Failed to uninstall {target}: $_"
}}"""
    else:
        # Linux uninstall with multiple package managers and snap support
        return f"""
if command -v snap >/dev/null 2>&1 && snap list | grep -q "^{target} "; then
    snap remove {target} || log_error "Failed to uninstall {target} with snap"
elif command -v apt-get >/dev/null 2>&1; then
    apt-get remove -y {target} || log_error "Failed to uninstall {target} with apt-get"
elif command -v yum >/dev/null 2>&1; then
    yum remove -y {target} || log_error "Failed to uninstall {target} with yum"
elif command -v dnf >/dev/null 2>&1; then
    dnf remove -y {target} || log_error "Failed to uninstall {target} with dnf"
elif command -v zypper >/dev/null 2>&1; then
    zypper remove -y {target} || log_error "Failed to uninstall {target} with zypper"
elif command -v pacman >/dev/null 2>&1; then
    pacman -R --noconfirm {target} || log_error "Failed to uninstall {target} with pacman"
else
    log_error "No package manager found to uninstall {target}"
fi
""" 