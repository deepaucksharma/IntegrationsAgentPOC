import os
import subprocess
import tempfile
import shutil
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

async def run_script_sandbox(
    script_path: str,
    timeout_ms: int,
    least_privilege: bool = True
) -> Tuple[bool, str, str, int, Optional[str]]:
    """
    Execute the script using nsjail sandbox for enhanced isolation.
    
    Args:
        script_path: Path to the script to execute
        timeout_ms: Timeout in milliseconds
        least_privilege: Whether to run with least privilege
        
    Returns:
        Tuple containing (success, stdout, stderr, exit_code, error_message)
    """
    # Check if nsjail is available
    nsjail_path = shutil.which('nsjail')
    if not nsjail_path:
        logger.warning("nsjail not available, falling back to direct execution")
        from .direct import run_script_direct
        return await run_script_direct(script_path, timeout_ms)
    
    # Create temporary directory for logs
    log_dir = tempfile.mkdtemp(prefix='workflow-nsjail-')
    log_path = os.path.join(log_dir, 'nsjail.log')
    process = None
    
    try:
        # Run script with nsjail
        logger.info(f"Running script in nsjail sandbox: {script_path}")
        cmd = [
            nsjail_path,
            '--quiet',
            '-Mo',  # Mount as read-only
            '--user', 'nobody',
            '--group', 'nogroup',
            '--disable_proc',
            '--time_limit', str(int(timeout_ms / 1000)),
            '--cwd', '/',
            '-R', f"{script_path}:/script.sh",
            '--',
            '/script.sh'
        ]
        
        # Add additional constraints if least_privilege is enabled
        if least_privilege:
            cmd.extend([
                '--rlimit_as', '1000',  # Address space limit in MB
                '--rlimit_cpu', '1',    # CPU time limit in seconds
                '--rlimit_fsize', '5',  # File size limit in MB
                '--rlimit_nofile', '32' # Number of open files
            ])
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        stdout_str, stderr_str = process.communicate(timeout=timeout_ms / 1000)
        success = process.returncode == 0
        error_message = None if success else f"Sandbox execution failed with return code {process.returncode}"
        return success, stdout_str, stderr_str, process.returncode, error_message
    except subprocess.TimeoutExpired:
        logger.error(f"Sandbox execution timed out after {timeout_ms}ms")
        if process:
            process.kill()
            stdout_str, stderr_str = process.communicate()
        else:
            stdout_str, stderr_str = "", ""
        stderr_str = f"Sandbox execution timed out after {timeout_ms}ms\n" + stderr_str
        error_message = stderr_str
        return False, stdout_str, stderr_str, 124, error_message
    except Exception as err:
        logger.exception(f"Error during sandbox execution: {err}")
        from .direct import run_script_direct
        return await run_script_direct(script_path, timeout_ms)
    finally:
        # Clean up log directory
        try:
            shutil.rmtree(log_dir, ignore_errors=True)
        except Exception as e:
            logger.error(f"Failed to clean up sandbox logs: {e}")