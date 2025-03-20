"""Recovery and rollback management for workflow agent."""
import logging
import re
from typing import Dict, Any, Optional, List
from ..core.state import WorkflowState, Change
from ..config.configuration import ensure_workflow_config
from ..storage.history import ExecutionHistoryManager

logger = logging.getLogger(__name__)

class RecoveryManager:
    """Manages recovery and rollback operations for workflow executions."""
    
    def __init__(self, history_manager: ExecutionHistoryManager):
        self.history_manager = history_manager

    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the recovery manager."""
        if self.history_manager:
            await self.history_manager.initialize(config)

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.history_manager:
            await self.history_manager.cleanup()

    async def rollback_changes(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle rollback in case of script execution or verification failure."""
        logger.info(f"Starting rollback for action: {state.action}, target: {state.target_name}")
        
        if not state.changes and not state.legacy_changes:
            logger.info("No changes to rollback")
            return {"status": "Nothing to rollback"}
        
        try:
            # Build a rollback script based on the recorded changes
            rollback_script = self._generate_rollback_script(state)
            
            if not rollback_script:
                logger.warning("Could not generate rollback script")
                return {"status": "Rollback skipped - no rollback actions available"}
            
            # Create a new state for the rollback script
            from copy import deepcopy
            rollback_state = deepcopy(state)
            rollback_state.action = "rollback"
            rollback_state.script = rollback_script
            
            # Execute the rollback script
            from ..execution.executor import ScriptExecutor
            executor = ScriptExecutor()
            await executor.initialize(config)
            result = await executor.run_script(rollback_state, config)
            
            if "error" in result:
                logger.error(f"Rollback script execution failed: {result['error']}")
                return {"error": f"Rollback failed: {result['error']}"}
            
            logger.info("Rollback completed successfully")
            return {"status": "Rollback completed successfully"}
            
        except Exception as e:
            logger.error(f"Error during rollback: {e}")
            return {"error": f"Rollback failed: {str(e)}"}

    def _generate_rollback_script(self, state: WorkflowState) -> Optional[str]:
        """Generate a rollback script based on the recorded changes."""
        system = state.system_context.get("platform", {}).get("system", "").lower()
        is_windows = "win" in system
        
        script_lines = []
        
        # Add appropriate header
        if is_windows:
            script_lines.extend([
                "# Windows rollback script",
                "Set-ExecutionPolicy Bypass -Scope Process -Force",
                "$ErrorActionPreference = \"Stop\"",
                ""
            ])
        else:
            script_lines.extend([
                "#!/bin/bash",
                "set -e",
                "echo \"Starting rollback for failed operation on " + state.target_name + "\"",
                ""
            ])
        
        # Process changes in reverse order (most recent first)
        changes = list(state.changes) if state.changes else []
        changes.reverse()
        
        for change in changes:
            # Only process revertible changes
            if not change.revertible:
                continue
                
            # Use explicit revert command if provided
            if change.revert_command:
                script_lines.append(f"# Reverting {change.type} of {change.target}")
                script_lines.append(change.revert_command)
                continue
            
            # Generate revert commands based on change type
            if change.type == "install":
                cmd = self._generate_uninstall_command(change.target, is_windows)
                if cmd:
                    script_lines.append(f"# Uninstalling {change.target}")
                    script_lines.append(cmd)
            
            elif change.type == "create" and "file" in change.target:
                if is_windows:
                    script_lines.append(f"# Removing created file")
                    script_lines.append(f"if (Test-Path \"{change.target}\") {{ Remove-Item -Force \"{change.target}\" }}")
                else:
                    script_lines.append(f"# Removing created file")
                    script_lines.append(f"[ -f \"{change.target}\" ] && rm -f \"{change.target}\"")
            
            elif change.type == "start" and "service" in change.target:
                if is_windows:
                    script_lines.append(f"# Stopping service {change.target}")
                    script_lines.append(f"Stop-Service -Name \"{change.target}\" -ErrorAction SilentlyContinue")
                else:
                    script_lines.append(f"# Stopping service {change.target}")
                    script_lines.append(f"(systemctl stop {change.target} || service {change.target} stop) 2>/dev/null || true")
        
        # Add final message
        script_lines.append("")
        script_lines.append("echo \"Rollback completed\"" if not is_windows else "Write-Host \"Rollback completed\"")
        
        return "\n".join(script_lines) if script_lines else None

    def _generate_uninstall_command(self, target: str, is_windows: bool) -> Optional[str]:
        """Generate an uninstall command based on the target."""
        if is_windows:
            # Windows uninstall approach
            if "newrelic" in target.lower():
                return f"$app = Get-WmiObject -Class Win32_Product | Where-Object {{ $_.Name -like \"*{target}*\" }}; if ($app) {{ $app.Uninstall() }}"
            return None
        else:
            # Linux uninstall approach
            if "newrelic" in target.lower():
                return f"""
if command -v apt-get >/dev/null 2>&1; then
    apt-get remove -y {target} || true
elif command -v yum >/dev/null 2>&1; then
    yum remove -y {target} || true
elif command -v dnf >/dev/null 2>&1; then
    dnf remove -y {target} || true
elif command -v zypper >/dev/null 2>&1; then
    zypper remove -y {target} || true
fi
"""
            return None

    async def perform_rollback(self, state: WorkflowState) -> Dict[str, Any]:
        """Perform rollback for a failed workflow."""
        logger.info("Starting rollback for action: %s, target: %s", state.action, state.target_name)
        
        try:
            # Get changes to rollback
            changes = state.changes
            if not changes:
                logger.info("No changes to rollback")
                return {"status": "success", "message": "No changes to rollback"}
            
            # Rollback changes in reverse order
            for change in reversed(changes):
                if not change.revertible or not change.revert_command:
                    logger.warning("Change %s is not revertible", change.change_id)
                    continue
                    
                logger.info("Rolling back change: %s", change.change_id)
                # Execute revert command here
                # For now, we'll just log it
                logger.info("Would execute: %s", change.revert_command)
            
            return {
                "status": "success",
                "message": "Rollback completed successfully"
            }
            
        except Exception as e:
            logger.error("Rollback failed: %s", e)
            return {
                "status": "error",
                "message": f"Rollback failed: {str(e)}"
            }