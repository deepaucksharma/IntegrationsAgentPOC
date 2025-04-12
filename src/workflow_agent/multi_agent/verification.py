"""
VerificationAgent: Responsible for verifying integration installation and configuration.
Implements the VerificationAgentInterface from the multi-agent system.
"""
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from .interfaces import VerificationAgentInterface
from .base import MultiAgentMessage, MessageType, MessagePriority
from ..core.state import WorkflowState
from ..execution.executor import ScriptExecutor
from ..error.exceptions import VerificationError

logger = logging.getLogger(__name__)

class VerificationStep:
    """Represents a verification step to be executed."""
    
    def __init__(
        self,
        name: str,
        description: str,
        script: str,
        expected_result: Optional[str] = None,
        required: bool = True,
        timeout_seconds: int = 60
    ):
        """
        Initialize verification step.
        
        Args:
            name: Step name
            description: Description of what the step verifies
            script: Script content to execute
            expected_result: Expected output (if None, exit code 0 is sufficient)
            required: Whether this step must pass
            timeout_seconds: Timeout for the step in seconds
        """
        self.name = name
        self.description = description
        self.script = script
        self.expected_result = expected_result
        self.required = required
        self.timeout_seconds = timeout_seconds
        self.result = None
        self.executed_at = None
        self.duration_ms = None
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "script": self.script,
            "expected_result": self.expected_result,
            "required": self.required,
            "timeout_seconds": self.timeout_seconds,
            "result": self.result,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "duration_ms": self.duration_ms
        }

class VerificationAgent(VerificationAgentInterface):
    """
    Agent for verifying system state and integration installations.
    Implements the VerificationAgentInterface from the multi-agent system.
    """
    
    def __init__(
        self, 
        coordinator: Any,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            coordinator=coordinator, 
            agent_id="verification"
        )
        self.config = config or {}
        self.executor = ScriptExecutor(None)  # This would typically be provided
        
        # Register message handlers
        self.register_message_handler(MessageType.VERIFICATION_REQUEST, self._handle_verification_request)
    
    # VerificationAgentInterface required method implementations
    
    async def verify_execution(self, execution_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify execution results.
        
        Args:
            execution_result: Results to verify
            context: Verification context
            
        Returns:
            Verification results
        """
        logger.info(f"Verifying execution results: {execution_result.get('command', 'unknown')}")
        
        try:
            # Extract verification criteria from context
            expected_exit_code = context.get("expected_exit_code", 0)
            expected_output = context.get("expected_output")
            
            # Get actual results
            exit_code = execution_result.get("exit_code")
            output = execution_result.get("output", {}).get("stdout", "")
            
            # Check exit code
            exit_code_match = exit_code == expected_exit_code
            
            # Check output if specified
            output_match = True
            if expected_output:
                output_match = expected_output in output
            
            # Determine overall result
            passed = exit_code_match and output_match
            
            return {
                "passed": passed,
                "exit_code_match": exit_code_match,
                "output_match": output_match,
                "details": {
                    "expected_exit_code": expected_exit_code,
                    "actual_exit_code": exit_code,
                    "expected_output": expected_output,
                    "actual_output": output,
                }
            }
        except Exception as e:
            logger.error(f"Error verifying execution: {e}", exc_info=True)
            return {
                "passed": False,
                "error": str(e)
            }
    
    async def verify_system_state(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Verify the system state.
        
        Args:
            state: Current system state
            
        Returns:
            Verification results
        """
        logger.info(f"Verifying system state for {state.integration_type}/{state.target_name}")
        
        try:
            # Generate verification steps
            steps = self._generate_verification_steps(state)
            
            if not steps:
                logger.warning("No verification steps could be generated")
                return {
                    "passed": False,
                    "error": "No verification steps could be generated"
                }
            
            # Run verification steps
            passed_steps = []
            failed_steps = []
            
            for step in steps:
                logger.debug(f"Running verification step: {step.name}")
                
                start_time = datetime.now()
                result = await self._run_verification_step(step, state)
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                
                # Update step with execution data
                step.executed_at = start_time
                step.duration_ms = duration_ms
                step.result = result
                
                if result["success"]:
                    passed_steps.append(step.to_dict())
                else:
                    failed_steps.append({
                        **step.to_dict(),
                        "error": result["error"]
                    })
                    
                    # If this is a required step and it failed, stop verification
                    if step.required:
                        break
            
            # Determine overall result
            all_required_passed = all(
                step.required and step.result and step.result.get("success", False)
                for step in steps
            )
            
            return {
                "passed": all_required_passed,
                "passed_steps": passed_steps,
                "failed_steps": failed_steps,
                "total_steps": len(steps),
                "success_rate": len(passed_steps) / len(steps) if steps else 0
            }
            
        except Exception as e:
            logger.error(f"Error verifying system state: {e}", exc_info=True)
            return {
                "passed": False,
                "error": str(e)
            }
    
    async def verify_security(self, artifact: Any, artifact_type: str) -> Dict[str, Any]:
        """
        Verify security aspects of an artifact.
        
        Args:
            artifact: Artifact to verify (script, config, etc.)
            artifact_type: Type of artifact
            
        Returns:
            Security verification results
        """
        logger.info(f"Verifying security for {artifact_type}")
        
        try:
            security_issues = []
            
            # For scripts, check for potentially dangerous commands
            if artifact_type == "script":
                script_content = str(artifact)
                dangerous_patterns = [
                    "rm -rf /",
                    ":(){ :|:& };:",  # Fork bomb
                    "chmod 777",
                    "> /dev/sda",
                    "mkfs",
                    "dd if=/dev/zero of=/dev/sda",
                    "wget | bash",
                    "curl | bash"
                ]
                
                for pattern in dangerous_patterns:
                    if pattern in script_content:
                        security_issues.append(f"Potentially dangerous command detected: {pattern}")
            
            # For configs, check for permission issues or sensitive data
            elif artifact_type == "config":
                config_content = str(artifact)
                sensitive_patterns = [
                    "password",
                    "secret",
                    "key",
                    "token",
                    "credential"
                ]
                
                for pattern in sensitive_patterns:
                    if pattern in config_content.lower():
                        security_issues.append(f"Potential sensitive data in config: {pattern}")
            
            return {
                "passed": len(security_issues) == 0,
                "security_issues": security_issues,
                "recommendations": [
                    "Review and sanitize any flagged content",
                    "Ensure proper access controls are in place",
                    "Use environment variables for sensitive values"
                ] if security_issues else []
            }
            
        except Exception as e:
            logger.error(f"Error verifying security: {e}", exc_info=True)
            return {
                "passed": False,
                "error": str(e)
            }
    
    # Message handlers
    
    async def _handle_verification_request(self, message: MultiAgentMessage) -> None:
        """
        Handle verification request messages.
        
        Args:
            message: Verification request message
        """
        try:
            content = message.content
            verification_type = content.get("verification_type", "execution")
            
            if verification_type == "execution":
                # Handle execution verification
                execution_result = content.get("execution_result", {})
                context = content.get("context", {})
                result = await self.verify_execution(execution_result, context)
                
                response = message.create_response(
                    content={"result": result, "verification_type": verification_type},
                    metadata={"success": True, "passed": result.get("passed", False)}
                )
                await self.coordinator.route_message(response, message.sender)
                
            elif verification_type in ["verify_result", "verify_removal", "verify_standalone"]:
                # Handle system state verification
                state_dict = content.get("state", {})
                
                # Create workflow state
                state = WorkflowState(**state_dict) if isinstance(state_dict, dict) else state_dict
                
                # Verify system state
                result = await self.verify_system_state(state)
                
                # Create and send response
                response = message.create_response(
                    content={"result": result, "verification_type": verification_type},
                    metadata={"success": True, "passed": result.get("passed", False)}
                )
                await self.coordinator.route_message(response, message.sender)
                
            elif verification_type == "security":
                # Handle security verification
                artifact = content.get("artifact")
                artifact_type = content.get("artifact_type", "unknown")
                result = await self.verify_security(artifact, artifact_type)
                
                # Create and send response
                response = message.create_response(
                    content={"result": result, "verification_type": verification_type},
                    metadata={"success": True, "passed": result.get("passed", False)}
                )
                await self.coordinator.route_message(response, message.sender)
                
            else:
                # Handle unknown verification type
                error_response = message.create_response(
                    content={"error": f"Unknown verification type: {verification_type}"},
                    metadata={"success": False, "passed": False}
                )
                await self.coordinator.route_message(error_response, message.sender)
                
        except Exception as e:
            logger.error(f"Error handling verification request: {e}", exc_info=True)
            
            # Send error response
            error_response = message.create_response(
                content={"error": str(e)},
                metadata={"success": False, "passed": False}
            )
            await self.coordinator.route_message(error_response, message.sender)
    
    # Helper methods
    
    def _generate_verification_steps(self, state: WorkflowState) -> List[VerificationStep]:
        """
        Generate verification steps based on the state.
        
        Args:
            state: Workflow state
            
        Returns:
            List of verification steps
        """
        steps = []
        
        # Add basic step to check the installation directory
        install_dir = state.parameters.get("install_dir", "")
        if install_dir:
            is_windows = state.system_context.get('is_windows', False)
            
            if is_windows:
                script = f'Test-Path "{install_dir}" | Write-Output'
                expected = 'True'
            else:
                script = f'[ -d "{install_dir}" ] && echo "Directory exists" || echo "Directory not found"'
                expected = 'Directory exists'
                
            steps.append(VerificationStep(
                name="Check Installation Directory",
                description=f"Verify installation directory {install_dir} exists",
                script=script,
                expected_result=expected,
                required=True
            ))
            
        # Add basic step to check a configuration file
        config_path = state.parameters.get("config_path", "")
        if config_path:
            is_windows = state.system_context.get('is_windows', False)
            
            if is_windows:
                script = f'Test-Path "{config_path}" | Write-Output'
                expected = 'True'
            else:
                script = f'[ -f "{config_path}" ] && echo "File exists" || echo "File not found"'
                expected = 'File exists'
                
            steps.append(VerificationStep(
                name="Check Configuration File",
                description=f"Verify configuration file {config_path} exists",
                script=script,
                expected_result=expected,
                required=True
            ))
        
        # Check if there are integration-specific verification steps in verification_data
        verification_data = state.verification_data or {}
        if verification_data and "steps" in verification_data:
            for step_data in verification_data["steps"]:
                steps.append(VerificationStep(
                    name=step_data.get("name", "Unnamed Step"),
                    description=step_data.get("description", ""),
                    script=step_data.get("script", "echo 'Empty step'"),
                    expected_result=step_data.get("expected_result"),
                    required=step_data.get("required", True),
                    timeout_seconds=step_data.get("timeout_seconds", 60)
                ))
                
        return steps
    
    async def _run_verification_step(self, step: VerificationStep, state: WorkflowState) -> Dict[str, Any]:
        """
        Run a verification step.
        
        Args:
            step: Verification step to run
            state: Workflow state
            
        Returns:
            Dictionary with result information
        """
        try:
            # Create a temporary state with the verification script
            temp_state = state.set_script(step.script)
            
            # Execute the script
            result_state = await self.executor.execute(temp_state)
            
            # Check for execution error
            if result_state.has_error:
                return {
                    "success": False,
                    "error": result_state.error,
                    "output": result_state.output.stdout if result_state.output else None
                }
                
            # Check the result against expected output if specified
            if step.expected_result is not None:
                output = result_state.output.stdout if result_state.output else ""
                if step.expected_result not in output:
                    return {
                        "success": False,
                        "error": f"Expected output containing '{step.expected_result}', got '{output}'",
                        "output": output
                    }
                    
            # Step passed
            return {
                "success": True,
                "output": result_state.output.stdout if result_state.output else None
            }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error executing verification step: {str(e)}",
                "output": None
            }
    
    # MultiAgentBase abstract method implementation
    
    async def _handle_message(self, message: MultiAgentMessage) -> None:
        """
        Handle a message that has no specific handler.
        
        Args:
            message: Message to handle
        """
        logger.warning(f"No specific handler for message type: {message.message_type}")
        
        # Generate a generic error response
        error_response = message.create_response(
            content={"error": f"No handler for message type: {message.message_type}"},
            metadata={"success": False}
        )
        await self.coordinator.route_message(error_response, message.sender)
