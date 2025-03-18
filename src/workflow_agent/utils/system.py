"""System utility functions for workflow agent."""
import os
import platform
import socket
import subprocess
import logging
import psutil
import shutil
import asyncio
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

def get_system_context() -> Dict[str, Any]:
    """Get information about the current system environment."""
    return {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "hostname": socket.gethostname()
        },
        "docker_available": shutil.which("docker") is not None,
        "package_managers": {
            "apt": shutil.which("apt-get") is not None,
            "yum": shutil.which("yum") is not None,
            "dnf": shutil.which("dnf") is not None,
            "pacman": shutil.which("pacman") is not None,
            "brew": shutil.which("brew") is not None
        },
        "user": {
            "username": os.getenv("USER", os.getenv("USERNAME", "unknown")),
            "uid": os.getuid() if hasattr(os, "getuid") else None,
            "home": os.path.expanduser("~")
        },
        "hardware": {
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available
        }
    }

async def execute_command(
    command: List[str],
    timeout: Optional[int] = None,
    capture_output: bool = True
) -> Dict[str, Any]:
    """Execute a system command safely."""
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE if capture_output else None,
            stderr=asyncio.subprocess.PIPE if capture_output else None
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            return {
                "success": process.returncode == 0,
                "return_code": process.returncode,
                "stdout": stdout.decode('utf-8') if stdout else "",
                "stderr": stderr.decode('utf-8') if stderr else "",
                "command": " ".join(command)
            }
        except asyncio.TimeoutError:
            process.kill()
            return {
                "success": False,
                "timeout": True,
                "return_code": None,
                "command": " ".join(command),
                "error": f"Command timeout after {timeout}s"
            }
    except Exception as e:
        return {
            "success": False,
            "return_code": None,
            "command": " ".join(command),
            "error": str(e)
        }