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
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Dict, Any, Optional, Tuple, List, Callable, Awaitable
from pathlib import Path
from ..core.state import WorkflowState, OutputData, ExecutionMetrics, Change
from ..config.configuration import ensure_workflow_config
from ..storage import HistoryManager
from .isolation import get_isolation_method, register_isolation_method
from ..monitoring.metrics import MetricsCollector

logger = logging.getLogger(__name__)

class ResourceLimiter:
    """
    Manages resource limits for script execution to prevent resource exhaustion.
    """
    def __init__(self, max_concurrent: int = 5, max_memory_mb: int = 1024, 
                 cpu_limit: float = 0.8, timeout_factor: float = 1.5):
        """Initialize resource limiter."""
        self.max_concurrent = max_concurrent
        self.max_memory_mb = max_memory_mb
        self.cpu_limit = cpu_limit
        self.timeout_factor = timeout_factor
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_executions = {}
        self._lock = threading.Lock()
    
    async def acquire(self, execution_id: str, estimated_duration: int = 0) -> bool:
        """
        Acquire resources for execution.
        
        Args:
            execution_id: Unique ID for this execution
            estimated_duration: Estimated duration in milliseconds
            
        Returns:
            True if resources acquired, False otherwise
        """
        await self.semaphore.acquire()
        
        # Check system resources
        if not self._check_system_resources():
            self.semaphore.release()
            return False
        
        # Register execution
        with self._lock:
            self.active_executions[execution_id] = {
                "start_time": time.time(),
                "estimated_duration": estimated_duration,
                "timeout": time.time() + (estimated_duration / 1000 * self.timeout_factor)
            }
        
        return True
    
    def release(self, execution_id: str) -> None:
        """
        Release resources for execution.
        
        Args:
            execution_id: Execution ID to release
        """
        with self._lock:
            if execution_id in self.active_executions:
                del self.active_executions[execution_id]
        
        self.semaphore.release()
    
    def _check_system_resources(self) -> bool:
        """
        Check if system has enough resources.
        
        Returns:
            True if resources available, False otherwise
        """
        try:
            # Check memory
            mem = psutil.virtual_memory()
            if mem.available < self.max_memory_mb * 1024 * 1024:
                logger.warning(f"Insufficient memory: {mem.available / (1024*1024):.1f}MB available")
                return False
            
            # Check CPU
            cpu = psutil.cpu_percent(interval=0.1) / 100
            if cpu > self.cpu_limit:
                logger.warning(f"High CPU usage: {cpu*100:.1f}%")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
            return True  # Assume resources available on error
    
    async def monitor_executions(self) -> None:
        """
        Monitor active executions and kill those that exceed timeout.
        Should be run in a separate task.
        """
        while True:
            try:
                now = time.time()
                to_kill = []
                
                with self._lock:
                    for execution_id, info in self.active_executions.items():
                        if now > info["timeout"]:
                            to_kill.append(execution_id)
                
                for execution_id in to_kill:
                    logger.warning(f"Execution {execution_id} exceeded timeout, killing")
                    # The process termination should be handled by the executor
                    with self._lock:
                        if execution_id in self.active_executions:
                            del self.active_executions[execution_id]
            
            except Exception as e:
                logger.error(f"Error in execution monitor: {e}")
            
            await asyncio.sleep(5)  # Check every 5 seconds

class ExecutionCache:
    """
    Caches execution results to avoid duplicate execution.
    """
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        """Initialize execution cache."""
        self.max_size = max_size
        self.ttl = ttl  # Time to live in seconds
        self.cache = {}
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached result for key.
        
        Args:
            key: Cache key
            
        Returns:
            Cached result or None if not found
        """
        with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                if time.time() < entry["expiry"]:
                    return entry["result"]
                else:
                    del self.cache[key]
        
        return None
    
    def put(self, key: str, result: Dict[str, Any]) -> None:
        """
        Cache execution result.
        
        Args:
            key: Cache key
            result: Execution result to cache
        """
        with self._lock:
            # Expire old entries if cache full
            if len(self.cache) >= self.max_size:
                now = time.time()
                expired = [k for k, v in self.cache.items() if now >= v["expiry"]]
                
                # Remove expired entries
                for k in expired:
                    del self.cache[k]
                
                # If still full, remove oldest entry
                if len(self.cache) >= self.max_size:
                    oldest = min(self.cache.items(), key=lambda x: x[1]["expiry"])
                    del self.cache[oldest[0]]
            
            self.cache[key] = {
                "result": result,
                "expiry": time.time() + self.ttl
            }
    
    def invalidate(self, key: str) -> None:
        """
        Invalidate cache entry.
        
        Args:
            key: Cache key to invalidate
        """
        with self._lock:
            if key in self.cache:
                del self.cache[key]
    
    def clear(self) -> None:
        """Clear entire cache."""
        with self._lock:
            self.cache.clear()

class ScriptExecutor:
    """Enhanced executor that runs scripts with different isolation methods and captures metrics."""
    
    def __init__(
        self, 
        history_manager: Optional[HistoryManager] = None, 
        timeout: int = 300,
        max_concurrent: int = 10,
        resource_limiter: Optional[ResourceLimiter] = None
    ):
        """
        Initialize the script executor.
        
        Args:
            history_manager: Optional history manager for recording execution history
            timeout: Default timeout for script execution in seconds
            max_concurrent: Maximum concurrent executions
            resource_limiter: Optional resource limiter
        """
        self.history_manager = history_manager or HistoryManager()
        self.timeout = timeout
        self.resource_limiter = resource_limiter or ResourceLimiter(max_concurrent=max_concurrent)
        self.metrics_collector = MetricsCollector()
        self.execution_cache = ExecutionCache()
        
        # Initialize thread and process pools with error handling
        try:
            self.thread_pool = ThreadPoolExecutor(max_workers=max_concurrent)
            self.process_pool = ProcessPoolExecutor(max_workers=max(1, max_concurrent // 2))
        except Exception as e:
            logger.error(f"Failed to initialize execution pools: {e}")
            # Fallback to single worker if pool creation fails
            self.thread_pool = ThreadPoolExecutor(max_workers=1)
            self.process_pool = ProcessPoolExecutor(max_workers=1)
        
        self.monitor_task = None
        self._cleanup_lock = threading.Lock()
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the executor.
        
        Args:
            config: Optional configuration
        """
        # Start resource monitor
        if self.monitor_task is None:
            self.monitor_task = asyncio.create_task(self.resource_limiter.monitor_executions())
        
        # Initialize isolation methods
        workflow_config = ensure_workflow_config(config)
        if workflow_config.isolation_method and workflow_config.use_isolation:
            # Pre-check if isolation method is available
            isolation_method = get_isolation_method(workflow_config.isolation_method)
            if not isolation_method:
                logger.warning(f"Isolation method {workflow_config.isolation_method} not available")
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        with self._cleanup_lock:
            # Cancel monitor task
            if self.monitor_task:
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except asyncio.CancelledError:
                    pass
                self.monitor_task = None
            
            # Shutdown thread and process pools with error handling
            try:
                self.thread_pool.shutdown(wait=False)
                self.process_pool.shutdown(wait=False)
            except Exception as e:
                logger.error(f"Error during pool shutdown: {e}")
                # Force shutdown if normal shutdown fails
                try:
                    self.thread_pool._threads.clear()
                    self.process_pool._processes.clear()
                except:
                    pass
            
            # Clear cache
            try:
                self.execution_cache.clear()
            except Exception as e:
                logger.error(f"Error clearing execution cache: {e}")
    
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
        execution_id = str(uuid.uuid4())
        
        # Generate cache key
        cache_key = self._generate_cache_key(state)
        
        # Check cache
        if cache_key and not state.parameters.get("force_execution", False):
            cached_result = self.execution_cache.get(cache_key)
            if cached_result:
                logger.info(f"Using cached result for {state.target_name}")
                # Add transaction ID and execution ID to result
                cached_result["transaction_id"] = transaction_id
                cached_result["execution_id"] = execution_id
                return cached_result
        
        try:
            # Acquire resources
            estimated_duration = workflow_config.execution_timeout
            if not await self.resource_limiter.acquire(execution_id, estimated_duration):
                logger.error("Failed to acquire resources for execution")
                return {"error": "System resources exhausted, try again later."}
            
            # Write script to temp file
            with open(script_path, 'w') as f:
                f.write(state.script)
            
            os.chmod(script_path, 0o755)
            logger.info(f"Prepared script at {script_path}")
            
            # Capture initial metrics with error handling
            start_time = time.time()
            metrics_data = {
                "start_cpu": 0,
                "start_memory": 0,
                "start_io": None,
                "start_network": None,
                "end_cpu": 0,
                "end_memory": 0,
                "end_io": None,
                "end_network": None
            }
            
            try:
                metrics_data["start_cpu"] = psutil.cpu_percent(interval=0.1)
                metrics_data["start_memory"] = psutil.virtual_memory().used
                try:
                    metrics_data["start_io"] = psutil.disk_io_counters()
                    metrics_data["start_network"] = psutil.net_io_counters()
                except Exception as e:
                    logger.warning(f"Failed to get initial IO/network metrics: {e}")
            except Exception as e:
                logger.warning(f"Failed to get initial system metrics: {e}")
            
            logger.info(f"Starting script execution: {script_path}")
            
            # Record workflow execution start in metrics with error handling
            try:
                self.metrics_collector.record_workflow_execution(
                    status="running",
                    target=state.target_name,
                    action=state.action,
                    duration=0
                )
            except Exception as e:
                logger.warning(f"Failed to record workflow execution start: {e}")
            
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
            
            # Capture final metrics with error handling
            end_time = time.time()
            execution_time_sec = end_time - start_time
            execution_time = int(execution_time_sec * 1000)  # Convert to ms
            
            try:
                metrics_data["end_cpu"] = psutil.cpu_percent(interval=0.1)
                metrics_data["end_memory"] = psutil.virtual_memory().used
                try:
                    metrics_data["end_io"] = psutil.disk_io_counters()
                    metrics_data["end_network"] = psutil.net_io_counters()
                except Exception as e:
                    logger.warning(f"Failed to get final IO/network metrics: {e}")
            except Exception as e:
                logger.warning(f"Failed to get final system metrics: {e}")
            
            # Record workflow execution completion in metrics with error handling
            try:
                self.metrics_collector.record_workflow_execution(
                    status="completed" if success else "failed",
                    target=state.target_name,
                    action=state.action,
                    duration=execution_time_sec
                )
            except Exception as e:
                logger.warning(f"Failed to record workflow execution completion: {e}")
            
            # Calculate metrics with error handling
            try:
                cpu_usage = (metrics_data["start_cpu"] + metrics_data["end_cpu"]) / 2
                memory_usage = max(0, metrics_data["end_memory"] - metrics_data["start_memory"])
                
                # Calculate IO and network metrics if available
                io_read = (metrics_data["end_io"].read_bytes - metrics_data["start_io"].read_bytes 
                          if metrics_data["end_io"] and metrics_data["start_io"] else None)
                io_write = (metrics_data["end_io"].write_bytes - metrics_data["start_io"].write_bytes 
                           if metrics_data["end_io"] and metrics_data["start_io"] else None)
                network_tx = (metrics_data["end_network"].bytes_sent - metrics_data["start_network"].bytes_sent 
                            if metrics_data["end_network"] and metrics_data["start_network"] else None)
                network_rx = (metrics_data["end_network"].bytes_recv - metrics_data["start_network"].bytes_recv 
                            if metrics_data["end_network"] and metrics_data["start_network"] else None)
            except Exception as e:
                logger.warning(f"Failed to calculate metrics: {e}")
                cpu_usage = None
                memory_usage = None
                io_read = None
                io_write = None
                network_tx = None
                network_rx = None
            
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
                    record_id = await self.history_manager.save_execution(
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
                    logger.info(f"Saved execution record with ID {record_id}")
                    execution_id = record_id
                else:
                    execution_id = None
            except Exception as e:
                logger.error(f"Failed to save execution record: {e}")
                execution_id = None
            
            result_dict = {}
            if success:
                logger.info(f"Script executed successfully for {state.action} on {state.target_name}")
                result_dict = {
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
                result_dict = {
                    "error": error_message or "Script execution failed",
                    "output": output,
                    "metrics": metrics,
                    "execution_id": execution_id,
                    "transaction_id": transaction_id,
                    "changes": changes,
                    "legacy_changes": [change.details for change in changes]
                }
            
            # Cache successful results
            if success and cache_key:
                self.execution_cache.put(cache_key, result_dict)
            
            return result_dict
            
        except Exception as err:
            error_message = str(err)
            logger.exception(f"Script execution failed with exception: {error_message}")
            end_time = time.time()
            execution_time = int((end_time - (state.metrics.start_time if state.metrics and state.metrics.start_time else end_time)) * 1000)
            
            # Record execution failure in metrics
            self.metrics_collector.record_workflow_execution(
                status="failed",
                target=state.target_name,
                action=state.action,
                duration=end_time - (state.metrics.start_time if state.metrics and state.metrics.start_time else end_time)
            )
            
            try:
                if self.history_manager:
                    record_id = await self.history_manager.save_execution(
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
                    record_id = None
            except Exception as e:
                logger.error(f"Failed to save execution record for error: {e}")
                record_id = None
            
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
                "execution_id": record_id,
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
            # Release resources
            self.resource_limiter.release(execution_id)
            
            # Cleanup temporary files
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
    
    def _generate_cache_key(self, state: WorkflowState) -> Optional[str]:
        """
        Generate cache key for state.
        
        Args:
            state: Workflow state
            
        Returns:
            Cache key or None if caching not applicable
        """
        # Skip caching for certain actions
        if state.action in ["verify", "test", "debug"]:
            return None
        
        # Skip caching if explicitly disabled
        if state.parameters.get("skip_cache", False):
            return None
        
        # Generate hash of relevant state parts
        key_parts = [
            state.target_name,
            state.action,
            state.integration_type
        ]
        
        # Add parameter hash
        param_str = json.dumps(state.parameters, sort_keys=True)
        
        # Generate key
        import hashlib
        hash_obj = hashlib.sha256()
        hash_obj.update(":".join(key_parts).encode('utf-8'))
        hash_obj.update(param_str.encode('utf-8'))
        
        return hash_obj.hexdigest()
    
    async def run_scripts_batch(
        self, 
        states: List[WorkflowState],
        config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Run multiple scripts in parallel.
        
        Args:
            states: List of workflow states
            config: Optional configuration
            
        Returns:
            List of execution results
        """
        tasks = [self.run_script(state, config) for state in states]
        return await asyncio.gather(*tasks)
    
    async def run_script_group(
        self,
        states: List[WorkflowState],
        config: Optional[Dict[str, Any]] = None,
        fail_fast: bool = False
    ) -> Dict[str, Any]:
        """
        Run a group of scripts with dependency tracking.
        
        Args:
            states: List of workflow states
            config: Optional configuration
            fail_fast: Whether to stop on first failure
            
        Returns:
            Dict with group execution results
        """
        results = {}
        failed = False
        
        # Sort states by dependencies
        sorted_states = self._sort_states_by_dependencies(states)
        
        for state in sorted_states:
            if failed and fail_fast:
                results[state.target_name] = {
                    "error": "Skipped due to previous failure",
                    "skipped": True
                }
                continue
            
            result = await self.run_script(state, config)
            results[state.target_name] = result
            
            if "error" in result:
                failed = True
        
        return {
            "results": results,
            "success": not failed,
            "failed_targets": [target for target, result in results.items() if "error" in result],
            "succeeded_targets": [target for target, result in results.items() if "error" not in result]
        }
    
    def _sort_states_by_dependencies(self, states: List[WorkflowState]) -> List[WorkflowState]:
        """
        Sort states by dependencies to ensure correct execution order.
        
        Args:
            states: List of workflow states
            
        Returns:
            Sorted list of states
        """
        # Build dependency graph
        graph = {}
        for state in states:
            target = state.target_name
            if target not in graph:
                graph[target] = set()
            
            # Add dependencies
            if hasattr(state, 'dependencies') and state.dependencies:
                for dep in state.dependencies:
                    if dep not in graph:
                        graph[dep] = set()
                    graph[target].add(dep)
        
        # Topological sort with cycle detection
        sorted_targets = []
        visited = set()
        temp_visited = set()
        cycle_path = []
        
        def visit(target):
            if target in temp_visited:
                # Cycle detected - log the full cycle path
                cycle_start = cycle_path.index(target)
                cycle = cycle_path[cycle_start:] + [target]
                logger.error(f"Dependency cycle detected: {' -> '.join(cycle)}")
                # Break the cycle by removing the last dependency
                if target in graph and cycle[-2] in graph[target]:
                    graph[target].remove(cycle[-2])
                    logger.info(f"Breaking cycle by removing dependency {cycle[-2]} from {target}")
                return
            
            if target not in visited:
                temp_visited.add(target)
                cycle_path.append(target)
                
                # Visit dependencies
                for dep in sorted(graph.get(target, [])):
                    visit(dep)
                
                cycle_path.pop()
                temp_visited.remove(target)
                visited.add(target)
                sorted_targets.append(target)
        
        # Visit all targets
        for target in sorted(graph.keys()):
            if target not in visited:
                visit(target)
        
        # Sort states based on target order
        target_to_state = {state.target_name: state for state in states}
        sorted_states = []
        
        for target in sorted_targets:
            if target in target_to_state:
                sorted_states.append(target_to_state[target])
        
        # Add any states not in the dependency graph
        for state in states:
            if state.target_name not in sorted_targets:
                sorted_states.append(state)
        
        return sorted_states