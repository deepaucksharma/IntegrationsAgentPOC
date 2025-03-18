"""Script execution with resource management."""
import os
import uuid
import tempfile
import time
import asyncio
import logging
import shutil
import json
from typing import Dict, Any, Optional, List

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
        """Blocking acquire with no return value."""
        await self.semaphore.acquire()
        async with self._lock:
            self.active_executions[execution_id] = {"start_time": time.time()}
    
    def release(self, execution_id: str) -> None:
        """Release resources for execution."""
        try:
            self.semaphore.release()
        except ValueError:
            # Handle case where semaphore might already be released
            pass
        
        if execution_id in self.active_executions:
            self.active_executions.pop(execution_id, None)

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
        pass
    
    async def cleanup(self) -> None:
        pass
    
    async def run_script(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not state.script:
            return {"error": "No script to run."}
        
        workflow_config = ensure_workflow_config(config or {})
        
        temp_dir = tempfile.mkdtemp(prefix='workflow-')
        script_id = str(uuid.uuid4())
        script_path = os.path.join(temp_dir, f"script-{script_id}.sh")
        
        transaction_id = state.transaction_id or str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        
        try:
            await self.resource_limiter.acquire(execution_id)
            
            with open(script_path, 'w') as f:
                f.write(state.script)
            os.chmod(script_path, 0o755)
            
            start_time = time.time()
            
            isolation_method = state.isolation_method or workflow_config.isolation_method
            use_isolation = workflow_config.use_isolation
            
            if use_isolation and isolation_method == "docker":
                result = await run_script_docker(
                    script_path,
                    workflow_config.execution_timeout,
                    workflow_config.least_privilege_execution
                )
            else:
                result = await run_script_direct(script_path, workflow_config.execution_timeout)
            
            success, stdout_str, stderr_str, exit_code, error_message = result
            end_time = time.time()
            execution_time_sec = end_time - start_time
            execution_time = int(execution_time_sec * 1000)
            
            metrics = ExecutionMetrics(
                start_time=start_time,
                end_time=end_time,
                execution_time=execution_time
            )
            output = OutputData(stdout=stdout_str, stderr=stderr_str, exit_code=exit_code)
            
            changes = state.changes.copy() if state.changes else []
            if success:
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
            
            # Save to history
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
                    "error": error_message or "Script execution failed",
                    "output": output,
                    "metrics": metrics,
                    "execution_id": execution_id,
                    "transaction_id": transaction_id
                }
            
        except Exception as err:
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
            except:
                pass