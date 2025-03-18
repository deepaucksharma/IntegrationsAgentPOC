import os
import platform
import socket
import logging
import psutil
import shutil
import asyncio
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

def get_system_context() -> Dict[str, Any]:
    """
    Gather basic system context data for environment-based script customization.
    """
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
            "uid": os.getuid() if hasattr(os, "getuid") else -1,
            "home": os.path.expanduser("~")
        },
        "hardware": {
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available
        }
    }

async def execute_command(command: List[str], timeout: Optional[int] = None, capture_output: bool = True) -> Dict[str, Any]:
    """
    Execute a shell command asynchronously with optional timeout and output capture.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE if capture_output else None,
            stderr=asyncio.subprocess.PIPE if capture_output else None
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "success": proc.returncode == 0,
                "return_code": proc.returncode,
                "stdout": stdout.decode("utf-8") if stdout else "",
                "stderr": stderr.decode("utf-8") if stderr else "",
                "command": " ".join(command)
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"success": False, "return_code": None, "command": " ".join(command), "error": f"Command timeout after {timeout}s"}
    except Exception as e:
        return {"success": False, "return_code": None, "command": " ".join(command), "error": str(e)}