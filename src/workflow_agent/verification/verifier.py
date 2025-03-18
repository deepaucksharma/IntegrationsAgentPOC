import os
import uuid
import tempfile
import subprocess
import logging
import json
import asyncio
import re
import time
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path
from ..core.state import WorkflowState
from ..config.configuration import verification_commands
from .commands import get_verification_command
from .strategies import (
    get_verification_strategy,
    SERVICE_CHECK,
    HTTP_CHECK,
    LOG_CHECK,
    PROCESS_CHECK,
    API_CHECK
)

logger = logging.getLogger(__name__)

class Verifier:
    """Enhanced verifier for checking integration success."""
    
    def __init__(self):
        """Initialize the verifier."""
        self.verification_history = {}
    
    async def cleanup(self) -> None:
        """Clean up verification resources."""
        try:
            self.verification_history.clear()
            logger.info("Verification resources cleaned up")
        except Exception as e:
            logger.error(f"Error during verification cleanup: {e}")
            # Don't re-raise as cleanup should be best-effort
    
    async def verify_result(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Verify the execution results.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with verification results
        """
        if state.error:
            logger.info(f"Skipping verification due to previous error: {state.error}")
            return {"verification_status": "skipped", "verification_output": None}
        
        logger.info(f"Verifying results for {state.action} on {state.target_name}")
        
        # Use multi-strategy verification
        results = await self._multi_strategy_verification(state, config)
        
        # Store verification history
        verification_id = str(uuid.uuid4())
        self.verification_history[verification_id] = {
            "target": state.target_name,
            "action": state.action,
            "timestamp": time.time(),
            "results": results
        }
        
        # Determine overall success
        if results["success"]:
            logger.info("Verification successful")
            return {
                "verification_status": "success",
                "verification_output": results,
                "verification_id": verification_id
            }
        else:
            logger.warning(f"Verification failed: {results['message']}")
            return {
                "verification_status": "failed",
                "verification_output": results,
                "error": f"Verification failed: {results['message']}",
                "verification_id": verification_id
            }
    
    async def _multi_strategy_verification(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Use multiple strategies to verify the integration.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with verification results
        """
        # Set up verification options based on integration type and target
        strategies = self._determine_verification_strategies(state)
        
        # Execute each strategy until one succeeds or all fail
        strategy_results = {}
        success = False
        message = "All verification strategies failed"
        
        for strategy_name in strategies:
            if strategy_name == "command":
                # Custom command verification
                results = await self._verify_with_command(state, config)
            else:
                # Use registered strategies
                strategy = get_verification_strategy(strategy_name)
                if strategy:
                    results = await strategy(state, config)
                else:
                    results = {"success": False, "message": f"Unknown strategy: {strategy_name}"}
            
            strategy_results[strategy_name] = results
            
            if results["success"]:
                success = True
                message = f"Verification succeeded using {strategy_name} strategy"
                break
        
        return {
            "success": success,
            "message": message,
            "strategies": strategy_results
        }
    
    def _determine_verification_strategies(self, state: WorkflowState) -> List[str]:
        """
        Determine which verification strategies to use.
        
        Args:
            state: Current workflow state
            
        Returns:
            List of strategy names to try
        """
        # Default strategies for all verifications
        strategies = []
        
        # Custom command has highest precedence
        if state.custom_verification or self._has_verification_command(state):
            strategies.append("command")
        
        # Add integration-specific strategies
        target = state.target_name
        category = getattr(state, "integration_category", None)
        
        # Database integrations
        if any(db in target for db in ["postgres", "mysql", "redis", "mongodb"]):
            strategies.extend([SERVICE_CHECK, PROCESS_CHECK])
        
        # Web servers
        elif any(web in target for web in ["nginx", "apache", "httpd"]):
            strategies.extend([HTTP_CHECK, SERVICE_CHECK, PROCESS_CHECK])
        
        # Monitoring agents
        elif any(agent in target for agent in ["monitoring", "newrelic", "agent"]):
            strategies.extend([SERVICE_CHECK, LOG_CHECK, PROCESS_CHECK])
        
        # Cloud integrations
        elif category == "aws" or "aws" in target:
            strategies.extend([API_CHECK, LOG_CHECK])
        elif category == "azure" or "azure" in target:
            strategies.extend([API_CHECK, LOG_CHECK])
        elif category == "gcp" or "gcp" in target:
            strategies.extend([API_CHECK, LOG_CHECK])
        
        # Add general strategies as fallbacks
        if LOG_CHECK not in strategies:
            strategies.append(LOG_CHECK)
        if PROCESS_CHECK not in strategies:
            strategies.append(PROCESS_CHECK)
        
        # If no specific strategies found, use command-only
        if not strategies:
            strategies.append("command")
        
        return strategies
    
    def _has_verification_command(self, state: WorkflowState) -> bool:
        """
        Check if there's a verification command for this target.
        
        Args:
            state: Current workflow state
            
        Returns:
            True if verification command exists, False otherwise
        """
        command_key = f"{state.target_name}-verify"
        
        # Check for category-specific command
        if hasattr(state, "integration_category") and state.integration_category:
            category_key = f"{state.integration_category}/{command_key}"
            if category_key in verification_commands:
                return True
        
        # Check for direct command
        if command_key in verification_commands:
            return True
        
        # Check for integration-type command
        integration_key = f"{state.integration_type}-verify"
        if integration_key in verification_commands:
            return True
        
        return False
    
    async def _verify_with_command(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Verify using a command.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with verification results
        """
        # Get the command to execute
        command = state.custom_verification
        if not command:
            command = get_verification_command(state)
        
        if not command:
            return {
                "success": False,
                "message": "No verification command found",
                "output": None
            }
        
        # Render the command with parameters
        from jinja2 import Template
        try:
            tpl = Template(command)
            rendered_command = tpl.render(
                target_name=state.target_name,
                action=state.action,
                parameters=state.parameters
            )
        except Exception as e:
            logger.error(f"Error rendering verification command: {e}")
            return {
                "success": False,
                "message": f"Error rendering verification command: {str(e)}",
                "output": None
            }
        
        # Create a temporary script for the command
        temp_dir = tempfile.mkdtemp(prefix='workflow-verify-')
        script_id = str(uuid.uuid4())
        script_path = os.path.join(temp_dir, f"verify-{script_id}.sh")
        
        try:
            # Write verification script
            with open(script_path, 'w') as f:
                f.write(f"""#!/usr/bin/env bash
set -e
{rendered_command}
""")
            
            os.chmod(script_path, 0o755)
            logger.info(f"Prepared verification script at {script_path}")
            
            # Execute the script
            try:
                process = await asyncio.create_subprocess_exec(
                    script_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                success = process.returncode == 0
                
                stdout_str = stdout.decode('utf-8', errors='replace')
                stderr_str = stderr.decode('utf-8', errors='replace')
                
                if success:
                    logger.info("Verification command executed successfully")
                    return {
                        "success": True,
                        "message": "Verification successful",
                        "output": {
                            "stdout": stdout_str,
                            "stderr": stderr_str,
                            "exit_code": process.returncode
                        }
                    }
                else:
                    logger.warning(f"Verification command failed with exit code {process.returncode}")
                    return {
                        "success": False,
                        "message": f"Verification command failed with exit code {process.returncode}",
                        "output": {
                            "stdout": stdout_str,
                            "stderr": stderr_str,
                            "exit_code": process.returncode
                        }
                    }
            except Exception as e:
                logger.error(f"Error executing verification command: {e}")
                return {
                    "success": False,
                    "message": f"Error executing verification command: {str(e)}",
                    "output": None
                }
        finally:
            # Cleanup
            try:
                if os.path.exists(script_path):
                    os.unlink(script_path)
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
            except Exception as e:
                logger.error(f"Error cleaning up verification script: {e}")