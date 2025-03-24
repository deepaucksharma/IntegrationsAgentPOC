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
    """Get system context information."""
    try:
        system = platform.system().lower()
        context = {
            "platform": {
                "system": system,
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor()
            },
            "environment": {
                "python_version": platform.python_version(),
                "path": os.environ.get("PATH", ""),
                "home": os.environ.get("HOME", os.environ.get("USERPROFILE", ""))
            }
        }

        # Add system-specific information
        if system == "windows":
            context["platform"].update({
                "distribution": "windows",
                "release": platform.release(),
                "edition": platform.win32_edition() if hasattr(platform, "win32_edition") else ""
            })
        elif system == "linux":
            # Try to get Linux distribution info
            try:
                import distro
                context["platform"].update({
                    "distribution": distro.id(),
                    "distribution_version": distro.version(),
                    "codename": distro.codename()
                })
            except ImportError:
                # Fallback to basic Linux info
                context["platform"].update({
                    "distribution": "unknown",
                    "distribution_version": "",
                    "codename": ""
                })

        return context
    except Exception as e:
        # Return basic info on error
        return {
            "platform": {
                "system": platform.system().lower(),
                "version": platform.version()
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