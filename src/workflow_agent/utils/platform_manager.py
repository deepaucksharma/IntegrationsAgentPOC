"""Platform detection and management for workflow agent."""
import os
import sys
import platform
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from ..error.exceptions import PlatformError, ErrorContext

class PlatformType(Enum):
    """Supported platform types."""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"

class LinuxDistribution(Enum):
    """Supported Linux distributions."""
    UBUNTU = "ubuntu"
    DEBIAN = "debian"
    RHEL = "rhel"
    CENTOS = "centos"
    FEDORA = "fedora"
    SUSE = "suse"
    ARCH = "arch"
    UNKNOWN = "unknown"

class WindowsVersion(Enum):
    """Supported Windows versions."""
    WINDOWS_7 = "windows_7"
    WINDOWS_8 = "windows_8"
    WINDOWS_10 = "windows_10"
    WINDOWS_11 = "windows_11"
    WINDOWS_SERVER = "windows_server"
    UNKNOWN = "unknown"

class PlatformManager:
    """Manages platform-specific operations and detection."""
    
    def __init__(self):
        self._platform_type = self._detect_platform_type()
        self._linux_distribution = self._detect_linux_distribution() if self._platform_type == PlatformType.LINUX else None
        self._windows_version = self._detect_windows_version() if self._platform_type == PlatformType.WINDOWS else None
        self._package_managers = self._detect_package_managers()
        self._shell_info = self._detect_shell_info()
        self._path_separator = "\\" if self._platform_type == PlatformType.WINDOWS else "/"

    @property
    def platform_type(self) -> PlatformType:
        """Get the current platform type."""
        return self._platform_type

    @property
    def linux_distribution(self) -> Optional[LinuxDistribution]:
        """Get the Linux distribution if applicable."""
        return self._linux_distribution

    @property
    def windows_version(self) -> Optional[WindowsVersion]:
        """Get the Windows version if applicable."""
        return self._windows_version

    @property
    def package_managers(self) -> Dict[str, bool]:
        """Get available package managers."""
        return self._package_managers.copy()

    @property
    def shell_info(self) -> Dict[str, str]:
        """Get shell information."""
        return self._shell_info.copy()

    def get_script_extension(self) -> str:
        """Get the appropriate script extension for the current platform."""
        if self._platform_type == PlatformType.WINDOWS:
            return ".ps1"
        return ".sh"

    def get_path_separator(self) -> str:
        """Get the platform-specific path separator."""
        return self._path_separator

    def normalize_path(self, path: Union[str, Path]) -> Path:
        """Normalize a path for the current platform."""
        if isinstance(path, str):
            path = Path(path)
        return path.resolve()

    def get_temp_directory(self) -> Path:
        """Get platform-appropriate temporary directory."""
        return Path(tempfile.gettempdir())

    def get_script_header(self) -> List[str]:
        """Get platform-specific script header."""
        if self._platform_type == PlatformType.WINDOWS:
            return [
                "# Windows PowerShell script",
                "Set-StrictMode -Version Latest",
                "$ErrorActionPreference = \"Stop\"",
                "$ProgressPreference = \"SilentlyContinue\"",
                "trap { Write-Error $_; exit 1 }",
                ""
            ]
        return [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "IFS=$'\\n\\t'",
            "trap 'echo \"Error on line $LINENO: $BASH_COMMAND\"' ERR",
            ""
        ]

    def get_default_paths(self) -> Dict[str, Path]:
        """Get platform-specific default paths."""
        if self._platform_type == PlatformType.WINDOWS:
            program_files = Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
            return {
                "program_files": program_files,
                "config_dir": Path("C:\\ProgramData\\New Relic"),
                "log_dir": Path("C:\\ProgramData\\New Relic\\logs"),
                "temp_dir": Path(os.environ.get("TEMP", "C:\\Windows\\Temp"))
            }
        return {
            "program_files": Path("/opt/newrelic"),
            "config_dir": Path("/etc/newrelic"),
            "log_dir": Path("/var/log/newrelic"),
            "temp_dir": Path("/tmp")
        }

    def convert_path_for_platform(self, path: Union[str, Path], target_platform: Optional[PlatformType] = None) -> str:
        """Convert a path between platforms."""
        if target_platform is None:
            target_platform = self._platform_type
        
        path = Path(path)
        if target_platform == PlatformType.WINDOWS:
            return str(path).replace("/", "\\")
        return str(path).replace("\\", "/")

    def is_admin(self) -> bool:
        """Check if current process has admin/root privileges."""
        try:
            if self._platform_type == PlatformType.WINDOWS:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                return os.geteuid() == 0
        except Exception as e:
            context = ErrorContext(component="PlatformManager", operation="check_admin")
            raise PlatformError("Failed to check admin privileges", context=context, details={"error": str(e)})

    def _detect_platform_type(self) -> PlatformType:
        """Detect the current platform type."""
        system = platform.system().lower()
        if "windows" in system:
            return PlatformType.WINDOWS
        elif "linux" in system:
            return PlatformType.LINUX
        elif "darwin" in system:
            return PlatformType.MACOS
        return PlatformType.UNKNOWN

    def _detect_linux_distribution(self) -> LinuxDistribution:
        """Detect the Linux distribution."""
        try:
            import distro
            dist_id = distro.id().lower()
            for distribution in LinuxDistribution:
                if distribution.value in dist_id:
                    return distribution
        except ImportError:
            try:
                with open("/etc/os-release") as f:
                    content = f.read().lower()
                    for distribution in LinuxDistribution:
                        if distribution.value in content:
                            return distribution
            except Exception:
                pass
        return LinuxDistribution.UNKNOWN

    def _detect_windows_version(self) -> WindowsVersion:
        """Detect Windows version."""
        try:
            ver = sys.getwindowsversion()
            if ver.major == 10 and ver.build >= 22000:
                return WindowsVersion.WINDOWS_11
            elif ver.major == 10:
                return WindowsVersion.WINDOWS_10
            elif ver.major == 6:
                if ver.minor == 3:
                    return WindowsVersion.WINDOWS_8
                elif ver.minor == 1:
                    return WindowsVersion.WINDOWS_7
            
            # Check if server version
            if "server" in platform.win32_edition().lower():
                return WindowsVersion.WINDOWS_SERVER
        except Exception:
            pass
        return WindowsVersion.UNKNOWN

    def _detect_package_managers(self) -> Dict[str, bool]:
        """Detect available package managers."""
        package_managers = {
            "apt": False,
            "yum": False,
            "dnf": False,
            "zypper": False,
            "pacman": False,
            "brew": False,
            "choco": False,
            "scoop": False,
            "winget": False
        }
        
        for pm in package_managers:
            package_managers[pm] = shutil.which(pm) is not None
            
        # Special case for Windows package managers
        if self._platform_type == PlatformType.WINDOWS:
            package_managers["choco"] = os.path.exists("C:\\ProgramData\\chocolatey\\choco.exe")
            package_managers["winget"] = shutil.which("winget.exe") is not None
        
        return package_managers

    def _detect_shell_info(self) -> Dict[str, str]:
        """Detect shell information."""
        if self._platform_type == PlatformType.WINDOWS:
            powershell_path = shutil.which("powershell") or "powershell.exe"
            return {
                "type": "powershell",
                "path": powershell_path,
                "version": platform.version(),
                "supports_execution_policy": self._check_execution_policy_support()
            }
        
        shell_path = os.environ.get("SHELL", "/bin/bash")
        shell_type = os.path.basename(shell_path)
        return {
            "type": shell_type,
            "path": shell_path,
            "version": platform.version(),
            "supports_sudo": shutil.which("sudo") is not None
        }

    def _check_execution_policy_support(self) -> bool:
        """Check if PowerShell execution policy can be modified."""
        try:
            import subprocess
            result = subprocess.run(
                ["powershell", "-Command", "Get-ExecutionPolicy"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False

    def validate_platform_requirements(self, requirements: Dict[str, Any]) -> None:
        """Validate platform requirements."""
        if requirements.get("platform_type"):
            required_platform = PlatformType(requirements["platform_type"])
            if required_platform != self._platform_type:
                raise PlatformError(
                    f"Unsupported platform: {self._platform_type.value}. Required: {required_platform.value}",
                    details={"current_platform": self._platform_type.value, "required_platform": required_platform.value}
                )

        if requirements.get("package_managers"):
            missing_managers = [
                pm for pm in requirements["package_managers"]
                if pm not in self._package_managers or not self._package_managers[pm]
            ]
            if missing_managers:
                raise PlatformError(
                    f"Missing required package managers: {', '.join(missing_managers)}",
                    details={"missing_managers": missing_managers, "available_managers": self._package_managers}
                ) 