"""
Secure subprocess execution utilities to prevent command injection.
"""
import logging
import os
import subprocess
import shlex
import platform
import asyncio
from typing import Dict, Any, Optional, List, Union, Tuple

logger = logging.getLogger(__name__)

def secure_join_args(args: List[str]) -> str:
    """
    Securely join command arguments to prevent command injection.
    
    Args:
        args: List of command arguments
        
    Returns:
        Joined command as string
    """
    if platform.system() == 'Windows':
        # Use list2cmdline for Windows
        return subprocess.list2cmdline(args)
    else:
        # Use shlex.quote for Unix-like systems
        return ' '.join(shlex.quote(arg) for arg in args)

def secure_shell_execute(
    command: Union[str, List[str]], 
    shell: bool = False, 
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    timeout: Optional[int] = None
) -> Tuple[int, str, str]:
    """
    Execute a shell command securely.
    
    Args:
        command: Command to execute as string or list of arguments
        shell: Whether to use shell execution
        env: Environment variables
        cwd: Working directory
        timeout: Command timeout in seconds
        
    Returns:
        Tuple of (exit_code, stdout, stderr)
        
    Raises:
        subprocess.TimeoutExpired: If command times out
        subprocess.SubprocessError: If command execution fails
    """
    # Prepare command
    if isinstance(command, list):
        cmd_args = command
        cmd_str = secure_join_args(command)
    else:
        if shell:
            cmd_args = command
            cmd_str = command
        else:
            # Split command into arguments
            cmd_args = shlex.split(command)
            cmd_str = command
            
    logger.debug(f"Executing command: {cmd_str}")
    
    try:
        # Create full environment by extending current environment
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
            
        # Execute command
        result = subprocess.run(
            cmd_args,
            shell=shell,
            env=full_env,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
        
        if exit_code != 0:
            logger.warning(f"Command exited with non-zero code {exit_code}: {cmd_str}")
            logger.debug(f"Command stderr: {stderr}")
        
        return exit_code, stdout, stderr
        
    except subprocess.TimeoutExpired as e:
        logger.error(f"Command timed out after {timeout} seconds: {cmd_str}")
        return 124, "", f"Command timed out after {timeout} seconds"
        
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        return 1, "", str(e)

async def async_secure_shell_execute(
    command: Union[str, List[str]], 
    shell: bool = False, 
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    timeout: Optional[int] = None
) -> Tuple[int, str, str]:
    """
    Execute a shell command securely with asyncio.
    
    Args:
        command: Command to execute as string or list of arguments
        shell: Whether to use shell execution
        env: Environment variables
        cwd: Working directory
        timeout: Command timeout in seconds
        
    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    # Prepare command
    if isinstance(command, list):
        cmd_str = secure_join_args(command)
        if shell:
            cmd = cmd_str
        else:
            cmd = command
    else:
        cmd_str = command
        cmd = command
        
    logger.debug(f"Executing async command: {cmd_str}")
    
    # Create full environment by extending current environment
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    
    try:
        # Execute command
        if shell:
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env,
                cwd=cwd
            )
        else:
            if isinstance(cmd, str):
                cmd = shlex.split(cmd)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env,
                cwd=cwd
            )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=timeout
            )
        except asyncio.TimeoutError:
            # Kill the process if it times out
            try:
                process.terminate()
                await asyncio.sleep(0.5)
                process.kill()
            except ProcessLookupError:
                pass
                
            logger.error(f"Command timed out after {timeout} seconds: {cmd_str}")
            return 124, "", f"Command timed out after {timeout} seconds"
            
        stdout_str = stdout.decode('utf-8', errors='replace')
        stderr_str = stderr.decode('utf-8', errors='replace')
        exit_code = process.returncode
        
        if exit_code != 0:
            logger.warning(f"Command exited with non-zero code {exit_code}: {cmd_str}")
            logger.debug(f"Command stderr: {stderr_str}")
        
        return exit_code, stdout_str, stderr_str
        
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        return 1, "", str(e)

def is_command_available(command: str) -> bool:
    """
    Check if a command is available in the system.
    
    Args:
        command: Command to check
        
    Returns:
        True if command is available, False otherwise
    """
    try:
        import shutil
        return shutil.which(command) is not None
    except ImportError:
        try:
            if platform.system() == 'Windows':
                cmd = f'where {command}'
            else:
                cmd = f'which {command}'
                
            process = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            return process.returncode == 0
        except Exception:
            return False
