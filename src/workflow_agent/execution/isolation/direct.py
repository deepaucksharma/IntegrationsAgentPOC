import subprocess
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

async def run_script_direct(
    script_path: str,
    timeout_ms: int,
    least_privilege: bool = True
) -> Tuple[bool, str, str, int, Optional[str]]:
    """
    Execute the script directly on the host system.
    
    Args:
        script_path: Path to the script to execute
        timeout_ms: Timeout in milliseconds
        least_privilege: Whether to run with least privilege (unused in direct mode)
        
    Returns:
        Tuple containing (success, stdout, stderr, exit_code, error_message)
    """
    process = None
    try:
        logger.info(f"Executing script directly: {script_path}")
        process = subprocess.Popen(
            [script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            shell=False
        )
        stdout_str, stderr_str = process.communicate(timeout=timeout_ms / 1000)
        success = process.returncode == 0
        error_message = None if success else f"Script execution failed with return code {process.returncode}"
        return success, stdout_str, stderr_str, process.returncode, error_message
    except subprocess.TimeoutExpired:
        logger.error(f"Script execution timed out after {timeout_ms}ms")
        if process:
            process.kill()
            stdout_str, stderr_str = process.communicate()
        else:
            stdout_str, stderr_str = "", ""
        stderr_str = f"Script execution timed out after {timeout_ms}ms\n" + stderr_str
        error_message = stderr_str
        return False, stdout_str, stderr_str, 124, error_message  # 124 is the exit code for timeout
    except Exception as err:
        logger.exception(f"Error during script execution: {err}")
        if process:
            process.kill()
            try:
                stdout_str, stderr_str = process.communicate(timeout=1)
            except:
                stdout_str, stderr_str = "", str(err)
        else:
            stdout_str, stderr_str = "", str(err)
        error_message = f"Script execution failed: {stderr_str}"
        return False, stdout_str, stderr_str, 1, error_message