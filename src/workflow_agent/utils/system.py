# src/workflow_agent/utils/system.py
import platform
import shutil
import os
import socket
import logging
import json
import urllib.request
import subprocess
from typing import Dict, Any, Optional, List
import psutil

logger = logging.getLogger(__name__)

def get_system_context() -> Dict[str, Any]:
    """
    Returns a dictionary of system context information.
    
    This collects detailed information about the execution environment
    including OS details, available tools, hardware resources, etc.
    
    Returns:
        Dictionary containing system context information
    """
    context = {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "hostname": socket.gethostname()
        },
        "docker_available": shutil.which("docker") is not None,
        "package_managers": _get_package_managers(),
        "user": {
            "username": os.getenv("USER", os.getenv("USERNAME", "unknown")),
            "uid": os.getuid() if hasattr(os, "getuid") else None,
            "home": os.path.expanduser("~")
        },
        "hardware": _get_hardware_info(),
        "tools": _get_available_tools(),
        "environment": _get_filtered_env_vars()
    }
    
    # Add cloud provider information if available
    try:
        cloud_info = _detect_cloud_provider()
        if cloud_info:
            context["cloud"] = cloud_info
    except Exception as e:
        logger.debug(f"Error detecting cloud provider: {e}")
    
    return context

def _get_package_managers() -> Dict[str, bool]:
    """Get available package managers on the system."""
    package_managers = {
        "apt": shutil.which("apt-get") is not None,
        "yum": shutil.which("yum") is not None,
        "dnf": shutil.which("dnf") is not None,
        "pacman": shutil.which("pacman") is not None,
        "brew": shutil.which("brew") is not None,
        "pip": shutil.which("pip") is not None,
        "npm": shutil.which("npm") is not None
    }
    
    # Determine primary package manager
    if platform.system() == "Linux":
        if os.path.exists("/etc/debian_version") or package_managers["apt"]:
            package_managers["primary"] = "apt"
        elif os.path.exists("/etc/fedora-release") or package_managers["dnf"]:
            package_managers["primary"] = "dnf"
        elif os.path.exists("/etc/redhat-release") or package_managers["yum"]:
            package_managers["primary"] = "yum"
        elif os.path.exists("/etc/arch-release") or package_managers["pacman"]:
            package_managers["primary"] = "pacman"
        else:
            package_managers["primary"] = "unknown"
    elif platform.system() == "Darwin":
        package_managers["primary"] = "brew" if package_managers["brew"] else "unknown"
    else:
        package_managers["primary"] = "unknown"
    
    return package_managers

def _get_hardware_info() -> Dict[str, Any]:
    """Get hardware-related information."""
    try:
        return {
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
            "disk_total": psutil.disk_usage('/').total,
            "disk_free": psutil.disk_usage('/').free
        }
    except Exception as e:
        logger.debug(f"Error getting hardware info: {e}")
        return {"error": str(e)}

def _get_available_tools() -> Dict[str, bool]:
    """Check for common tools used in integrations."""
    tools = {
        "curl": shutil.which("curl") is not None,
        "wget": shutil.which("wget") is not None,
        "git": shutil.which("git") is not None,
        "aws": shutil.which("aws") is not None,
        "az": shutil.which("az") is not None,
        "gcloud": shutil.which("gcloud") is not None,
        "terraform": shutil.which("terraform") is not None,
        "ansible": shutil.which("ansible") is not None,
        "docker-compose": shutil.which("docker-compose") is not None,
        "python3": shutil.which("python3") is not None,
        "node": shutil.which("node") is not None,
        "psql": shutil.which("psql") is not None,
        "mysql": shutil.which("mysql") is not None
    }
    return tools

def _get_filtered_env_vars() -> Dict[str, str]:
    """Get a filtered subset of environment variables."""
    safe_vars = [
        "PATH", "LANG", "LC_ALL", "TERM", "SHELL", "EDITOR", 
        "SUDO_USER", "PWD", "HOME", "USER", "LOGNAME", 
        "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP", "DISPLAY"
    ]
    result = {}
    for var in safe_vars:
        if var in os.environ:
            result[var] = os.environ[var]
    return result

def _detect_cloud_provider() -> Optional[Dict[str, Any]]:
    """Attempt to detect cloud provider for the current environment."""
    # Check for AWS
    try:
        # Try to access AWS metadata service
        req = urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/instance-id",
            headers={"Accept": "application/json"},
            method="GET"
        )
        req.timeout = 1
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                return {"provider": "aws", "instance_id": response.read().decode('utf-8')}
    except:
        pass
    
    # Check for GCP
    try:
        req = urllib.request.Request(
            "http://metadata.google.internal/computeMetadata/v1/instance/id",
            headers={"Metadata-Flavor": "Google"},
            method="GET"
        )
        req.timeout = 1
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                return {"provider": "gcp", "instance_id": response.read().decode('utf-8')}
    except:
        pass
    
    # Check for Azure
    try:
        req = urllib.request.Request(
            "http://169.254.169.254/metadata/instance?api-version=2021-02-01",
            headers={"Metadata": "true"},
            method="GET"
        )
        req.timeout = 1
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                return {"provider": "azure", "instance_id": data.get("compute", {}).get("vmId")}
    except:
        pass
    
    return None

def execute_command(
    command: List[str], 
    timeout: Optional[int] = None,
    capture_output: bool = True
) -> Dict[str, Any]:
    """
    Execute a system command safely.
    
    Args:
        command: Command list to execute
        timeout: Optional timeout in seconds
        capture_output: Whether to capture stdout/stderr
    
    Returns:
        Dictionary with command execution results
    """
    try:
        result = subprocess.run(
            command,
            timeout=timeout,
            capture_output=capture_output,
            text=True,
            check=False
        )
        
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout if capture_output else "",
            "stderr": result.stderr if capture_output else "",
            "command": " ".join(command)
        }
    except subprocess.TimeoutExpired:
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