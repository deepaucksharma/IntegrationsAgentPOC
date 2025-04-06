"""
Recovery Manager for handling rollback of failed workflows.
"""
import asyncio
import logging
import os
import tempfile
import re
import json
import platform
from enum import Enum
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from ..core.state import WorkflowState, Change, WorkflowStage
from ..error.exceptions import RecoveryError

logger = logging.getLogger(__name__)

class RecoveryStrategy(str, Enum):
    """Enum for recovery strategies."""
    FULL_ROLLBACK = "full_rollback"
    STAGED_ROLLBACK = "staged_rollback"
    INDIVIDUAL_ACTIONS = "individual_actions"
    SKIP_VERIFICATION = "skip_verification"
    BEST_EFFORT = "best_effort"

class RecoveryManager:
    """
    Enhanced recovery manager with robust rollback capabilities and multiple strategies.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration."""
        self.config = config
        self.isolation_method = config.get("isolation_method", "direct")
        self.use_recovery = config.get("use_recovery", True)
        self.max_rollback_attempts = config.get("max_rollback_attempts", 3)
        self.backup_dir = self._ensure_backup_dir(config.get("backup_dir", "./backup"))
        self.recovery_timeout = config.get("recovery_timeout", 600)  # 10 minutes
        self.verify_rollback = config.get("verify_rollback", True)
    
    def _ensure_backup_dir(self, backup_dir_path: str) -> Path:
        """Ensure the backup directory exists."""
        backup_dir = Path(backup_dir_path)
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            return backup_dir
        except Exception as e:
            logger.warning(f"Could not create backup directory: {e}")
            # Fall back to temp directory
            return Path(tempfile.gettempdir()) / "workflow_recovery"
            
    async def recover(self, state: WorkflowState) -> WorkflowState:
        """
        Recover from a failed workflow by rolling back changes with enhanced robustness.
        Uses a multi-strategy approach to maximize the chances of successful recovery.
        
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
            return state.add_message("Nothing to rollback").mark_reverted()
            
        # Start recovery process
        logger.info(f"Starting recovery for workflow: {state.execution_id}, action: {state.action}, target: {state.target_name}")
        
        # Mark state as reverting
        state = state.mark_reverting()
        state = state.set_stage(WorkflowStage.ROLLBACK)
        
        # Create rollback plan
        state = state.add_message("Creating rollback plan...")
        rollback_plan = await self._create_rollback_plan(state)
        
        if not rollback_plan:
            logger.warning("Could not create rollback plan")
            return state.add_warning("Recovery failed - could not create rollback plan")
            
        # Store plan in state
        state = state.evolve(
            recovery_strategy=RecoveryStrategy.FULL_ROLLBACK,
            checkpoints=dict(state.checkpoints, **{"rollback_plan": rollback_plan})
        )
        
        # Try different recovery strategies in order
        strategies = [
            self._try_full_rollback,
            self._try_staged_rollback,
            self._try_individual_rollback
        ]
        
        for strategy_fn in strategies:
            try:
                # Mark the current recovery attempt in the state
                state = state.add_message(f"Attempting recovery with {strategy_fn.__name__}")
                
                # Attempt recovery with this strategy
                recovery_result = await strategy_fn(state)
                
                # If successful (no error), return the result
                if not recovery_result.has_error:
                    logger.info(f"Recovery successful using {strategy_fn.__name__}")
                    return recovery_result.mark_reverted()
                
                # Otherwise, log the failure and try next strategy
                logger.warning(f"Recovery using {strategy_fn.__name__} failed: {recovery_result.error}")
                state = state.add_warning(f"Recovery attempt with {strategy_fn.__name__} failed: {recovery_result.error}")
                
            except Exception as e:
                logger.error(f"Error during {strategy_fn.__name__}: {e}", exc_info=True)
                state = state.add_warning(f"Error during {strategy_fn.__name__}: {str(e)}")
        
        # All strategies failed
        logger.error("All recovery strategies failed")
        return state.add_warning("Recovery failed - all strategies failed").mark_partially_reverted()
        
    async def _try_full_rollback(self, state: WorkflowState) -> WorkflowState:
        """Try full rollback using a comprehensive rollback script."""
        logger.info("Attempting full rollback")
        
        try:
            # Generate comprehensive rollback script
            rollback_script = await self._generate_rollback_script(state)
            
            if not rollback_script:
                return state.add_warning("Full rollback skipped - no rollback script generated")
                
            # Save script for reference
            state = state.set_rollback_script(rollback_script)
            
            # Execute rollback script with enhanced monitoring
            result_state = await self._execute_rollback_script(state, rollback_script)
            
            # If successful, verify the rollback
            if not result_state.has_error and self.verify_rollback:
                verified = await self._verify_rollback(result_state)
                if not verified:
                    return result_state.add_warning("Rollback verification failed")
            
            return result_state
                
        except Exception as e:
            logger.error(f"Error during full rollback: {e}", exc_info=True)
            return state.add_error(f"Full rollback failed: {str(e)}")
            
    async def _try_staged_rollback(self, state: WorkflowState) -> WorkflowState:
        """Try staged rollback, breaking down changes into smaller groups."""
        logger.info("Attempting staged rollback")
        
        try:
            # Group changes by type for more controlled rollback
            change_groups = self._group_changes_by_type(state.changes)
            
            # Define execution order based on dependency considerations
            execution_order = [
                "service",  # Stop services first
                "process",  # Stop processes
                "file",     # Remove/restore files
                "directory", # Remove directories
                "config",   # Revert configuration
                "package",  # Uninstall packages
                "user",     # Remove users
                "group",    # Remove groups
                "other"     # Other changes
            ]
            
            # Original state for reference
            current_state = state
            
            # Process each group in order
            for group_type in execution_order:
                if group_type in change_groups:
                    logger.info(f"Processing {group_type} rollback group")
                    
                    # Generate script for this group only
                    group_script = self._generate_group_rollback_script(
                        current_state, 
                        change_groups[group_type]
                    )
                    
                    if group_script:
                        # Execute this group's rollback
                        current_state = await self._execute_rollback_script(
                            current_state,
                            group_script
                        )
                        
                        # Stop if a critical error occurs
                        if current_state.has_error:
                            logger.error(f"Staged rollback failed at {group_type} group: {current_state.error}")
                            return current_state
            
            # Verification after all stages
            if self.verify_rollback:
                verified = await self._verify_rollback(current_state)
                if not verified:
                    return current_state.add_warning("Staged rollback verification failed")
            
            return current_state
            
        except Exception as e:
            logger.error(f"Error during staged rollback: {e}", exc_info=True)
            return state.add_error(f"Staged rollback failed: {str(e)}")
            
    async def _execute_single_change_rollback(self, state: WorkflowState, script_content: str, change: Change) -> WorkflowState:
        """Execute rollback for a single change and track the result."""
        # Create a temporary script file for just this change
        with tempfile.NamedTemporaryFile(
            suffix=self._get_script_extension(state),
            delete=False,
            mode='w+'
        ) as script_file:
            script_path = script_file.name
            script_file.write(script_content)
            
        try:
            # Make script executable on Unix-like systems
            if os.name != 'nt':
                os.chmod(script_path, 0o755)
                
            # Execute the script
            cmd = self._get_execution_command(script_path, state)
            
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.get("execution_timeout", 60)  # Shorter timeout for individual changes
                )
            except asyncio.TimeoutError:
                process.terminate()
                return state.add_error(f"Timed out rolling back change {change.type} - {change.target}")
            
            # Process results
            stdout_str = stdout.decode() if stdout else ""
            stderr_str = stderr.decode() if stderr else ""
            
            if process.returncode != 0:
                return state.add_error(f"Failed to roll back {change.type} - {change.target}: {stderr_str}")
                
            # Mark the change as rolled back
            updated_changes = []
            for c in state.changes:
                if c.change_id == change.change_id:
                    # Mark this change as having had rollback attempted
                    updated_changes.append(c.mark_rollback_attempted(True))
                else:
                    updated_changes.append(c)
                    
            # Update the state with the rollback result
            return state.evolve(changes=updated_changes)
            
        except Exception as e:
            return state.add_error(f"Error rolling back {change.type} - {change.target}: {str(e)}")
            
        finally:
            # Clean up temporary script file
            try:
                os.unlink(script_path)
            except Exception:
                pass

    async def _verify_rollback(self, state: WorkflowState) -> bool:
        """Verify that rollback was successful by checking key aspects of the system."""
        logger.info("Verifying rollback success")
        
        # Check status markers in output, if available
        if state.output and state.output.stdout:
            # Look for the special rollback status marker
            match = re.search(r"ROLLBACK_STATUS_MARKER:(\w+)", state.output.stdout)
            if match:
                status = match.group(1)
                if status == "ROLLBACK_SUCCESS":
                    logger.info("Rollback reported success")
                    return True
                else:
                    logger.warning(f"Rollback reported non-success status: {status}")
                    return False
                    
        # If no marker, perform basic verification
        try:
            verification_results = []
            
            # Go through changes and verify they were reverted
            for change in state.changes:
                if not change.revertible:
                    continue
                    
                # Check based on change type
                if change.type == 'file_created':
                    # File should no longer exist
                    file_exists = Path(change.target).exists()
                    if file_exists:
                        logger.warning(f"File still exists after rollback: {change.target}")
                        verification_results.append(False)
                    else:
                        verification_results.append(True)
                        
                elif change.type == 'directory_created':
                    # Directory should no longer exist
                    dir_exists = Path(change.target).exists()
                    if dir_exists:
                        logger.warning(f"Directory still exists after rollback: {change.target}")
                        verification_results.append(False)
                    else:
                        verification_results.append(True)
                        
                elif change.type.startswith('service_'):
                    # Best-effort service verification - complex to check on all platforms
                    pass
                    
            # Consider successful if all checks passed or if no checks were performed
            if verification_results and all(verification_results):
                logger.info("Rollback verification completed successfully")
                return True
            elif not verification_results:
                logger.info("No verifiable changes to check, assuming success")
                return True
            else:
                logger.warning("Rollback verification failed for some changes")
                return False
                
        except Exception as e:
            logger.error(f"Error during rollback verification: {e}")
            return False

    async def _try_individual_rollback(self, state: WorkflowState) -> WorkflowState:
        """Try rolling back changes one by one, the most careful but slowest approach."""
        logger.info("Attempting individual rollback actions")
        
        # Original state for reference
        current_state = state
        successful_changes = []
        failed_changes = []
        
        # Process each change individually in reverse order (most recent first)
        for change in reversed(state.changes):
            if not change.revertible:
                logger.info(f"Skipping non-revertible change: {change.type} - {change.target}")
                continue
                
            try:
                # Generate script for just this change
                single_script = self._generate_single_change_rollback(current_state, change)
                
                if not single_script:
                    logger.warning(f"Could not generate rollback for change: {change.type} - {change.target}")
                    failed_changes.append(change)
                    continue
                    
                # Execute just this change
                logger.info(f"Rolling back change: {change.type} - {change.target}")
                result = await self._execute_single_change_rollback(current_state, single_script, change)
                
                if result.has_error:
                    logger.warning(f"Failed to roll back change: {change.type} - {change.target}, error: {result.error}")
                    failed_changes.append(change)
                else:
                    logger.info(f"Successfully rolled back change: {change.type} - {change.target}")
                    successful_changes.append(change)
                    # Update state to include this successful change
                    current_state = result
                    
            except Exception as e:
                logger.error(f"Error rolling back change {change.type} - {change.target}: {e}")
                failed_changes.append(change)
                
        # Summarize results
        if not successful_changes:
            return state.add_error("Individual rollback failed - no changes were successfully reverted")
            
        # Create a summary message
        summary = f"Individual rollback: {len(successful_changes)} changes reverted successfully, {len(failed_changes)} failed"
        logger.info(summary)
        
        # Update final state
        if failed_changes:
            return current_state.add_warning(summary).mark_partially_reverted()
        else:
            return current_state.add_message(summary).mark_reverted()
            
    async def _execute_rollback_script(self, state: WorkflowState, script_content: str) -> WorkflowState:
        """Execute a rollback script with enhanced monitoring and error handling."""
        # Generate a unique name for this rollback script for logging
        script_id = f"rollback-{state.execution_id[:8]}"
        logger.info(f"Executing rollback script {script_id}")
        
        # Create a temporary file for the rollback script
        with tempfile.NamedTemporaryFile(
            suffix=self._get_script_extension(state),
            delete=False,
            mode='w+'
        ) as script_file:
            script_path = script_file.name
            script_file.write(script_content)
            
        try:
            # Make script executable on Unix-like systems
            if os.name != 'nt':
                os.chmod(script_path, 0o755)
                
            # Also save a copy to backup directory for reference
            backup_script_path = self.backup_dir / f"{script_id}{self._get_script_extension(state)}"
            try:
                # Ensure backup directory exists
                self.backup_dir.mkdir(parents=True, exist_ok=True)
                # Copy the script
                with open(backup_script_path, 'w') as f:
                    f.write(script_content)
            except Exception as e:
                logger.warning(f"Failed to save backup of rollback script: {e}")
                
            # Execute the script with appropriate command
            cmd = self._get_execution_command(script_path, state)
            logger.debug(f"Executing command: {cmd}")
            
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.recovery_timeout
                )
            except asyncio.TimeoutError:
                # Kill the process if it times out
                try:
                    process.terminate()
                    logger.error(f"Rollback script {script_id} execution timed out")
                    return state.add_error(f"Rollback script execution timed out after {self.recovery_timeout} seconds")
                except:
                    pass
            
            # Process results
            stdout_str = stdout.decode() if stdout else ""
            stderr_str = stderr.decode() if stderr else ""
            
            # Log outputs for debugging
            if stdout_str:
                logger.debug(f"Rollback script stdout: {stdout_str[:1000]}")
            if stderr_str:
                logger.debug(f"Rollback script stderr: {stderr_str[:1000]}")
                
            # Check exit code
            if process.returncode != 0:
                error_msg = f"Rollback script {script_id} failed with exit code {process.returncode}: {stderr_str}"
                logger.error(error_msg)
                return state.add_error(error_msg)
                
            # Create output data for the state
            from ..core.state import OutputData
            output = OutputData(
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=process.returncode,
                duration=0.0,  # We don't track duration for rollback
            )
            
            # Update state with execution results
            updated_state = state.set_output(output)
            updated_state = updated_state.add_message(f"Rollback script {script_id} executed successfully")
            
            return updated_state
            
        except Exception as e:
            logger.error(f"Error executing rollback script {script_id}: {e}", exc_info=True)
            return state.add_error(f"Error executing rollback script: {str(e)}")
            
        finally:
            # Clean up temporary script file
            try:
                os.unlink(script_path)
            except Exception as e:
                logger.warning(f"Failed to remove temporary script: {e}")
                
    async def _create_rollback_plan(self, state: WorkflowState) -> List[Dict[str, Any]]:
        """
        Create a detailed rollback plan with precise steps and verification methods.
        
        Args:
            state: The workflow state with changes to revert.
            
        Returns:
            List of rollback steps with details.
        """
        if not state.changes:
            return []
            
        is_windows = state.system_context.get('is_windows', os.name == 'nt')
        
        # Build structured rollback plan
        rollback_plan = []
        
        for change in reversed(state.changes):
            if not isinstance(change, Change) or not change.revertible:
                continue
                
            # Build step with command and verification
            step = {
                "id": str(change.change_id),
                "type": change.type,
                "target": change.target,
                "priority": self._get_rollback_priority(change),
                "verification": self._get_verification_command(change, is_windows),
                "backup_file": change.backup_file,
                "timestamp": change.timestamp.isoformat() if hasattr(change, "timestamp") else None
            }
            
            # Add command to step
            if change.revert_command:
                step["command"] = change.revert_command
            else:
                # Generate command based on type
                cmd = None
                if change.type == 'file_created':
                    cmd = self._get_file_remove_command(change.target, is_windows)
                elif change.type == 'directory_created':
                    cmd = self._get_directory_remove_command(change.target, is_windows)
                elif change.type == 'package_installed':
                    cmd = self._get_package_revert_command(change.target, is_windows)
                elif change.type == 'service_started':
                    cmd = self._get_service_revert_command(change.target, is_windows)
                elif change.type.startswith('service_'):
                    cmd = self._get_service_revert_command(change.target, is_windows)
                elif change.type.startswith('package_'):
                    cmd = self._get_package_revert_command(change.target, is_windows)
                    
                if cmd:
                    step["command"] = cmd
                else:
                    # Skip if we can't generate a command
                    continue
            
            rollback_plan.append(step)
        
        # Sort by priority
        rollback_plan.sort(key=lambda x: x["priority"])
        
        return rollback_plan
        
    def _get_rollback_priority(self, change: Change) -> int:
        """Determine the priority of a rollback action (lower is handled first)."""
        # Handle service operations first 
        if change.type.startswith('service_'):
            return 10
        # Then processes
        elif change.type.startswith('process_'):
            return 20
        # Then files and directories
        elif change.type.startswith('file_') or change.type.startswith('directory_'):
            return 30
        # Then packages
        elif change.type.startswith('package_'):
            return 40
        # Then configurations
        elif change.type.startswith('config_'):
            return 50
        # Then users and groups
        elif change.type.startswith('user_') or change.type.startswith('group_'):
            return 60
        # Generic changes
        else:
            return 100
            
    def _get_verification_command(self, change: Change, is_windows: bool) -> Optional[str]:
        """Generate a verification command to check if the rollback was successful."""
        if change.type == 'file_created':
            if is_windows:
                return f'!(Test-Path -Path "{change.target}")'
            else:
                return f'[ ! -f "{change.target}" ]'
        elif change.type == 'directory_created':
            if is_windows:
                return f'!(Test-Path -Path "{change.target}" -PathType Container)'
            else:
                return f'[ ! -d "{change.target}" ]'
        elif change.type.startswith('service_'):
            if is_windows:
                return f'!(Get-Service -Name "{change.target}" -ErrorAction SilentlyContinue | Where-Object {{ $_.Status -eq "Running" }})'
            else:
                return f'! systemctl is-active --quiet {change.target}'
        elif change.type.startswith('package_'):
            if is_windows:
                return None  # Complex to verify packages on Windows
            else:
                return f'! dpkg -l | grep -q "{change.target}" && ! rpm -q "{change.target}" >/dev/null 2>&1'
        else:
            return None
            
    async def _generate_rollback_script(self, state: WorkflowState) -> Optional[str]:
        """
        Generate a comprehensive rollback script based on recorded changes with enhanced error handling.
        
        Args:
            state: The workflow state with changes to revert.
            
        Returns:
            Script content or None if no reversible changes.
        """
        # First create a detailed rollback plan
        rollback_plan = await self._create_rollback_plan(state)
        
        if not rollback_plan:
            return None
            
        # Generate script from plan
        is_windows = state.system_context.get('is_windows', os.name == 'nt')
        script_header = self._get_enhanced_script_header(is_windows, state)
        
        revert_commands = []
        for step in rollback_plan:
            command = step.get("command")
            if not command:
                continue
                
            # Wrap each command with error handling and logging
            if is_windows:
                revert_commands.append(f'try {{ Log-Message "Rolling back {step["type"]} - {step["target"]}" }}')
                revert_commands.append(f'try {{')
                revert_commands.append(f'    {command}')
                
                # Add verification if available
                if step.get("verification"):
                    revert_commands.append(f'    if ({step["verification"]}) {{')
                    revert_commands.append(f'        Log-Message "Rollback of {step["target"]} verified successfully"')
                    revert_commands.append(f'    }} else {{')
                    revert_commands.append(f'        Log-Warning "Rollback of {step["target"]} could not be verified"')
                    revert_commands.append(f'    }}')
                
                revert_commands.append(f'}} catch {{')
                revert_commands.append(f'    Log-Error "Failed to rollback {step["type"]} - {step["target"]}: $_"')
                revert_commands.append(f'}}')
                revert_commands.append('')
            else:
                revert_commands.append(f'log_message "Rolling back {step["type"]} - {step["target"]}"')
                revert_commands.append(f'(')
                revert_commands.append(f'    {command}')
                
                # Add verification if available
                if step.get("verification"):
                    revert_commands.append(f'    if {step["verification"]}; then')
                    revert_commands.append(f'        log_message "Rollback of {step["target"]} verified successfully"')
                    revert_commands.append(f'    else')
                    revert_commands.append(f'        log_warning "Rollback of {step["target"]} could not be verified"')
                    revert_commands.append(f'    fi')
                
                revert_commands.append(f') || log_error "Failed to rollback {step["type"]} - {step["target"]}: $?"')
                revert_commands.append('')
        
        if not revert_commands:
            return None
            
        script_footer = self._get_enhanced_script_footer(is_windows, state)
        return script_header + "\n".join(revert_commands) + "\n" + script_footer
        
    def _get_enhanced_script_header(self, is_windows: bool, state: WorkflowState) -> str:
        """Get an enhanced script header with comprehensive error handling and logging."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        workflow_id = state.execution_id[:8] if state.execution_id else "unknown"
        
        if is_windows:
            return f"""# Enhanced Automatic Rollback Script 
# Generated: {timestamp}
# Workflow ID: {workflow_id}
# Action: {state.action}
# Target: {state.target_name}

$ErrorActionPreference = "Stop"
$DebugPreference = "Continue"
$RollbackSuccess = $true
$RollbackStartTime = Get-Date

function Log-Message {{
    param([string]$Message)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host "[$timestamp] $Message"
    Add-Content -Path "$env:TEMP\\rollback_{workflow_id}.log" -Value "[$timestamp] $Message"
}}

function Log-Warning {{
    param([string]$Message)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host "[$timestamp] WARNING: $Message" -ForegroundColor Yellow
    Add-Content -Path "$env:TEMP\\rollback_{workflow_id}.log" -Value "[$timestamp] WARNING: $Message"
}}

function Log-Error {{
    param([string]$Message)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host "[$timestamp] ERROR: $Message" -ForegroundColor Red
    Add-Content -Path "$env:TEMP\\rollback_{workflow_id}.log" -Value "[$timestamp] ERROR: $Message"
    $global:RollbackSuccess = $false
}}

function Log-Debug {{
    param([string]$Message)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Debug "[$timestamp] DEBUG: $Message"
    Add-Content -Path "$env:TEMP\\rollback_{workflow_id}.log" -Value "[$timestamp] DEBUG: $Message"
}}

function Exit-WithSummary {{
    $duration = (Get-Date) - $RollbackStartTime
    Log-Message "Rollback operation completed in $($duration.TotalSeconds) seconds"
    
    if ($global:RollbackSuccess) {{
        Log-Message "ROLLBACK STATUS: SUCCESS - All operations completed"
        exit 0
    }} else {{
        Log-Message "ROLLBACK STATUS: PARTIAL - Some operations failed (see log)"
        exit 1
    }}
}}

# Ensure we clean up even on unexpected exit
trap {{
    Log-Error "Unexpected error: $_"
    Exit-WithSummary
    exit 1
}}

Log-Message "Starting rollback operations for {state.target_name}..."
Log-Message "Total changes to rollback: {len(state.changes)}"
Log-Message ""

"""
        else:
            return f"""#!/bin/bash
# Enhanced Automatic Rollback Script
# Generated: {timestamp}
# Workflow ID: {workflow_id}
# Action: {state.action}
# Target: {state.target_name}

set -e
ROLLBACK_SUCCESS=true
ROLLBACK_START_TIME=$(date +%s)
LOGFILE="/tmp/rollback_{workflow_id}.log"

log_message() {{
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $1"
    echo "[$timestamp] $1" >> "$LOGFILE"
}}

log_warning() {{
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] WARNING: $1" >&2
    echo "[$timestamp] WARNING: $1" >> "$LOGFILE"
}}

log_error() {{
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] ERROR: $1" >&2
    echo "[$timestamp] ERROR: $1" >> "$LOGFILE"
    ROLLBACK_SUCCESS=false
}}

log_debug() {{
    if [ "$DEBUG" = "true" ]; then
        timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        echo "[$timestamp] DEBUG: $1" >&2
        echo "[$timestamp] DEBUG: $1" >> "$LOGFILE"
    fi
}}

exit_with_summary() {{
    ROLLBACK_END_TIME=$(date +%s)
    DURATION=$((ROLLBACK_END_TIME - ROLLBACK_START_TIME))
    log_message "Rollback operation completed in $DURATION seconds"
    
    if [ "$ROLLBACK_SUCCESS" = "true" ]; then
        log_message "ROLLBACK STATUS: SUCCESS - All operations completed"
        exit 0
    else
        log_message "ROLLBACK STATUS: PARTIAL - Some operations failed (see log)"
        exit 1
    fi
}}

# Trap for unexpected errors
trap 'log_error "Unexpected error: $?"; exit_with_summary' ERR
trap 'exit_with_summary' EXIT

log_message "Starting rollback operations for {state.target_name}..."
log_message "Total changes to rollback: {len(state.changes)}"
log_message ""

"""
    
    def _get_enhanced_script_footer(self, is_windows: bool, state: WorkflowState) -> str:
        """Get an enhanced script footer with comprehensive reporting."""
        if is_windows:
            return """
# Verify overall rollback status
if ($global:RollbackSuccess) {
    Log-Message "Rollback completed successfully!"
} else {
    Log-Warning "Rollback completed with some issues. Check the logs for details."
}

# Record final status for workflow agent to process
$status = if ($global:RollbackSuccess) { "ROLLBACK_SUCCESS" } else { "ROLLBACK_PARTIAL" }
Write-Output "ROLLBACK_STATUS_MARKER:$status"

Exit-WithSummary
"""
        else:
            return """
# Verify overall rollback status
if [ "$ROLLBACK_SUCCESS" = "true" ]; then
    log_message "Rollback completed successfully!"
else
    log_warning "Rollback completed with some issues. Check the logs for details."
fi

# Record final status for workflow agent to process
status=$([ "$ROLLBACK_SUCCESS" = "true" ] && echo "ROLLBACK_SUCCESS" || echo "ROLLBACK_PARTIAL")
echo "ROLLBACK_STATUS_MARKER:$status"

exit_with_summary
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
