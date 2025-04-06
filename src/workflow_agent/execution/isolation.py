"""
Isolation strategies for script execution.
"""
import logging
import os
import tempfile
import asyncio
import platform
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from ..error.exceptions import ExecutionError
from ..core.state import OutputData
from ..config.configuration import WorkflowConfiguration

logger = logging.getLogger(__name__)

class IsolationStrategy(ABC):
    """Base class for isolation strategies."""
    
    def __init__(self, config: WorkflowConfiguration):
        """Initialize with configuration."""
        self.config = config
        
    @abstractmethod
    async def execute(
        self, 
        script_content: str,
        parameters: Dict[str, Any],
        working_dir: Optional[Path] = None
    ) -> OutputData:
        """
        Execute a script with isolation.
        
        Args:
            script_content: Content of the script to execute
            parameters: Parameters to pass to the script
            working_dir: Working directory for execution
            
        Returns:
            Output data with stdout, stderr, exit code
        """
        pass
        
    @abstractmethod
    def get_name(self) -> str:
        """Get the name of the isolation strategy."""
        pass

class DirectIsolation(IsolationStrategy):
    """Execute scripts directly on the host."""
    
    def __init__(self, config: WorkflowConfiguration):
        """Initialize direct isolation."""
        super().__init__(config)
        
    async def execute(
        self, 
        script_content: str,
        parameters: Dict[str, Any],
        working_dir: Optional[Path] = None
    ) -> OutputData:
        """Execute a script directly on the host."""
        is_windows = platform.system().lower() == 'windows'
        
        # Create a temporary script file
        with tempfile.NamedTemporaryFile(
            suffix='.ps1' if is_windows else '.sh',
            delete=False,
            mode='w+'
        ) as script_file:
            script_path = script_file.name
            script_file.write(script_content)
            
        try:
            # Make the script executable on Unix-like systems
            if not is_windows:
                os.chmod(script_path, 0o755)
                
            # Execute the script
            if is_windows:
                cmd = f'powershell.exe -ExecutionPolicy Bypass -File "{script_path}"'
            else:
                cmd = f'bash "{script_path}"'
                
            logger.info(f"Executing script with command: {cmd}")
            
            # Track execution time
            import time
            start_time = time.time()
            
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.execution_timeout
                )
            except asyncio.TimeoutError:
                if process.returncode is None:
                    process.terminate()
                    return OutputData(
                        stdout="",
                        stderr="Script execution timed out",
                        exit_code=124,
                        duration=time.time() - start_time
                    )
            
            # Convert stdout and stderr to strings
            stdout_str = stdout.decode() if stdout else ""
            stderr_str = stderr.decode() if stderr else ""
            
            duration = time.time() - start_time
            
            # Parse output for changes
            changes = self._parse_changes(stdout_str)
            
            # Create output data
            output = OutputData(
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=process.returncode or 0,
                duration=duration
            )
            
            # Log result
            if process.returncode == 0:
                logger.info(f"Script executed successfully in {duration:.2f}s")
            else:
                logger.error(f"Script execution failed with exit code {process.returncode}")
                if stderr_str:
                    logger.error(f"Error output: {stderr_str}")
                    
            return output
            
        finally:
            # Clean up temporary script file
            try:
                os.unlink(script_path)
            except Exception as e:
                logger.warning(f"Failed to remove temporary script: {e}")
    
    def _parse_changes(self, output: str) -> List[Dict[str, Any]]:
        """Parse script output for changes."""
        changes = []
        
        # Look for standardized change indicators
        import re
        
        # Package installations
        for match in re.finditer(r"CHANGE:PACKAGE_INSTALLED:(\S+)", output):
            package_name = match.group(1)
            changes.append({
                "type": "package_installed",
                "target": package_name,
                "revertible": True
            })
            
        # File creations
        for match in re.finditer(r"CHANGE:FILE_CREATED:(\S+)", output):
            file_path = match.group(1)
            changes.append({
                "type": "file_created",
                "target": file_path,
                "revertible": True
            })
            
        # Directory creations
        for match in re.finditer(r"CHANGE:DIRECTORY_CREATED:(\S+)", output):
            dir_path = match.group(1)
            changes.append({
                "type": "directory_created",
                "target": dir_path,
                "revertible": True
            })
            
        # Service operations
        for match in re.finditer(r"CHANGE:SERVICE_(\w+):(\S+)", output):
            operation = match.group(1).lower()
            service_name = match.group(2)
            changes.append({
                "type": f"service_{operation}",
                "target": service_name,
                "revertible": operation in ["started", "enabled"]
            })
            
        return changes
        
    def get_name(self) -> str:
        """Get isolation name."""
        return "direct"

class DockerIsolation(IsolationStrategy):
    """Execute scripts in Docker containers."""
    
    def __init__(self, config: WorkflowConfiguration):
        """Initialize Docker isolation."""
        super().__init__(config)
        self.image = config.docker_image if hasattr(config, 'docker_image') else "debian:stable-slim"
        self.memory_limit = "512m"
        self.cpu_limit = "1.0"
        
    async def execute(
        self, 
        script_content: str,
        parameters: Dict[str, Any],
        working_dir: Optional[Path] = None
    ) -> OutputData:
        """Execute a script in a Docker container."""
        # Check if Docker is available
        if not await self._is_docker_available():
            logger.error("Docker is not available. Cannot use Docker isolation.")
            raise ExecutionError("Docker is not available for script isolation")
            
        # Create a temporary directory for the script
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write the script to the temporary directory
            script_path = Path(temp_dir) / "script.sh"
            with open(script_path, "w") as f:
                f.write(script_content)
                
            # Make the script executable
            os.chmod(script_path, 0o755)
            
            # Create a temporary file for the output
            output_path = Path(temp_dir) / "output.txt"
            error_path = Path(temp_dir) / "error.txt"
            
            # Build the Docker command
            container_name = f"workflow-agent-{parameters.get('execution_id', 'unknown')}"
            
            docker_cmd = (
                f"docker run --rm --name {container_name} "
                f"--memory={self.memory_limit} --cpus={self.cpu_limit} "
                f"-v {script_path}:/script.sh:ro "
                f"{self.image} /script.sh"
            )
            
            # Execute the Docker command
            import time
            start_time = time.time()
            
            try:
                process = await asyncio.create_subprocess_shell(
                    docker_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=working_dir
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.config.execution_timeout
                    )
                except asyncio.TimeoutError:
                    # Kill the container if it's still running
                    await asyncio.create_subprocess_shell(
                        f"docker kill {container_name}",
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL
                    )
                    
                    return OutputData(
                        stdout="",
                        stderr="Docker execution timed out",
                        exit_code=124,
                        duration=time.time() - start_time
                    )
                
                # Convert stdout and stderr to strings
                stdout_str = stdout.decode() if stdout else ""
                stderr_str = stderr.decode() if stderr else ""
                
                duration = time.time() - start_time
                
                # Create output data
                output = OutputData(
                    stdout=stdout_str,
                    stderr=stderr_str,
                    exit_code=process.returncode or 0,
                    duration=duration
                )
                
                # Log result
                if process.returncode == 0:
                    logger.info(f"Docker script executed successfully in {duration:.2f}s")
                else:
                    logger.error(f"Docker script execution failed with exit code {process.returncode}")
                    
                return output
                
            except Exception as e:
                logger.error(f"Error executing Docker command: {e}")
                return OutputData(
                    stdout="",
                    stderr=f"Error executing Docker command: {str(e)}",
                    exit_code=1,
                    duration=time.time() - start_time
                )
    
    async def _is_docker_available(self) -> bool:
        """Check if Docker is available."""
        try:
            process = await asyncio.create_subprocess_shell(
                "docker --version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await process.communicate()
            return process.returncode == 0 and stdout
        except Exception:
            return False
            
    def get_name(self) -> str:
        """Get isolation name."""
        return "docker"

class IsolationFactory:
    """Factory for creating isolation strategy instances."""
    
    @staticmethod
    def create(isolation_method: str, config: WorkflowConfiguration) -> IsolationStrategy:
        """
        Create an isolation strategy.
        
        Args:
            isolation_method: Type of isolation to use
            config: Workflow configuration
            
        Returns:
            Isolation strategy instance
            
        Raises:
            ExecutionError: If the isolation method is not supported
        """
        if isolation_method.lower() == "docker":
            return DockerIsolation(config)
        elif isolation_method.lower() == "direct":
            return DirectIsolation(config)
        else:
            logger.error(f"Unsupported isolation method: {isolation_method}")
            raise ExecutionError(f"Unsupported isolation method: {isolation_method}")
