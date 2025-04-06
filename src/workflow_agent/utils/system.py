"""
System utilities for gathering information about the environment.
"""
import os
import platform
import socket
import sys
import uuid
import json
from typing import Dict, Any

def get_system_context() -> Dict[str, Any]:
    """
    Get information about the system environment.
    
    Returns:
        Dictionary of system information
    """
    # Basic system info
    info = {
        "os": platform.system(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "is_windows": platform.system().lower() == "windows",
    }
    
    # Add OS-specific information
    if info["is_windows"]:
        try:
            import wmi
            c = wmi.WMI()
            
            # Windows version info
            os_info = c.Win32_OperatingSystem()[0]
            info["os_version"] = os_info.Version
            info["os_name"] = os_info.Caption
            
            # Processor info
            processor_info = c.Win32_Processor()[0]
            info["processor"] = processor_info.Name
            info["processor_cores"] = processor_info.NumberOfCores
            
        except ImportError:
            # WMI not available, use platform module
            info["os_version"] = platform.version()
            info["os_name"] = platform.win32_ver()[0]
    else:
        # Linux/Unix/Mac information
        if platform.system().lower() == "linux":
            # Try to get distribution info
            try:
                import distro
                info["os_name"] = distro.name(pretty=True)
                info["os_version"] = distro.version()
                info["os_codename"] = distro.codename()
            except ImportError:
                # Fall back to platform
                info["os_name"] = platform.system()
                info["os_version"] = platform.release()
        else:
            # macOS or other Unix
            info["os_name"] = platform.system()
            info["os_version"] = platform.release()
    
    # Get available package managers
    info["package_managers"] = detect_package_managers()
    
    # Get networking info
    try:
        info["ip_address"] = socket.gethostbyname(socket.gethostname())
    except Exception:
        info["ip_address"] = "127.0.0.1"
    
    return info

def detect_package_managers() -> Dict[str, bool]:
    """
    Detect available package managers on the system.
    
    Returns:
        Dictionary mapping package manager names to availability
    """
    package_managers = {
        "pip": False,
        "npm": False,
        "apt": False,
        "yum": False,
        "dnf": False,
        "pacman": False,
        "brew": False,
        "choco": False,
        "winget": False,
    }
    
    # Check if we're on Windows
    is_windows = platform.system().lower() == "windows"
    
    # Always check pip since we're running Python
    try:
        import subprocess
        subprocess.check_output([sys.executable, "-m", "pip", "--version"])
        package_managers["pip"] = True
    except Exception:
        pass
    
    if is_windows:
        # Check Windows package managers
        for cmd in ["choco", "winget"]:
            try:
                subprocess.check_output(["where", cmd], stderr=subprocess.DEVNULL)
                package_managers[cmd] = True
            except Exception:
                pass
    else:
        # Check Unix package managers
        for cmd in ["npm", "apt", "apt-get", "yum", "dnf", "pacman", "brew"]:
            try:
                subprocess.check_output(["which", cmd], stderr=subprocess.DEVNULL)
                
                # Map apt-get to apt
                if cmd == "apt-get":
                    package_managers["apt"] = True
                else:
                    package_managers[cmd] = True
            except Exception:
                pass
    
    return package_managers

def generate_execution_id() -> str:
    """
    Generate a unique execution ID.
    
    Returns:
        Unique execution ID
    """
    return str(uuid.uuid4())
