"""
Verification manager for handling verification operations.
"""
import logging
from typing import Dict, Any, Optional, List, Union
import yaml
from pathlib import Path

from ..core.state import WorkflowState
from ..error.exceptions import VerificationError
from ..config.configuration import WorkflowConfiguration
from ..templates.manager import TemplateManager
from .runner import VerificationRunner

logger = logging.getLogger(__name__)

class VerificationStep:
    """Represents a verification step to be executed."""
    
    def __init__(
        self,
        name: str,
        description: str,
        script: str,
        expected_result: Optional[str] = None,
        required: bool = True
    ):
        """
        Initialize verification step.
        
        Args:
            name: Step name
            description: Description of what the step verifies
            script: Script content to execute
            expected_result: Expected output (if None, exit code 0 is sufficient)
            required: Whether this step must pass
        """
        self.name = name
        self.description = description
        self.script = script
        self.expected_result = expected_result
        self.required = required
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "script": self.script,
            "expected_result": self.expected_result,
            "required": self.required
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VerificationStep':
        """Create step from dictionary."""
        return cls(
            name=data.get("name", "Unnamed Step"),
            description=data.get("description", ""),
            script=data.get("script", ""),
            expected_result=data.get("expected_result"),
            required=data.get("required", True)
        )

class VerificationManager:
    """Manages verification operations."""
    
    def __init__(self, config: WorkflowConfiguration, template_manager: TemplateManager):
        """
        Initialize verification manager.
        
        Args:
            config: Workflow configuration
            template_manager: Template manager for script generation
        """
        self.config = config
        self.template_manager = template_manager
        self.runner = VerificationRunner(config)
        
    async def verify(self, state: WorkflowState) -> WorkflowState:
        """
        Verify an integration using the workflow state.
        
        Args:
            state: Workflow state with integration parameters
            
        Returns:
            Updated workflow state with verification results
        """
        if state.action != "verify":
            logger.error(f"Cannot verify: Invalid action '{state.action}'")
            return state.set_error(f"Cannot verify: Invalid action '{state.action}'")
            
        try:
            # Load verification steps
            steps = await self._load_verification_steps(state)
            
            if not steps:
                logger.warning(f"No verification steps found for {state.integration_type}")
                return state.add_warning("No verification steps found")
                
            logger.info(f"Running {len(steps)} verification steps for {state.integration_type}")
            
            # Run verification steps
            passed_steps = []
            failed_steps = []
            
            for step in steps:
                result = await self.runner.run_step(step, state)
                
                if result["success"]:
                    passed_steps.append(step.name)
                    state = state.add_message(f"Verification step '{step.name}' passed")
                else:
                    failed_steps.append({
                        "name": step.name,
                        "error": result["error"]
                    })
                    
                    error_msg = f"Verification step '{step.name}' failed: {result['error']}"
                    if step.required:
                        logger.error(error_msg)
                        state = state.set_error(error_msg)
                        return state
                    else:
                        logger.warning(error_msg)
                        state = state.add_warning(error_msg)
            
            # All steps passed or non-required steps failed
            verification_summary = {
                "passed": passed_steps,
                "failed": failed_steps,
                "total": len(steps),
                "success": len(passed_steps) == len(steps)
            }
            
            state = state.evolve(
                template_data={
                    **state.template_data,
                    "verification_results": verification_summary
                }
            )
            
            if verification_summary["success"]:
                logger.info("All verification steps passed")
                state = state.add_message("All verification steps passed")
            else:
                logger.warning("Some non-required verification steps failed")
                state = state.add_warning("Some non-required verification steps failed")
                
            return state.mark_completed()
            
        except Exception as e:
            logger.error(f"Verification error: {e}", exc_info=True)
            return state.set_error(f"Verification error: {str(e)}")
    
    async def _load_verification_steps(self, state: WorkflowState) -> List[VerificationStep]:
        """
        Load verification steps for a specific integration.
        
        Args:
            state: Workflow state with integration information
            
        Returns:
            List of verification steps
        """
        steps = []
        
        # Try to load verification from template
        template_key = f"verify/{state.integration_type}/{state.target_name}"
        verification_script = self.template_manager.get_template(template_key)
        
        if verification_script:
            # Render the template
            rendered_script = self.template_manager.render_template(
                template_key,
                {
                    **state.parameters,
                    **state.template_data,
                    "target_name": state.target_name,
                    "integration_type": state.integration_type
                }
            )
            
            if rendered_script:
                steps.append(VerificationStep(
                    name="Template Verification",
                    description=f"Verification for {state.integration_type} - {state.target_name}",
                    script=rendered_script,
                    required=True
                ))
                
        # Try to load verification from YAML definition
        try:
            # Check built-in verifications first
            verification_dir = Path(__file__).parent / "definitions"
            if verification_dir.exists():
                yaml_path = verification_dir / f"{state.integration_type}.yaml"
                
                if yaml_path.exists():
                    with open(yaml_path, "r") as f:
                        verification_data = yaml.safe_load(f)
                        
                    if isinstance(verification_data, dict) and "steps" in verification_data:
                        for step_data in verification_data["steps"]:
                            # Render any templates in the script
                            if "script_template" in step_data:
                                script = self.template_manager.render_string_template(
                                    step_data["script_template"],
                                    {
                                        **state.parameters,
                                        **state.template_data,
                                        "target_name": state.target_name,
                                        "integration_type": state.integration_type
                                    }
                                )
                                step_data["script"] = script
                                
                            step = VerificationStep.from_dict(step_data)
                            steps.append(step)
        except Exception as e:
            logger.warning(f"Error loading verification from YAML: {e}")
            
        return steps
