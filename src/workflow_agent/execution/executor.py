"""
Script execution with resource management.
"""
import os
import uuid
import tempfile
import time
import asyncio
import logging
import shutil
import sys
from typing import Dict, Any, Optional, Tuple

from ..core.state import WorkflowState, OutputData, ExecutionMetrics, Change
from ..config.configuration import ensure_workflow_config
from .isolation import run_script_direct, run_script_docker

logger = logging.getLogger(__name__)

class ResourceLimiter:
    """Manages resource limits for script execution."""
    def __init__(self, max_concurrent: int = 5, max_memory_mb: int = 1024):
        self.max_concurrent = max_concurrent
        self.max_memory_mb = max_memory_mb
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_executions = {}
        self._lock = asyncio.Lock()
    
    async def acquire(self, execution_id: str) -> None:
        """Acquire execution resources with execution ID tracking."""
        await self.semaphore.acquire()
        async with self._lock:
            self.active_executions[execution_id] = {"start_time": time.time()}
    
    def release(self, execution_id: str) -> None:
        """Release resources for execution."""
        try:
            self.semaphore.release()
        except ValueError:
            pass
        if execution_id in self.active_executions:
            self.active_executions.pop(execution_id, None)

async def run_script_direct_windows(script_path: str, timeout: int) -> Tuple[bool, str, str, int, Optional[str]]:
    """Execute a PowerShell script directly on Windows."""
    try:
        # Create a process to run PowerShell with the script
        process = await asyncio.create_subprocess_exec(
            'powershell.exe',
            '-NoProfile',
            '-NonInteractive',
            '-ExecutionPolicy', 'Bypass',
            '-File', script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout/1000)
            stdout_str = stdout.decode('utf-8', errors='ignore') if stdout else ''
            stderr_str = stderr.decode('utf-8', errors='ignore') if stderr else ''
            success = process.returncode == 0
            error_message = None if success else f"Script failed with exit code {process.returncode}"
            return success, stdout_str, stderr_str, process.returncode, error_message
        except asyncio.TimeoutError:
            try:
                process.kill()
            except:
                pass
            return False, "", "", -1, "Script execution timed out"
    except Exception as e:
        return False, "", str(e), -1, f"Script execution failed: {str(e)}"

class ScriptExecutor:
    """Execute scripts with isolation and resource management."""
    
    def __init__(
        self, 
        history_manager=None, 
        timeout: int = 300,
        max_concurrent: int = 10,
        resource_limiter=None
    ):
        self.history_manager = history_manager
        self.timeout = timeout
        self.resource_limiter = resource_limiter or ResourceLimiter(max_concurrent=max_concurrent)
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the executor."""
        pass
    
    async def cleanup(self) -> None:
        """Clean up executor resources."""
        pass
    
    async def run_script(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a script with optional isolation."""
        if not state.script:
            return {"error": "No script to run."}
        
        workflow_config = ensure_workflow_config(config or {})
        temp_dir = tempfile.mkdtemp(prefix='workflow-')
        script_id = str(uuid.uuid4())
        
        # Use appropriate file extension based on platform
        is_windows = sys.platform.lower() == "win32"
        script_ext = ".ps1" if is_windows else ".sh"
        script_path = os.path.join(temp_dir, f"script-{script_id}{script_ext}")
        
        transaction_id = state.transaction_id or str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        
        try:
            await self.resource_limiter.acquire(execution_id)
            try:
                with open(script_path, 'w', newline='\n') as f:
                    f.write(state.script)
                os.chmod(script_path, 0o755)
            except IOError as e:
                return {"error": f"Failed to create script file: {e}"}
            
            start_time = time.time()
            isolation_method = state.isolation_method or workflow_config.isolation_method
            use_isolation = workflow_config.use_isolation
            
            if use_isolation and isolation_method == "docker":
                logger.info(f"Running script with Docker isolation for {state.target_name} {state.action}")
                result = await run_script_docker(
                    script_path,
                    workflow_config.execution_timeout,
                    workflow_config.least_privilege_execution
                )
            else:
                logger.info(f"Running script directly for {state.target_name} {state.action}")
                if is_windows:
                    result = await run_script_direct_windows(script_path, workflow_config.execution_timeout)
                else:
                    result = await run_script_direct(script_path, workflow_config.execution_timeout)
            
            success, stdout_str, stderr_str, exit_code, error_message = result
            end_time = time.time()
            execution_time = int((end_time - start_time) * 1000)
            
            metrics = ExecutionMetrics(
                start_time=start_time,
                end_time=end_time,
                execution_time=execution_time
            )
            output = OutputData(stdout=stdout_str, stderr=stderr_str, exit_code=exit_code)
            changes = state.changes.copy() if state.changes else []
            
            if success:
                # Optional: parse stdout for changes
                for line in stdout_str.lower().split('\n'):
                    if "installed package" in line:
                        changes.append(Change(
                            type="install",
                            target="package",
                            details="Installed package from script",
                            revertible=True
                        ))
                    if "created file" in line:
                        changes.append(Change(
                            type="create",
                            target="file",
                            details="Created file from script",
                            revertible=True
                        ))
                
                # If no changes detected, add a default one
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
            
            # Save to history if there's a history manager
            try:
                if self.history_manager:
                    record_id = await self.history_manager.save_execution(
                        target_name=state.target_name,
                        action=state.action,
                        success=success,
                        execution_time=execution_time,
                        error_message=None if success else error_message,
                        script=state.script,
                        output={"stdout": stdout_str, "stderr": stderr_str, "exit_code": exit_code},
                        parameters=state.parameters,
                        transaction_id=transaction_id,
                        user_id=workflow_config.user_id
                    )
                    execution_id = record_id
            except Exception as e:
                logger.error(f"Failed to save execution history: {e}")
                execution_id = None
            
            if success:
                return {
                    "output": output,
                    "status": f"Script executed successfully for {state.action} on {state.target_name}",
                    "changes": changes,
                    "legacy_changes": [c.details for c in changes],
                    "metrics": metrics,
                    "execution_id": execution_id,
                    "transaction_id": transaction_id
                }
            else:
                return {
                    "error": error_message or f"Script execution failed with exit code {exit_code}",
                    "output": output,
                    "metrics": metrics,
                    "execution_id": execution_id,
                    "transaction_id": transaction_id
                }
            
        except Exception as err:
            logger.exception(f"Error executing script: {err}")
            return {
                "error": f"Script execution failed: {str(err)}",
                "execution_id": execution_id,
                "transaction_id": transaction_id
            }
        finally:
            self.resource_limiter.release(execution_id)
            try:
                if os.path.exists(script_path):
                    os.unlink(script_path)
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Error cleaning up temporary files: {e}")