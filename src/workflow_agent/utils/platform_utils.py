"""
Platform detection utilities for consistent cross-platform behavior.
"""
import logging
import os
import sys
import platform
import re
import shutil
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)

# Platform types
PLATFORM_WINDOWS = "windows"
PLATFORM_LINUX = "linux"
PLATFORM_MACOS = "macos"
PLATFORM_UNKNOWN = "unknown"

def get_platform() -> str:
    """
    Get the current platform in a standardized way.
    
    Returns:
        Standardized platform string (windows, linux, macos, or unknown)
    """
    system = platform.system().lower()
    
    if system == 'windows':
        return PLATFORM_WINDOWS
    elif system == 'linux':
        return PLATFORM_LINUX
    elif system == 'darwin':
        return PLATFORM_MACOS
    else:
        logger.warning(f"Unknown platform detected: {system}")
        return PLATFORM_UNKNOWN

def is_windows() -> bool:
    """
    Check if the current platform is Windows.
    
    Returns:
        True if Windows, False otherwise
    """
    return get_platform() == PLATFORM_WINDOWS

def is_linux() -> bool:
    """
    Check if the current platform is Linux.
    
    Returns:
        True if Linux, False otherwise
    """
    return get_platform() == PLATFORM_LINUX

def is_macos() -> bool:
    """
    Check if the current platform is macOS.
    
    Returns:
        True if macOS, False otherwise
    """
    return get_platform() == PLATFORM_MACOS

def get_platform_info() -> Dict[str, Any]:
    """
    Get detailed platform information for system context.
    
    Returns:
        Dictionary with platform details
    """
    info = {
        "platform": get_platform(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "platform_machine": platform.machine(),
        "python_version": platform.python_version(),
        "is_64bit": sys.maxsize > 2**32,
    }
    
    # Add distro info for Linux
    if is_linux():
        try:
            import distro
            info["linux_distro"] = distro.id()
            info["linux_distro_version"] = distro.version()
            info["linux_distro_codename"] = distro.codename()
        except ImportError:
            logger.warning("distro package not available, Linux distribution info not collected")
            # Try older platform.linux_distribution() if available
            if hasattr(platform, 'linux_distribution'):
                linux_dist = platform.linux_distribution()
                info["linux_distro"] = linux_dist[0]
                info["linux_distro_version"] = linux_dist[1]
    
    # Add Windows-specific info
    if is_windows():
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
                info["windows_product_name"] = winreg.QueryValueEx(key, "ProductName")[0]
        except Exception as e:
            logger.warning(f"Could not get Windows product name: {e}")
    
    return info

def get_shell_info() -> Dict[str, Any]:
    """
    Get information about available shells and scripting environments.
    
    Returns:
        Dictionary with shell availability
    """
    info = {
        "has_bash": shutil.which("bash") is not None,
        "has_powershell": shutil.which("powershell") is not None,
        "has_pwsh": shutil.which("pwsh") is not None,  # PowerShell Core
        "has_cmd": shutil.which("cmd") is not None if is_windows() else False,
        "has_python": shutil.which("python") is not None or shutil.which("python3") is not None,
    }
    
    # Preferred shell for script execution
    if is_windows():
        if info["has_powershell"]:
            info["preferred_shell"] = "powershell"
        elif info["has_cmd"]:
            info["preferred_shell"] = "cmd"
        else:
            info["preferred_shell"] = "unknown"
    else:
        if info["has_bash"]:
            info["preferred_shell"] = "bash"
        elif shutil.which("sh") is not None:
            info["preferred_shell"] = "sh"
            info["has_sh"] = True
        else:
            info["preferred_shell"] = "unknown"
    
    return info

def get_platform_temp_dir() -> str:
    """
    Get the platform-specific temporary directory.
    
    Returns:
        Path to temporary directory
    """
    import tempfile
    return tempfile.gettempdir()

def get_platform_path_separator() -> str:
    """
    Get the platform-specific path separator.
    
    Returns:
        Path separator character
    """
    return os.path.sep

def normalize_path_for_platform(path: str) -> str:
    """
    Normalize a path for the current platform.
    
    Args:
        path: Path to normalize
        
    Returns:
        Normalized path for current platform
    """
    if is_windows():
        # Convert forward slashes to backslashes on Windows
        normalized = path.replace('/', '\\')
        # Handle UNC paths correctly
        if normalized.startswith('\\\\'):
            return normalized
        # Add drive letter if missing
        if not re.match(r'^[a-zA-Z]:', normalized):
            normalized = os.path.join(os.getcwd(), normalized)
        return normalized
    else:
        # Convert backslashes to forward slashes on Unix-like systems
        return path.replace('\\', '/')

def get_platform_line_ending() -> str:
    """
    Get the platform-specific line ending.
    
    Returns:
        Line ending sequence
    """
    if is_windows():
        return '\r\n'
    else:
        return '\n'

def get_environment_with_path(additional_paths: Optional[List[str]] = None) -> Dict[str, str]:
    """
    Get environment variables with updated PATH.
    
    Args:
        additional_paths: Optional list of paths to add to PATH
        
    Returns:
        Environment variables dictionary with updated PATH
    """
    env = os.environ.copy()
    
    if additional_paths:
        path_sep = os.pathsep  # ; on Windows, : on Unix-like
        path_var = "PATH"
        
        # For case-insensitive PATH on Windows
        if is_windows():
            for key in env:
                if key.upper() == "PATH":
                    path_var = key
                    break
                    
        current_path = env.get(path_var, "")
        updated_path = current_path
        
        # Add additional paths
        for path in additional_paths:
            if path not in current_path:
                if updated_path:
                    updated_path += path_sep
                updated_path += path
                
        env[path_var] = updated_path
        
    return env
