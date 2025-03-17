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
from ..state import WorkflowState, OutputData, ExecutionMetrics, Change
from ..configuration import ensure_workflow_config
from ..history import save_execution, async_save_execution

logger = logging.getLogger(__name__)

async def run_script(
    state: WorkflowState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Runs the generated script in a controlled environment, capturing system metrics,
    handling errors, and recording the execution in history.
    
    Args:
        state: Current workflow state
        config: Optional configuration
        
    Returns:
        Dict with updates to workflow state or error message
        
    Error Handling:
      - Catches timeouts and unexpected exceptions
      - Cleans up temporary resources
      - Records failures in history
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
        with open(script_path, 'w') as f:
            f.write(state.script)
        
        os.chmod(script_path, 0o755)
        logger.info(f"Prepared script at {script_path}")
        
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
            if isolation_method == "docker":
                logger.info("Attempting to run script in Docker container")
                result = await _run_script_docker(script_path, workflow_config.execution_timeout, workflow_config.least_privilege_execution)
            elif isolation_method == "chroot":
                logger.info("Attempting to run script in chroot environment")
                result = await _run_script_chroot(script_path, workflow_config.execution_timeout)
            elif isolation_method == "venv":
                logger.info("Attempting to run script in Python venv")
                result = await _run_script_venv(script_path, workflow_config.execution_timeout)
            elif isolation_method == "sandbox":
                logger.info("Attempting to run script in sandbox (nsjail)")
                result = await _run_script_sandbox(script_path, workflow_config.execution_timeout)
            else:
                logger.warning(f"Unknown isolation method: {isolation_method}, falling back to direct execution")
                result = await _run_script_direct(script_path, workflow_config.execution_timeout)
        else:
            logger.info("Running script directly (no isolation)")
            result = await _run_script_direct(script_path, workflow_config.execution_timeout)
        
        success, stdout_str, stderr_str, exit_code, error_message = result
        
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
            for line in stdout_str.lower().split('\n'):
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
            execution_id = await async_save_execution(
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
    except asyncio.TimeoutError:
        error_message = f"Script execution timed out after {workflow_config.execution_timeout} seconds"
        logger.error(error_message)
        return {
            "error": error_message,
            "metrics": metrics,
            "execution_id": execution_id,
            "transaction_id": transaction_id,
            "changes": changes,
            "legacy_changes": [change.details for change in changes]
        }
    except Exception as e:
        error_message = f"Script execution failed: {str(e)}"
        logger.error(error_message)
        return {
            "error": error_message,
            "metrics": metrics,
            "execution_id": execution_id,
            "transaction_id": transaction_id,
            "changes": changes,
            "legacy_changes": [change.details for change in changes]
        }
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Removed temporary directory: {temp_dir}")
        except OSError as e:
            logger.warning(f"Failed to remove temporary directory {temp_dir}: {e}")

async def _run_script_direct(script_path: str, timeout: int) -> Tuple[bool, str, str, int, Optional[str]]:
    """Runs the script directly using subprocess."""
    try:
        process = await asyncio.create_subprocess_shell(
            f"bash {script_path}",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Create a new process group
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            stdout_str = stdout.decode("utf-8", errors="ignore")
            stderr_str = stderr.decode("utf-8", errors="ignore")
            exit_code = process.returncode
            success = exit_code == 0
            error_message = stderr_str if not success else None
            
        except asyncio.TimeoutError:
            # Kill the process group
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except OSError as e:
                logger.warning(f"Failed to kill process group: {e}")
            
            stdout_str, stderr_str = await process.communicate()
            stdout_str = stdout_str.decode("utf-8", errors="ignore")
            stderr_str = stderr_str.decode("utf-8", errors="ignore")
            exit_code = -1
            error_message = f"Script execution timed out after {timeout} seconds"
            success = False
        
        return success, stdout_str, stderr_str, exit_code, error_message
    except Exception as e:
        error_message = f"Failed to execute script: {str(e)}"
        logger.error(error_message)
        return False, "", "", -1, error_message

async def _run_script_docker(script_path: str, timeout: int, least_privilege: bool) -> Tuple[bool, str, str, int, Optional[str]]:
    """Runs the script inside a Docker container."""
    try:
        # Build the Docker command
        docker_command = [
            "docker", "run", "--rm",
            "-v", f"{os.path.dirname(script_path)}:/app",  # Mount the directory
            "-w", "/app",  # Set working directory
            "ubuntu:latest",  # Use a lightweight image
            "bash", script_path.split("/")[-1]  # Execute the script
        ]
        
        if least_privilege:
            docker_command.insert(2, "--security-opt=no-new-privileges")
            docker_command.insert(2, "--user=1000:1000")
        
        process = await asyncio.create_subprocess_exec(
            *docker_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            stdout_str = stdout.decode("utf-8", errors="ignore")
            stderr_str = stderr.decode("utf-8", errors="ignore")
            exit_code = process.returncode
            success = exit_code == 0
            error_message = stderr_str if not success else None
        except asyncio.TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode("utf-8", errors="ignore")
            stderr_str = stderr.decode("utf-8", errors="ignore")
            exit_code = -1
            error_message = f"Script execution timed out after {timeout} seconds"
            success = False
        
        return success, stdout_str, stderr_str, exit_code, error_message
    except Exception as e:
        error_message = f"Failed to execute script in Docker: {str(e)}"
        logger.error(error_message)
        return False, "", "", -1, error_message

async def _run_script_chroot(script_path: str, timeout: int) -> Tuple[bool, str, str, int, Optional[str]]:
    """Runs the script inside a chroot environment."""
    try:
        # Create a temporary chroot environment
        chroot_dir = tempfile.mkdtemp(prefix='chroot-')
        
        # Copy the script into the chroot environment
        shutil.copy(script_path, os.path.join(chroot_dir, "script.sh"))
        
        # Create basic directories
        os.makedirs(os.path.join(chroot_dir, "dev"), exist_ok=True)
        os.makedirs(os.path.join(chroot_dir, "proc"), exist_ok=True)
        os.makedirs(os.path.join(chroot_dir, "sys"), exist_ok=True)
        
        # Mount necessary filesystems
        mount_commands = [
            f"mount --bind /dev {os.path.join(chroot_dir, 'dev')}",
            f"mount --bind /proc {os.path.join(chroot_dir, 'proc')}",
            f"mount --bind /sys {os.path.join(chroot_dir, 'sys')}"
        ]
        for cmd in mount_commands:
            subprocess.run(cmd, shell=True, check=True)
        
        # Build the chroot command
        chroot_command = [
            "chroot", chroot_dir,
            "bash", "script.sh"
        ]
        
        process = await asyncio.create_subprocess_exec(
            *chroot_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            stdout_str = stdout.decode("utf-8", errors="ignore")
            stderr_str = stderr.decode("utf-8", errors="ignore")
            exit_code = process.returncode
            success = exit_code == 0
            error_message = stderr_str if not success else None
        except asyncio.TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode("utf-8", errors="ignore")
            stderr_str = stderr.decode("utf-8", errors="ignore")
            exit_code = -1
            error_message = f"Script execution timed out after {timeout} seconds"
            success = False
        
        # Unmount filesystems
        umount_commands = [
            f"umount {os.path.join(chroot_dir, 'dev')}",
            f"umount {os.path.join(chroot_dir, 'proc')}",
            f"umount {os.path.join(chroot_dir, 'sys')}"
        ]
        for cmd in umount_commands:
            subprocess.run(cmd, shell=True, check=False)  # Ignore errors on umount
        
        # Clean up chroot directory
        shutil.rmtree(chroot_dir)
        
        return success, stdout_str, stderr_str, exit_code, error_message
    except Exception as e:
        error_message = f"Failed to execute script in chroot: {str(e)}"
        logger.error(error_message)
        # Clean up chroot directory on error
        try:
            shutil.rmtree(chroot_dir)
        except OSError:
            pass
        return False, "", "", -1, error_message

async def _run_script_venv(script_path: str, timeout: int) -> Tuple[bool, str, str, int, Optional[str]]:
    """Runs the script inside a Python virtual environment."""
    try:
        # Create a temporary venv
        venv_dir = tempfile.mkdtemp(prefix='venv-')
        
        # Create the venv
        subprocess.run([shutil.which("python3"), "-m", "venv", venv_dir], check=True)
        
        # Get the activate script path
        activate_script = Path(venv_dir) / "bin" / "activate"
        if not activate_script.exists():
            activate_script = Path(venv_dir) / "Scripts" / "activate"  # Windows
        
        # Build the command to run the script
        command = [
            "bash", "-c",
            f"source {activate_script} && bash {script_path}"
        ]
        
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(script_path)
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            stdout_str = stdout.decode("utf-8", errors="ignore")
            stderr_str = stderr.decode("utf-8", errors="ignore")
            exit_code = process.returncode
            success = exit_code == 0
            error_message = stderr_str if not success else None
        except asyncio.TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode("utf-8", errors="ignore")
            stderr_str = stderr.decode("utf-8", errors="ignore")
            exit_code = -1
            error_message = f"Script execution timed out after {timeout} seconds"
            success = False
        
        # Clean up venv
        shutil.rmtree(venv_dir)
        
        return success, stdout_str, stderr_str, exit_code, error_message
    except Exception as e:
        error_message = f"Failed to execute script in venv: {str(e)}"
        logger.error(error_message)
        # Clean up venv on error
        try:
            shutil.rmtree(venv_dir)
        except OSError:
            pass
        return False, "", "", -1, error_message

async def _run_script_sandbox(script_path: str, timeout: int) -> Tuple[bool, str, str, int, Optional[str]]:
    """Runs the script inside a sandbox (nsjail)."""
    try:
        # Build the nsjail command
        nsjail_command = [
            "nsjail",
            "-Mo",  # Minimal mode
            "--disable-stdio-log",
            "--time_limit", str(timeout),
            "--cwd", "/",  # Set working directory
            "--bindmount", f"{os.path.dirname(script_path)}:/app",  # Mount the directory
            "--exec", "/app/" + os.path.basename(script_path)  # Execute the script
        ]
        
        process = await asyncio.create_subprocess_exec(
            *nsjail_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            stdout_str = stdout.decode("utf-8", errors="ignore")
            stderr_str = stderr.decode("utf-8", errors="ignore")
            exit_code = process.returncode
            success = exit_code == 0
            error_message = stderr_str if not success else None
        except asyncio.TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode("utf-8", errors="ignore")
            stderr_str = stderr.decode("utf-8", errors="ignore")
            exit_code = -1
            error_message = f"Script execution timed out after {timeout} seconds"
            success = False
        
        return success, stdout_str, stderr_str, exit_code, error_message
    except Exception as e:
        error_message = f"Failed to execute script in sandbox: {str(e)}"
        logger.error(error_message)
        return False, "", "", -1, error_message