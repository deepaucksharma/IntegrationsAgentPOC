"""
Verification agent implementation.
"""
import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from .base_agent import BaseAgent, AgentConfig, AgentCapability, AgentContext, AgentResult
from ..error.exceptions import AgentError, VerificationError
from ..core.state import WorkflowState, WorkflowStatus

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

class VerificationAgent(BaseAgent):
    """
    Agent for verifying system state.
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the verification agent.
        
        Args:
            config: Optional agent configuration
        """
        super().__init__(config)
        
    def _register_capabilities(self) -> None:
        """Register agent capabilities."""
        self.capabilities.add(AgentCapability.VERIFICATION)
        
    async def _validate_agent_context(self, context: AgentContext) -> bool:
        """
        Validate agent-specific context requirements.
        
        Args:
            context: Agent execution context
            
        Returns:
            True if context is valid
            
        Raises:
            AgentError: If context is invalid
        """
        # Ensure required parameters are present
        state = context.workflow_state
        
        if not state.integration_type:
            raise AgentError("Integration type is required")
            
        return True
        
    async def _execute_agent_logic(self, context: AgentContext) -> AgentResult:
        """
        Execute verification steps.
        
        Args:
            context: Agent execution context
            
        Returns:
            Agent result with verification results
        """
        state = context.workflow_state
        
        # Generate verification steps
        try:
            steps = self._generate_verification_steps(state)
            
            if not steps:
                return AgentResult.error_result(
                    workflow_state=state,
                    error_message="No verification steps could be generated"
                )
                
            logger.info(f"Running {len(steps)} verification steps for {state.integration_type}")
            
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
                    state = state.add_message(f"Verification step '{step.name}' passed")
                else:
                    failed_steps.append({
                        **step.to_dict(),
                        "error": result["error"]
                    })
                    
                    error_msg = f"Verification step '{step.name}' failed: {result['error']}"
                    if step.required:
                        logger.error(error_msg)
                        
                        # For required steps, fail immediately
                        return AgentResult.error_result(
                            workflow_state=state.set_error(error_msg),
                            error_message=error_msg,
                            metadata={
                                "passed_steps": passed_steps,
                                "failed_steps": failed_steps
                            }
                        )
                    else:
                        logger.warning(error_msg)
                        state = state.add_warning(error_msg)
                        
            # All steps passed or non-required steps failed
            new_state = state.set_verification_result("verification", {
                "passed_steps": passed_steps,
                "failed_steps": failed_steps,
                "total_steps": len(steps),
                "success_rate": len(passed_steps) / len(steps) if steps else 0
            })
            
            # Mark as completed
            if state.status != WorkflowStatus.COMPLETED:
                new_state = new_state.mark_completed()
                
            return AgentResult.success_result(
                workflow_state=new_state,
                output={
                    "passed_steps": passed_steps,
                    "failed_steps": failed_steps,
                    "total_steps": len(steps)
                }
            )
                
        except Exception as e:
            error_msg = f"Verification error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            return AgentResult.error_result(
                workflow_state=state,
                error_message=error_msg
            )
            
    def _generate_verification_steps(self, state: WorkflowState) -> List[VerificationStep]:
        """
        Generate verification steps based on the state.
        
        Args:
            state: Workflow state
            
        Returns:
            List of verification steps
        """
        # This is a simple example - in a real implementation, these would be
        # generated dynamically based on the integration type and installation
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
                script = f'[ -d "{config_path}" ] && echo "Directory exists" || echo "Directory not found"'
                expected = 'Directory exists'
                
            steps.append(VerificationStep(
                name="Check Configuration Directory",
                description=f"Verify configuration directory {config_path} exists",
                script=script,
                expected_result=expected,
                required=True
            ))
            
        # In a real implementation, additional steps would be added based on:
        # - Integration type
        # - Installation parameters
        # - System type
        # - Changes made during installation
            
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
            # In a real implementation, this would execute the script
            # For now, we'll simulate execution with a mock result
            
            # Assume this uses an executor from another part of the system
            from ..execution.executor import ScriptExecutor
            executor = ScriptExecutor(None)  # This would typically come from a container
            
            # Create a temporary state with the verification script
            temp_state = state.set_script(step.script)
            
            # Execute the script
            result_state = await executor.execute(temp_state)
            
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
