import os
import uuid
import tempfile
import subprocess
import time
import signal
import psutil
import logging
import shutil
import asyncio
import json
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from ..core.state import WorkflowState, OutputData, ExecutionMetrics, Change
from ..config.configuration import ensure_workflow_config
from ..storage import HistoryManager
from .isolation import get_isolation_method

logger = logging.getLogger(__name__)

class ScriptExecutor:
    """Executes scripts with different isolation methods and captures metrics."""
    
    def __init__(self, history_manager: Optional[HistoryManager] = None):
        """
        Initialize the script executor.
        
        Args:
            history_manager: Optional history manager for recording execution history
        """
        self.history_manager = history_manager or HistoryManager()
    
    async def run_script(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run the generated script in a controlled environment.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with execution results
        """
        if not state.script:
            logger.error("No script to run")
            return {"error": "No script to run."}
        
        workflow_config = ensure_workflow_config(config)
        temp_dir = tempfile.mkdtemp(prefix='workflow-')
        script_id = str(uuid.uuid4())
        script_path = os.path.join(temp_dir, f"script-{script_id}.sh")
        
        error_message = None
        process = None
        transaction_id = state.transaction_id or str(uuid.uuid4())
        
        try:
            # Write script to temp file
            with open(script_path, 'w') as f:
                f.write(state.script)
            
            os.chmod(script_path, 0o755)
            logger.info(f"Prepared script at {script_path}")
            
            # Capture initial metrics
            start_time = time.time()
            try:
                start_cpu = psutil.cpu_percent(interval=0.1)
                start_memory = psutil.virtual_memory().used
                try:
                    start_io = psutil.disk_io_counters()
                    start_network = psutil.net_io_counters()
                except:
                    start_io = None
                    start_network = None
            except Exception as e:
                logger.warning(f"Failed to get initial system metrics: {e}")
                start_cpu = 0
                start_memory = 0
                start_io = None
                start_network = None
            
            logger.info(f"Starting script execution: {script_path}")
            
            # Determine isolation method
            isolation_method = state.isolation_method or workflow_config.isolation_method
            use_isolation = workflow_config.use_isolation
            
            if use_isolation:
                isolation_executor = get_isolation_method(isolation_method)
                if isolation_executor:
                    result = await isolation_executor(
                        script_path, 
                        workflow_config.execution_timeout,
                        workflow_config.least_privilege_execution
                    )
                else:
                    logger.warning(f"Unknown isolation method: {isolation_method}, falling back to direct execution")
                    from .isolation.direct import run_script_direct
                    result = await run_script_direct(script_path, workflow_config.execution_timeout)
            else:
                logger.info("Running script directly (no isolation)")
                from .isolation.direct import run_script_direct
                result = await run_script_direct(script_path, workflow_config.execution_timeout)
            
            success, stdout_str, stderr_str, exit_code, error_message = result
            
            # Capture final metrics
            end_time = time.time()
            try:
                end_cpu = psutil.cpu_percent(interval=0.1)
                end_memory = psutil.virtual_memory().used
                try:
                    end_io = psutil.disk_io_counters()
                    end_network = psutil.net_io_counters()
                except:
                    end_io = None
                    end_network = None
            except Exception as e:
                logger.warning(f"Failed to get final system metrics: {e}")
                end_cpu = 0
                end_memory = 0
                end_io = None
                end_network = None
            
            # Calculate metrics
            execution_time = int((end_time - start_time) * 1000)
            cpu_usage = (start_cpu + end_cpu) / 2
            memory_usage = max(0, end_memory - start_memory)
            
            # Calculate IO and network metrics if available
            io_read = end_io.read_bytes - start_io.read_bytes if end_io and start_io else None
            io_write = end_io.write_bytes - start_io.write_bytes if end_io and start_io else None
            network_tx = end_network.bytes_sent - start_network.bytes_sent if end_network and start_network else None
            network_rx = end_network.bytes_recv - start_network.bytes_recv if end_network and start_network else None
            
            metrics = ExecutionMetrics(
                start_time=start_time,
                end_time=end_time,
                execution_time=execution_time,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                io_read=io_read,
                io_write=io_write,
                network_tx=network_tx,
                network_rx=network_rx
            )
            
            output = OutputData(
                stdout=stdout_str, 
                stderr=stderr_str,
                exit_code=exit_code
            )
            
            # Extract any changes mentioned in output
            changes = state.changes if state.changes else []
            
            if success:
                # Extract changes from the output
                changes = await self._extract_changes_from_output(stdout_str, changes, state)
            
            # If no changes were captured, add a generic one
            if not changes:
                if state.action in ["install", "setup"]:
                    changes.append(Change(
                        type="install",
                        target=state.target_name,
                        details=f"Installed {state.target_name}",
                        revertible=True
                    ))
                elif state.action == "verify":
                    changes.append(Change(
                        type="verify",
                        target=state.target_name,
                        details=f"Verified {state.target_name}",
                        revertible=False
                    ))
                elif state.action in ["remove", "uninstall"]:
                    changes.append(Change(
                        type="remove",
                        target=state.target_name,
                        details=f"Removed {state.target_name}",
                        revertible=False
                    ))
            
            # Save execution history
            try:
                if self.history_manager:
                    execution_id = await self.history_manager.save_execution(
                        target_name=state.target_name,
                        action=state.action,
                        success=success,
                        execution_time=execution_time,
                        error_message=None if success else error_message,
                        system_context=state.system_context,
                        script=state.script,
                        output={"stdout": stdout_str, "stderr": stderr_str, "exit_code": exit_code},
                        parameters=state.parameters,
                        transaction_id=transaction_id,
                        user_id=workflow_config.user_id
                    )
                    logger.info(f"Saved execution record with ID {execution_id}")
                else:
                    execution_id = None
            except Exception as e:
                logger.error(f"Failed to save execution record: {e}")
                execution_id = None
            
            if success:
                logger.info(f"Script executed successfully for {state.action} on {state.target_name}")
                return {
                    "output": output,
                    "status": f"Script executed successfully for {state.action} on {state.target_name}",
                    "changes": changes,
                    "legacy_changes": [change.details for change in changes],
                    "metrics": metrics,
                    "execution_id": execution_id,
                    "transaction_id": transaction_id
                }
            else:
                logger.error(f"Script execution failed: {error_message}")
                return {
                    "error": error_message or "Script execution failed",
                    "output": output,
                    "metrics": metrics,
                    "execution_id": execution_id,
                    "transaction_id": transaction_id,
                    "changes": changes,
                    "legacy_changes": [change.details for change in changes]
                }
        except Exception as err:
            error_message = str(err)
            logger.exception(f"Script execution failed with exception: {error_message}")
            end_time = time.time()
            execution_time = int((end_time - (state.metrics.start_time if state.metrics and state.metrics.start_time else end_time)) * 1000)
            
            try:
                if self.history_manager:
                    execution_id = await self.history_manager.save_execution(
                        target_name=state.target_name,
                        action=state.action,
                        success=False,
                        execution_time=execution_time,
                        error_message=error_message,
                        system_context=state.system_context,
                        script=state.script,
                        transaction_id=transaction_id,
                        user_id=workflow_config.user_id
                    )
                else:
                    execution_id = None
            except Exception as e:
                logger.error(f"Failed to save execution record for error: {e}")
                execution_id = None
            
            return {
                "error": f"Script execution failed: {error_message}",
                "output": OutputData(stdout="", stderr=error_message, exit_code=1),
                "metrics": ExecutionMetrics(
                    start_time=state.metrics.start_time if state.metrics and state.metrics.start_time else 0,
                    end_time=end_time,
                    execution_time=execution_time,
                    cpu_usage=None,
                    memory_usage=None
                ),
                "execution_id": execution_id,
                "transaction_id": transaction_id,
                "changes": [Change(
                    type="attempt",
                    target=state.target_name,
                    details=f"Attempted {state.action} on {state.target_name}",
                    revertible=False
                )],
                "legacy_changes": [f"Attempted {state.action} on {state.target_name}"]
            }
        finally:
            if process and process.poll() is None:
                try:
                    process.kill()
                    logger.info("Killed hanging process")
                except:
                    pass
            try:
                if os.path.exists(script_path):
                    os.unlink(script_path)
                    logger.debug(f"Removed temporary script file: {script_path}")
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
                    logger.debug(f"Removed temporary directory: {temp_dir}")
            except Exception as cleanup_err:
                logger.error(f"Cleanup error: {cleanup_err}")
    
    async def _extract_changes_from_output(
        self,
        stdout: str,
        existing_changes: List[Change],
        state: WorkflowState
    ) -> List[Change]:
        """
        Extract changes from script output.
        
        Args:
            stdout: Script standard output
            existing_changes: Existing changes list
            state: Current workflow state
            
        Returns:
            Updated changes list
        """
        changes = existing_changes.copy()
        
        for line in stdout.lower().split('\n'):
            if "installed package" in line or "installing package" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part in ["package:", "package"]:
                        if i+1 < len(parts):
                            pkg_name = parts[i+1]
                            changes.append(Change(
                                type="install",
                                target=f"package:{pkg_name}",
                                details=f"Installed package: {pkg_name}",
                                revertible=True,
                                revert_command=f"apt-get remove -y {pkg_name} || yum remove -y {pkg_name}"
                            ))
            
            if "creating file" in line or "created file" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part in ["file:", "file"]:
                        if i+1 < len(parts):
                            file_path = parts[i+1]
                            changes.append(Change(
                                type="create",
                                target=f"file:{file_path}",
                                details=f"Created file: {file_path}",
                                revertible=True,
                                revert_command=f"rm -f {file_path}"
                            ))
            
            if "restarting" in line and any(svc in line for svc in ["service", "apache", "nginx", "systemctl"]):
                for svc in ["apache2", "httpd", "nginx", "mysql", "postgresql", "php-fpm", "newrelic"]:
                    if svc in line:
                        changes.append(Change(
                            type="configure",
                            target=f"service:{svc}",
                            details=f"Configured service: {svc}",
                            revertible=True,
                            revert_command=f"systemctl stop {svc}"
                        ))
        
        return changes