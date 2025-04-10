"""
Platform-specific verification implementations for more accurate system state validation.
"""
import logging
import os
import sys
import platform
import re
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
import asyncio

from ..core.state import WorkflowState, Change
from ..error.exceptions import VerificationError
from ..error.handler import ErrorHandler, handle_safely_async

logger = logging.getLogger(__name__)

class PlatformVerifier:
    """Base class for platform-specific verification."""
    
    @classmethod
    def create(cls) -> 'PlatformVerifier':
        """Factory method to create appropriate verifier for current platform."""
        system = platform.system().lower()
        
        if system == 'windows':
            return WindowsVerifier()
        elif system == 'linux':
            return LinuxVerifier()
        elif system == 'darwin':
            return MacOSVerifier()
        else:
            logger.warning(f"Unknown platform {system}, using generic verifier")
            return PlatformVerifier()
    
    async def verify_file_exists(self, path: str) -> bool:
        """Verify a file exists."""
        return os.path.isfile(path)
    
    async def verify_file_not_exists(self, path: str) -> bool:
        """Verify a file does not exist."""
        return not os.path.isfile(path)
    
    async def verify_directory_exists(self, path: str) -> bool:
        """Verify a directory exists."""
        return os.path.isdir(path)
    
    async def verify_directory_not_exists(self, path: str) -> bool:
        """Verify a directory does not exist."""
        return not os.path.isdir(path)
    
    async def verify_service_running(self, service_name: str) -> bool:
        """Verify a service is running."""
        logger.warning(f"Service verification not implemented for this platform: {service_name}")
        return False
    
    async def verify_service_not_running(self, service_name: str) -> bool:
        """Verify a service is not running."""
        logger.warning(f"Service verification not implemented for this platform: {service_name}")
        return False
    
    async def verify_package_installed(self, package_name: str) -> bool:
        """Verify a package is installed."""
        logger.warning(f"Package verification not implemented for this platform: {package_name}")
        return False
    
    async def verify_package_not_installed(self, package_name: str) -> bool:
        """Verify a package is not installed."""
        logger.warning(f"Package verification not implemented for this platform: {package_name}")
        return False
    
    async def verify_port_in_use(self, port: int) -> bool:
        """Verify a port is in use."""
        # This method works cross-platform using asyncio
        try:
            # Try to bind to the port
            sock = await asyncio.start_server(
                lambda reader, writer: None,
                '127.0.0.1',
                port
            )
            sock.close()
            await sock.wait_closed()
            # If we get here, the port is available (not in use)
            return False
        except OSError:
            # Port is in use
            return True
    
    async def verify_port_not_in_use(self, port: int) -> bool:
        """Verify a port is not in use."""
        return not await self.verify_port_in_use(port)
    
    async def verify_change(self, change: Change) -> Tuple[bool, Optional[str]]:
        """
        Verify a specific change based on its type.
        
        Args:
            change: Change to verify
            
        Returns:
            Tuple of (is_verified, message)
        """
        change_type = change.type.lower()
        target = change.target
        verified = False
        message = None
        
        try:
            if change_type == 'file_created':
                verified = await self.verify_file_exists(target)
                message = "File exists" if verified else "File does not exist"
            elif change_type == 'file_deleted':
                verified = await self.verify_file_not_exists(target)
                message = "File does not exist" if verified else "File still exists"
            elif change_type == 'directory_created':
                verified = await self.verify_directory_exists(target)
                message = "Directory exists" if verified else "Directory does not exist"
            elif change_type == 'directory_deleted':
                verified = await self.verify_directory_not_exists(target)
                message = "Directory does not exist" if verified else "Directory still exists"
            elif change_type == 'service_started':
                verified = await self.verify_service_running(target)
                message = "Service is running" if verified else "Service is not running"
            elif change_type == 'service_stopped':
                verified = await self.verify_service_not_running(target)
                message = "Service is not running" if verified else "Service is still running"
            elif change_type == 'package_installed':
                verified = await self.verify_package_installed(target)
                message = "Package is installed" if verified else "Package is not installed"
            elif change_type == 'package_removed':
                verified = await self.verify_package_not_installed(target)
                message = "Package is not installed" if verified else "Package is still installed"
            else:
                message = f"Unknown change type: {change_type}"
                verified = False
        except Exception as e:
            message = f"Verification error for {change_type} - {target}: {e}"
            logger.error(message, exc_info=True)
            verified = False
            
        return verified, message

class WindowsVerifier(PlatformVerifier):
    """Windows-specific verification methods."""
    
    async def verify_service_running(self, service_name: str) -> bool:
        """Verify a service is running on Windows."""
        try:
            # Use PowerShell to check service status
            cmd = f'powershell -Command "Get-Service -Name \'{service_name}\' -ErrorAction SilentlyContinue | Where-Object {{ $_.Status -eq \'Running\' }}"'
            result = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            # If we got output, the service exists and is running
            return bool(stdout.strip())
        except Exception as e:
            logger.error(f"Error checking Windows service {service_name}: {e}")
            return False
    
    async def verify_service_not_running(self, service_name: str) -> bool:
        """Verify a service is not running on Windows."""
        try:
            # Check if service exists
            cmd = f'powershell -Command "Get-Service -Name \'{service_name}\' -ErrorAction SilentlyContinue"'
            result = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            if not stdout.strip():
                # Service doesn't exist
                return True
                
            # Check if it's stopped
            cmd = f'powershell -Command "Get-Service -Name \'{service_name}\' -ErrorAction SilentlyContinue | Where-Object {{ $_.Status -ne \'Running\' }}"'
            result = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            # If we got output, the service exists but is not running
            return bool(stdout.strip())
        except Exception as e:
            logger.error(f"Error checking Windows service {service_name}: {e}")
            return False
    
    async def verify_package_installed(self, package_name: str) -> bool:
        """Verify a package is installed on Windows."""
        try:
            # Try several package managers
            
            # Check Chocolatey
            if shutil.which('choco'):
                cmd = f'choco list -lo -r | findstr /B /I "{package_name}"'
                result = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await result.communicate()
                if stdout.strip():
                    return True
            
            # Check WinGet
            if shutil.which('winget'):
                cmd = f'winget list | findstr /B /I "{package_name}"'
                result = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await result.communicate()
                if stdout.strip():
                    return True
            
            # Check installed programs with PowerShell
            cmd = f'powershell -Command "Get-ItemProperty HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Where-Object {{$_.DisplayName -like \'*{package_name}*\'}} | Select-Object DisplayName"'
            result = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            if stdout.strip():
                return True
                
            # Check 64-bit programs
            cmd = f'powershell -Command "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Where-Object {{$_.DisplayName -like \'*{package_name}*\'}} | Select-Object DisplayName"'
            result = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            return bool(stdout.strip())
        except Exception as e:
            logger.error(f"Error checking Windows package {package_name}: {e}")
            return False
            
    async def verify_package_not_installed(self, package_name: str) -> bool:
        """Verify a package is not installed on Windows."""
        return not await self.verify_package_installed(package_name)

class LinuxVerifier(PlatformVerifier):
    """Linux-specific verification methods."""
    
    async def verify_service_running(self, service_name: str) -> bool:
        """Verify a service is running on Linux."""
        try:
            # First try systemctl (systemd)
            if shutil.which('systemctl'):
                cmd = f'systemctl is-active --quiet {service_name}'
                result = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await result.communicate()
                
                # Exit code 0 means service is running
                if result.returncode == 0:
                    return True
            
            # Fall back to service command
            if shutil.which('service'):
                cmd = f'service {service_name} status'
                result = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await result.communicate()
                
                # Check for "running" in output
                output = stdout.decode().lower()
                return 'running' in output or 'started' in output
            
            # Last resort, check process list
            cmd = f'ps -A | grep -w {service_name}'
            result = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            # If we have output (excluding grep itself), service might be running
            output_lines = stdout.decode().strip().split('\n')
            for line in output_lines:
                if service_name in line and 'grep' not in line:
                    return True
                    
            return False
        except Exception as e:
            logger.error(f"Error checking Linux service {service_name}: {e}")
            return False
    
    async def verify_service_not_running(self, service_name: str) -> bool:
        """Verify a service is not running on Linux."""
        return not await self.verify_service_running(service_name)
    
    async def verify_package_installed(self, package_name: str) -> bool:
        """Verify a package is installed on Linux."""
        try:
            # Try different package managers
            
            # Debian/Ubuntu
            if shutil.which('dpkg'):
                cmd = f'dpkg -l {package_name} | grep -E "^ii"'
                result = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await result.communicate()
                if stdout.strip():
                    return True
            
            # Red Hat/CentOS
            if shutil.which('rpm'):
                cmd = f'rpm -q {package_name}'
                result = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await result.communicate()
                if result.returncode == 0:
                    return True
            
            # Arch Linux
            if shutil.which('pacman'):
                cmd = f'pacman -Q {package_name}'
                result = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await result.communicate()
                if result.returncode == 0:
                    return True
            
            # Snap packages
            if shutil.which('snap'):
                cmd = f'snap list {package_name}'
                result = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await result.communicate()
                if stdout.strip() and package_name in stdout.decode():
                    return True
                    
            return False
        except Exception as e:
            logger.error(f"Error checking Linux package {package_name}: {e}")
            return False
            
    async def verify_package_not_installed(self, package_name: str) -> bool:
        """Verify a package is not installed on Linux."""
        return not await self.verify_package_installed(package_name)

class MacOSVerifier(PlatformVerifier):
    """macOS-specific verification methods."""
    
    async def verify_service_running(self, service_name: str) -> bool:
        """Verify a service is running on macOS."""
        try:
            # Try launchctl
            cmd = f'launchctl list | grep {service_name}'
            result = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            # If we have output, the service might be running
            return bool(stdout.strip())
        except Exception as e:
            logger.error(f"Error checking macOS service {service_name}: {e}")
            return False
    
    async def verify_service_not_running(self, service_name: str) -> bool:
        """Verify a service is not running on macOS."""
        return not await self.verify_service_running(service_name)
    
    async def verify_package_installed(self, package_name: str) -> bool:
        """Verify a package is installed on macOS."""
        try:
            # Try Homebrew
            if shutil.which('brew'):
                cmd = f'brew list | grep {package_name}'
                result = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await result.communicate()
                if stdout.strip():
                    return True
            
            # Try macports
            if shutil.which('port'):
                cmd = f'port installed {package_name}'
                result = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await result.communicate()
                if stdout.strip() and 'None of the specified' not in stdout.decode():
                    return True
                    
            # For .app packages, check Applications directory
            if '/' not in package_name:
                app_paths = [
                    f'/Applications/{package_name}.app',
                    f'/Applications/Utilities/{package_name}.app',
                    f'{os.path.expanduser("~")}/Applications/{package_name}.app'
                ]
                
                for path in app_paths:
                    if os.path.exists(path) and os.path.isdir(path):
                        return True
                        
            return False
        except Exception as e:
            logger.error(f"Error checking macOS package {package_name}: {e}")
            return False
            
    async def verify_package_not_installed(self, package_name: str) -> bool:
        """Verify a package is not installed on macOS."""
        return not await self.verify_package_installed(package_name)
