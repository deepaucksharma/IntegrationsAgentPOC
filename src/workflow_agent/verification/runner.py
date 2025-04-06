"""
Verification runner for executing verification steps.
"""
import logging
import asyncio
import tempfile
import os
from typing import Dict, Any, Optional

from ..core.state import WorkflowState
from ..error.exceptions import VerificationError
from ..config.configuration import WorkflowConfiguration
from ..execution.isolation import IsolationFactory

logger = logging.getLogger(__name__)

class VerificationRunner:
    """Executes verification steps."""
    
    def __init__(self, config: WorkflowConfiguration):
        """
        Initialize verification runner with configuration.
        
        Args:
            config: Workflow configuration
        """
        self.config = config
        
    async def run_step(self, step: Any, state: WorkflowState) -> Dict[str, Any]:
        """
        Run a verification step.
        
        Args:
            step: Verification step to run
            state: Current workflow state
            
        Returns:
            Dictionary with verification result
        """
        logger.info(f"Running verification step: {step.name}")
        
        # Get isolation strategy
        isolation_method = state.isolation_method or self.config.isolation_method
        isolation = IsolationFactory.create(isolation_method, self.config)
        
        try:
            # Execute the script
            output = await isolation.execute(
                step.script,
                state.parameters,
                None  # Use default working directory
            )
            
            # Check results
            stdout = output.stdout.strip()
            stderr = output.stderr.strip()
            exit_code = output.exit_code
            
            if exit_code != 0:
                logger.error(f"Verification step '{step.name}' failed with exit code {exit_code}")
                return {
                    "success": False,
                    "error": f"Exit code {exit_code}. {stderr or stdout}",
                    "output": stdout,
                    "step": step.name
                }
                
            # Check expected result if provided
            if step.expected_result and step.expected_result not in stdout:
                logger.error(f"Verification step '{step.name}' failed: expected result not found")
                return {
                    "success": False,
                    "error": f"Expected result not found: {step.expected_result}",
                    "output": stdout,
                    "step": step.name
                }
                
            logger.info(f"Verification step '{step.name}' passed")
            return {
                "success": True,
                "output": stdout,
                "step": step.name
            }
            
        except Exception as e:
            logger.error(f"Error executing verification step '{step.name}': {e}")
            return {
                "success": False,
                "error": str(e),
                "step": step.name
            }

class DirectVerifier:
    """Performs direct verification without scripts."""
    
    def __init__(self, config: WorkflowConfiguration):
        """
        Initialize direct verifier.
        
        Args:
            config: Workflow configuration
        """
        self.config = config
        
    async def verify_file_exists(self, file_path: str) -> Dict[str, Any]:
        """Verify that a file exists."""
        exists = os.path.isfile(file_path)
        return {
            "success": exists,
            "error": "" if exists else f"File not found: {file_path}"
        }
        
    async def verify_directory_exists(self, dir_path: str) -> Dict[str, Any]:
        """Verify that a directory exists."""
        exists = os.path.isdir(dir_path)
        return {
            "success": exists,
            "error": "" if exists else f"Directory not found: {dir_path}"
        }
        
    async def verify_process_running(self, process_name: str) -> Dict[str, Any]:
        """Verify that a process is running."""
        import psutil
        
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == process_name:
                return {
                    "success": True,
                    "error": ""
                }
                
        return {
            "success": False,
            "error": f"Process not running: {process_name}"
        }
        
    async def verify_port_listening(self, port: int) -> Dict[str, Any]:
        """Verify that a port is open and listening."""
        import socket
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        
        if result == 0:
            return {
                "success": True,
                "error": ""
            }
        else:
            return {
                "success": False,
                "error": f"Port {port} is not listening"
            }
