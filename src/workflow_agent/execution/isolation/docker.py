import os
import uuid
import tempfile
import subprocess
import shutil
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

async def run_script_docker(
    script_path: str,
    timeout_ms: int,
    least_privilege: bool = True
) -> Tuple[bool, str, str, int, Optional[str]]:
    """
    Execute the script in an isolated Docker container.
    
    Args:
        script_path: Path to the script to execute
        timeout_ms: Timeout in milliseconds
        least_privilege: Whether to run with least privilege
        
    Returns:
        Tuple containing (success, stdout, stderr, exit_code, error_message)
    """
    # Check if Docker is available
    try:
        docker_check = subprocess.run(
            ["docker", "--version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            timeout=2
        )
        if docker_check.returncode != 0:
            logger.warning("Docker not available for isolation, falling back to direct execution")
            from .direct import run_script_direct
            return await run_script_direct(script_path, timeout_ms)
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("Docker not available for isolation, falling back to direct execution")
        from .direct import run_script_direct
        return await run_script_direct(script_path, timeout_ms)
    
    # Create temporary directory for container files
    temp_dir = tempfile.mkdtemp(prefix='workflow-docker-')
    container_script_path = os.path.join(temp_dir, os.path.basename(script_path))
    shutil.copy2(script_path, container_script_path)
    
    container_name = f"workflow-{uuid.uuid4().hex[:8]}"
    
    docker_image = "alpine:latest"
    docker_cmd = ["docker", "run", "--rm", "--name", container_name]
    
    # Add security and resource constraints
    if least_privilege:
        docker_cmd.extend([
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory=512m",
            "--cpus=1",
            "--pids-limit=100",
            "--network=none"
        ])
    
    # Add volume mount
    docker_cmd.extend(["-v", f"{container_script_path}:/script.sh"])
    
    # Add image and command
    docker_cmd.extend([docker_image, "sh", "-c", "chmod +x /script.sh && /script.sh"])
    
    process = None
    try:
        logger.info(f"Running script in isolated Docker container: {container_name}")
        process = subprocess.Popen(
            docker_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        stdout_str, stderr_str = process.communicate(timeout=timeout_ms / 1000)
        success = process.returncode == 0
        error_message = None if success else f"Script execution in container failed with return code {process.returncode}"
        return success, stdout_str, stderr_str, process.returncode, error_message
    except subprocess.TimeoutExpired:
        logger.error(f"Container execution timed out after {timeout_ms}ms")
        try:
            subprocess.run(["docker", "kill", container_name], 
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        except:
            pass
        if process:
            process.kill()
            stdout_str, stderr_str = process.communicate()
        else:
            stdout_str, stderr_str = "", ""
        stderr_str = f"Container execution timed out after {timeout_ms}ms\n" + stderr_str
        error_message = stderr_str
        return False, stdout_str, stderr_str, 124, error_message
    except Exception as err:
        logger.exception(f"Error during container execution: {err}")
        try:
            subprocess.run(["docker", "kill", container_name], 
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        except:
            pass
        if process:
            process.kill()
            try:
                stdout_str, stderr_str = process.communicate(timeout=1)
            except:
                stdout_str, stderr_str = "", str(err)
        else:
            stdout_str, stderr_str = "", str(err)
        error_message = f"Container execution failed: {stderr_str}"
        return False, stdout_str, stderr_str, 1, error_message
    finally:
        try:
            if os.path.exists(container_script_path):
                os.unlink(container_script_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception as e:
            logger.error(f"Failed to clean up container script: {e}")