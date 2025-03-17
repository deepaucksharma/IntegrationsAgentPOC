import os
import subprocess
import tempfile
import shutil
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

async def run_script_venv(
    script_path: str,
    timeout_ms: int,
    least_privilege: bool = True
) -> Tuple[bool, str, str, int, Optional[str]]:
    """
    Execute the script in a Python virtual environment.
    
    Args:
        script_path: Path to the script to execute
        timeout_ms: Timeout in milliseconds
        least_privilege: Whether to run with least privilege
        
    Returns:
        Tuple containing (success, stdout, stderr, exit_code, error_message)
    """
    # Check if venv module is available
    try:
        import venv
    except ImportError:
        logger.warning("Python venv module not available, falling back to direct execution")
        from .direct import run_script_direct
        return await run_script_direct(script_path, timeout_ms)
    
    # Create a temporary virtual environment
    venv_dir = tempfile.mkdtemp(prefix='workflow-venv-')
    process = None
    
    try:
        # Create venv
        logger.info(f"Creating Python virtual environment in {venv_dir}")
        venv.create(venv_dir, with_pip=True)
        
        # Copy script to venv
        venv_script_path = os.path.join(venv_dir, os.path.basename(script_path))
        shutil.copy2(script_path, venv_script_path)
        os.chmod(venv_script_path, 0o755)
        
        # Run script in venv
        activate_script = os.path.join(venv_dir, 'bin', 'activate')
        logger.info(f"Running script in virtual environment: {venv_dir}")
        process = subprocess.Popen(
            ['bash', '-c', f'source {activate_script} && {venv_script_path}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        stdout_str, stderr_str = process.communicate(timeout=timeout_ms / 1000)
        success = process.returncode == 0
        error_message = None if success else f"Venv script execution failed with return code {process.returncode}"
        return success, stdout_str, stderr_str, process.returncode, error_message
    except subprocess.TimeoutExpired:
        logger.error(f"Venv execution timed out after {timeout_ms}ms")
        if process:
            process.kill()
            stdout_str, stderr_str = process.communicate()
        else:
            stdout_str, stderr_str = "", ""
        stderr_str = f"Venv execution timed out after {timeout_ms}ms\n" + stderr_str
        error_message = stderr_str
        return False, stdout_str, stderr_str, 124, error_message
    except Exception as err:
        logger.exception(f"Error during venv execution: {err}")
        from .direct import run_script_direct
        return await run_script_direct(script_path, timeout_ms)
    finally:
        # Clean up venv environment
        try:
            shutil.rmtree(venv_dir, ignore_errors=True)
        except Exception as e:
            logger.error(f"Failed to clean up venv environment: {e}")