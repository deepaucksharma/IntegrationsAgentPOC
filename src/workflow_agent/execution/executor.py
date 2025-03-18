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
from datetime import datetime

from ..core.state import WorkflowState, OutputData, ExecutionMetrics, Change
from ..config.configuration import ensure_workflow_config
from .isolation import run_script_direct, run_script_docker
from ..utils.platform_manager import PlatformManager
from ..utils.resource_manager import ResourceManager
from ..error.exceptions import ExecutionError, ResourceError, TimeoutError

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
        platform_manager: Optional[PlatformManager] = None,
        resource_manager: Optional[ResourceManager] = None,
        timeout: int = 300
    ):
        self.platform_manager = platform_manager or PlatformManager()
        self.resource_manager = resource_manager or ResourceManager()
        self.timeout = timeout

    async def initialize(self) -> None:
        """Initialize the executor."""
        await self.resource_manager.initialize()

    async def cleanup(self) -> None:
        """Clean up executor resources."""
        await self.resource_manager.cleanup()

    async def run_script(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> WorkflowState:
        """Execute a script with proper resource management."""
        if not state.script:
            return state.set_error("No script to execute")

        # Create execution context
        execution_id = str(uuid.uuid4())
        metrics = ExecutionMetrics(start_time=datetime.utcnow())
        
        try:
            # Create temporary directory for script
            async with self.resource_manager.temp_directory(prefix=f"workflow-{execution_id}-") as temp_dir:
                # Get appropriate script extension
                script_ext = self.platform_manager.get_script_extension()
                script_path = os.path.join(temp_dir, f"script{script_ext}")
                
                # Write script to file
                script_content = self.platform_manager.get_script_header()
                script_content.extend([state.script])
                
                async with self.resource_manager.temp_file(
                    suffix=script_ext,
                    prefix=f"script-{execution_id}-",
                    content="\n".join(script_content)
                ) as script_file:
                    # Execute script
                    start_time = datetime.utcnow()
                    try:
                        process = await self.resource_manager.create_process(
                            self._get_execution_command(script_file),
                            cwd=temp_dir
                        )
                        
                        try:
                            stdout, stderr = await asyncio.wait_for(
                                process.communicate(),
                                timeout=self.timeout
                            )
                        except asyncio.TimeoutError:
                            raise TimeoutError(
                                f"Script execution timed out after {self.timeout} seconds",
                                details={"timeout": self.timeout, "execution_id": execution_id}
                            )
                        
                        end_time = datetime.utcnow()
                        duration = (end_time - start_time).total_seconds()
                        
                        # Update metrics
                        metrics.end_time = end_time
                        metrics.duration = duration
                        
                        # Create output data
                        output = OutputData(
                            stdout=stdout.decode() if stdout else "",
                            stderr=stderr.decode() if stderr else "",
                            exit_code=process.returncode,
                            duration=duration,
                            timestamp=end_time
                        )
                        
                        # Check execution status
                        if process.returncode != 0:
                            return state.evolve(
                                error=f"Script execution failed with exit code {process.returncode}",
                                output=output,
                                metrics=metrics,
                                execution_id=execution_id
                            )
                        
                        # Parse changes from output
                        changes = self._parse_changes(output.stdout)
                        
                        # Return successful state
                        return state.evolve(
                            output=output,
                            metrics=metrics,
                            execution_id=execution_id,
                            changes=changes
                        )
                        
                    except TimeoutError:
                        raise
                    except Exception as e:
                        raise ExecutionError(
                            f"Script execution failed: {str(e)}",
                            details={"execution_id": execution_id, "error": str(e)}
                        )
                        
        except (TimeoutError, ExecutionError) as e:
            return state.set_error(str(e))
        except Exception as e:
            logger.error(f"Unexpected error during script execution: {e}")
            return state.set_error(f"Unexpected error during script execution: {str(e)}")

    def _get_execution_command(self, script_path: str) -> str:
        """Get platform-specific command to execute script."""
        if self.platform_manager.platform_type.value == "windows":
            return f"powershell -ExecutionPolicy Bypass -File {script_path}"
        return f"bash {script_path}"

    def _parse_changes(self, output: str) -> list[Change]:
        """Parse changes from script output."""
        changes = []
        for line in output.lower().split('\n'):
            if "installed package" in line:
                changes.append(Change(
                    type="install",
                    target="package",
                    revertible=True,
                    revert_command=self._get_package_revert_command(line)
                ))
            elif "created file" in line:
                changes.append(Change(
                    type="create",
                    target="file",
                    revertible=True,
                    revert_command=f"rm -f {line.split()[-1]}"
                ))
            elif "modified config" in line:
                changes.append(Change(
                    type="modify",
                    target="config",
                    revertible=True,
                    revert_command=f"# TODO: Implement config restore"
                ))
        return changes

    def _get_package_revert_command(self, line: str) -> str:
        """Generate package removal command based on package manager."""
        if self.platform_manager.platform_type.value == "windows":
            return "choco uninstall {package} -y"
        
        # Detect package manager from line
        if "apt" in line:
            return "apt-get remove {package} -y"
        elif "yum" in line:
            return "yum remove {package} -y"
        elif "dnf" in line:
            return "dnf remove {package} -y"
        elif "zypper" in line:
            return "zypper remove {package} -y"
        
        return "# Unknown package manager"