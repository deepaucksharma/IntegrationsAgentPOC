import os
import subprocess
import logging
import shutil
import tempfile
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

async def run_script_chroot(
    script_path: str,
    timeout_ms: int,
    least_privilege: bool = True
) -> Tuple[bool, str, str, int, Optional[str]]:
    """
    Execute the script in a chroot environment for isolation.
    
    Args:
        script_path: Path to the script to execute
        timeout_ms: Timeout in milliseconds
        least_privilege: Whether to run with least privilege
        
    Returns:
        Tuple containing (success, stdout, stderr, exit_code, error_message)
    """
    # Check if chroot is available and user has permissions
    if os.geteuid() != 0:
        logger.warning("Chroot isolation requires root privileges, falling back to direct execution")
        from .direct import run_script_direct
        return await run_script_direct(script_path, timeout_ms)
    
    # Create a minimal chroot environment
    chroot_dir = tempfile.mkdtemp(prefix='workflow-chroot-')
    process = None
    
    try:
        # Create minimal directories
        for d in ['bin', 'lib', 'lib64', 'usr', 'tmp']:
            os.makedirs(os.path.join(chroot_dir, d), exist_ok=True)
        
        # Copy script to chroot
        chroot_script_path = os.path.join(chroot_dir, 'tmp', os.path.basename(script_path))
        shutil.copy2(script_path, chroot_script_path)
        os.chmod(chroot_script_path, 0o755)
        
        # Copy minimal shell
        shell_path = shutil.which('sh')
        if not shell_path:
            logger.error("Could not find sh shell, cannot create chroot environment")
            from .direct import run_script_direct
            return await run_script_direct(script_path, timeout_ms)
            
        # Copy shell and dependencies
        subprocess.run(['cp', shell_path, os.path.join(chroot_dir, 'bin', 'sh')])
        
        # Find and copy required libraries
        ldd_output = subprocess.check_output(['ldd', shell_path]).decode('utf-8')
        for line in ldd_output.splitlines():
            if '=>' in line:
                lib_path = line.split('=>')[1].strip().split()[0]
                if lib_path.startswith('/'):
                    dir_name = os.path.dirname(lib_path).lstrip('/')
                    os.makedirs(os.path.join(chroot_dir, dir_name), exist_ok=True)
                    shutil.copy2(lib_path, os.path.join(chroot_dir, dir_name, os.path.basename(lib_path)))
        
        # Run in chroot
        logger.info(f"Running script in chroot environment: {chroot_dir}")
        process = subprocess.Popen(
            ['chroot', chroot_dir, '/bin/sh', '-c', f'/tmp/{os.path.basename(script_path)}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        stdout_str, stderr_str = process.communicate(timeout=timeout_ms / 1000)
        success = process.returncode == 0
        error_message = None if success else f"Chroot script execution failed with return code {process.returncode}"
        return success, stdout_str, stderr_str, process.returncode, error_message
    except subprocess.TimeoutExpired:
        logger.error(f"Chroot execution timed out after {timeout_ms}ms")
        if process:
            process.kill()
            stdout_str, stderr_str = process.communicate()
        else:
            stdout_str, stderr_str = "", ""
        stderr_str = f"Chroot execution timed out after {timeout_ms}ms\n" + stderr_str
        error_message = stderr_str
        return False, stdout_str, stderr_str, 124, error_message
    except (subprocess.SubprocessError, OSError) as err:
        logger.error(f"Chroot execution failed: {err}")
        logger.warning(
            "Falling back to direct execution. This may pose security risks "
            "as the script will run without isolation."
        )
        from .direct import run_script_direct
        return await run_script_direct(script_path, timeout_ms)
    except Exception as err:
        logger.exception(f"Unexpected error during chroot execution: {err}")
        raise  # Re-raise unexpected errors
    finally:
        # Clean up chroot environment
        try:
            shutil.rmtree(chroot_dir, ignore_errors=True)
        except Exception as e:
            logger.error(f"Failed to clean up chroot environment: {e}")