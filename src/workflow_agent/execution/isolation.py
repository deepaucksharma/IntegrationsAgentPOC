"""Isolation methods for script execution."""
import os
import uuid
import tempfile
import shutil
import logging
import asyncio
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

async def run_script_direct(
    script_path: str,
    timeout_ms: int
) -> Tuple[bool, str, str, int, Optional[str]]:
    """Execute the script directly on the host system."""
    process = None
    timeout_sec = timeout_ms / 1000
    try:
        process = await asyncio.create_subprocess_exec(
            script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
            stdout_str = stdout.decode('utf-8')
            stderr_str = stderr.decode('utf-8')
            success = process.returncode == 0
            error_message = None if success else f"Script execution failed with return code {process.returncode}"
            return success, stdout_str, stderr_str, process.returncode, error_message
        except asyncio.TimeoutError:
            if process:
                process.kill()
                try:
                    stdout, stderr = await process.communicate()
                    stdout_str = stdout.decode('utf-8')
                    stderr_str = stderr.decode('utf-8')
                except:
                    stdout_str, stderr_str = "", ""
            else:
                stdout_str, stderr_str = "", ""
            stderr_str = f"Script execution timed out after {timeout_sec}s\n" + stderr_str
            return False, stdout_str, stderr_str, 124, stderr_str
    except Exception as err:
        if process:
            process.kill()
            try:
                stdout, stderr = await process.communicate()
                stdout_str = stdout.decode('utf-8')
                stderr_str = stderr.decode('utf-8')
            except:
                stdout_str, stderr_str = "", str(err)
        else:
            stdout_str, stderr_str = "", str(err)
        return False, stdout_str, stderr_str, 1, f"Script execution failed: {stderr_str}"

async def run_script_docker(
    script_path: str,
    timeout_ms: int,
    least_privilege: bool = True
) -> Tuple[bool, str, str, int, Optional[str]]:
    """Execute the script in an isolated Docker container."""
    try:
        process = await asyncio.create_subprocess_exec(
            "docker", "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.wait()
        if process.returncode != 0:
            logger.warning("Docker not available, falling back to direct execution")
            return await run_script_direct(script_path, timeout_ms)
    except Exception:
        logger.warning("Docker not available, falling back to direct execution")
        return await run_script_direct(script_path, timeout_ms)
    
    temp_dir = tempfile.mkdtemp(prefix='workflow-docker-')
    container_script_path = os.path.join(temp_dir, os.path.basename(script_path))
    shutil.copy2(script_path, container_script_path)
    
    container_name = f"workflow-{uuid.uuid4().hex[:8]}"
    docker_image = "alpine:latest"
    docker_cmd = ["docker", "run", "--rm", "--name", container_name]
    if least_privilege:
        docker_cmd.extend([
            "--read-only",
            "--security-opt=no-new-privileges",
            "--memory=512m",
            "--cpus=1",
            "--network=none"
        ])
    docker_cmd.extend(["-v", f"{container_script_path}:/script.sh"])
    docker_cmd.extend([docker_image, "sh", "-c", "chmod +x /script.sh && /script.sh"])
    
    process = None
    timeout_sec = timeout_ms / 1000
    try:
        logger.info(f"Running script in Docker container: {container_name}")
        process = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
            stdout_str = stdout.decode('utf-8')
            stderr_str = stderr.decode('utf-8')
            success = process.returncode == 0
            error_message = None if success else f"Script execution in container failed with return code {process.returncode}"
            return success, stdout_str, stderr_str, process.returncode, error_message
        except asyncio.TimeoutError:
            logger.error(f"Container execution timed out after {timeout_sec}s")
            try:
                kill_process = await asyncio.create_subprocess_exec(
                    "docker", "kill", container_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await kill_process.wait()
            except:
                pass
            if process:
                process.kill()
                try:
                    stdout, stderr = await process.communicate()
                    stdout_str = stdout.decode('utf-8')
                    stderr_str = stderr.decode('utf-8')
                except:
                    stdout_str, stderr_str = "", ""
            else:
                stdout_str, stderr_str = "", ""
            stderr_str = f"Container execution timed out after {timeout_sec}s\n" + stderr_str
            return False, stdout_str, stderr_str, 124, stderr_str
    except Exception as err:
        logger.exception(f"Error during container execution: {err}")
        try:
            kill_process = await asyncio.create_subprocess_exec(
                "docker", "kill", container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await kill_process.wait()
        except:
            pass
        if process:
            process.kill()
            try:
                stdout, stderr = await process.communicate()
                stdout_str = stdout.decode('utf-8')
                stderr_str = stderr.decode('utf-8')
            except:
                stdout_str, stderr_str = "", str(err)
        else:
            stdout_str, stderr_str = "", str(err)
        return False, stdout_str, stderr_str, 1, f"Container execution failed: {stderr_str}"
    finally:
        try:
            if os.path.exists(container_script_path):
                os.unlink(container_script_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception as e:
            logger.error(f"Failed to clean up container script: {e}")