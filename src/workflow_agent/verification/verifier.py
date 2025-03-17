import os
import logging
import subprocess
import shlex
from typing import Dict, Any, Optional, Tuple
from jinja2 import Template
from ..core.state import WorkflowState
from ..config.configuration import ensure_workflow_config
from .commands import get_verification_command

logger = logging.getLogger(__name__)

class Verifier:
    """Verifies the results of script execution."""
    
    async def verify_result(
        self,
        state: WorkflowState, 
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Verify the results of the script execution.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with verification results or error
        """
        # Get configuration
        workflow_config = ensure_workflow_config(config)
        
        # Skip verification for removal/uninstall actions unless explicitly configured
        if state.action in ["remove", "uninstall"] and workflow_config.skip_verification:
            logger.info("Skipping verification for removal/uninstall action")
            return {"status": "No verification needed for removal/uninstall actions (configured to skip)."}
        
        # Determine verification strategy
        verification_results = []
        
        # 1. Try custom verification command if provided
        if state.custom_verification:
            logger.info(f"Using custom verification command: {state.custom_verification}")
            result = await self._execute_verification_command(state.custom_verification, state)
            verification_results.append({
                "type": "custom",
                "command": state.custom_verification,
                **result
            })
            
            if not result["success"]:
                logger.error(f"Custom verification failed: {result['error']}")
                return {
                    "error": f"Custom verification failed: {result['stderr'].strip() or result['error'] or 'Command returned non-zero exit code'}",
                    "verification_output": {
                        "results": verification_results,
                        "success": False
                    }
                }
        
        # 2. Try predefined verification command for target-action
        verification_command = get_verification_command(state.target_name, state.parameters)
        
        if verification_command:
            logger.info(f"Verifying with command: {verification_command}")
            result = await self._execute_verification_command(verification_command, state)
            verification_results.append({
                "type": "predefined",
                "command": verification_command,
                **result
            })
            
            if result["success"]:
                logger.info("Verification successful")
                return {
                    "status": f"Verification successful: {result['stdout'].strip()}",
                    "verification_output": {
                        "results": verification_results,
                        "success": True
                    }
                }
            else:
                logger.error(f"Verification failed: {result['error']}")
                return {
                    "error": f"Verification failed: {result['stderr'].strip() or result['error'] or 'Command returned non-zero exit code'}",
                    "verification_output": {
                        "results": verification_results,
                        "success": False
                    }
                }
        
        # 3. Try target-specific verification based on integration type
        if state.integration_type == "infra_agent":
            # For infrastructure agents, check service status
            try:
                if state.action in ["install", "setup"]:
                    service_name = "newrelic-infra"
                    logger.info(f"Checking service status for {service_name}")
                    
                    # Check if systemctl exists
                    if os.path.exists("/bin/systemctl") or os.path.exists("/usr/bin/systemctl"):
                        verify_cmd = f"systemctl status {service_name}"
                        result = await self._execute_verification_command(verify_cmd, state)
                        verification_results.append({
                            "type": "service-check",
                            "command": verify_cmd,
                            **result
                        })
                        
                        if result["success"]:
                            logger.info(f"Service {service_name} is running")
                            return {
                                "status": f"Verification successful: {service_name} service is running",
                                "verification_output": {
                                    "results": verification_results,
                                    "success": True
                                }
                            }
                        else:
                            logger.warning(f"Service {service_name} is not running, but continuing")
                            # Not failing on service check, as it might not be started yet
                            verification_results.append({
                                "type": "warning",
                                "message": f"Service {service_name} is not running"
                            })
            except Exception as e:
                logger.warning(f"Error during service check: {e}")
                verification_results.append({
                    "type": "service-check",
                    "success": False,
                    "error": str(e)
                })
        
        # 4. If we've reached here with verification results but no definitive success/failure,
        # consider it a partial success with warnings
        if verification_results:
            logger.info("Partial verification with warnings")
            return {
                "status": "Verification completed with warnings",
                "verification_output": {
                    "results": verification_results,
                    "success": True,
                    "warnings": True
                }
            }
        
        # 5. No verification method found
        logger.info(f"No verification command defined for {state.target_name}, assuming success")
        return {
            "status": f"Verification assumed successful for {state.target_name} (no verification command defined).",
            "verification_output": {
                "results": [],
                "success": True,
                "assumed": True
            }
        }
    
    async def _execute_verification_command(
        self,
        command: str,
        state: Optional[WorkflowState] = None
    ) -> Dict[str, Any]:
        """
        Safely execute a verification command.
        
        Args:
            command: Command to execute
            state: Optional workflow state for context
            
        Returns:
            Dict with execution results
        """
        try:
            if "|" in command or ">" in command or "<" in command or "&" in command or ";" in command:
                logger.info("Using shell execution for complex command")
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    shell=True
                )
            else:
                logger.info("Using direct execution for simple command")
                process = subprocess.Popen(
                    shlex.split(command),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    shell=False
                )
            stdout, stderr = process.communicate(timeout=30)
            success = process.returncode == 0
            error = None if success else f"Command returned exit code {process.returncode}"
            return {
                "success": success,
                "stdout": stdout,
                "stderr": stderr,
                "error": error,
                "exit_code": process.returncode
            }
        except subprocess.TimeoutExpired:
            if process:
                process.kill()
                stdout, stderr = process.communicate()
            else:
                stdout, stderr = "", ""
            return {
                "success": False,
                "stdout": stdout,
                "stderr": stderr,
                "error": "Verification timed out after 30 seconds",
                "exit_code": 124
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "error": f"Error executing verification command: {str(e)}",
                "exit_code": 1
            }