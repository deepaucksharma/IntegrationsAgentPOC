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
        
    async def verify_system_clean(self, state: WorkflowState) -> WorkflowState:
        """
        Verify that the system is in a clean state after rollback.
        
        Args:
            state: Workflow state after rollback
            
        Returns:
            Updated workflow state with verification results
        """
        logger.info(f"Verifying system is clean after rollback for {state.integration_type}")
        
        try:
            # Create generic verification steps to check system cleanliness
            steps = []
            
            # Check if integration-specific verification exists
            verification_dir = Path(__file__).parent / "definitions"
            yaml_path = verification_dir / f"{state.integration_type}_clean.yaml"
            
            if yaml_path.exists():
                # Use integration-specific verification
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
            else:
                # Generate basic verification steps based on changes
                steps = self._generate_clean_verification_steps(state)
                
            if not steps:
                logger.warning(f"No clean verification steps created for {state.integration_type}")
                return state.add_warning("No clean verification steps available")
                
            logger.info(f"Running {len(steps)} clean verification steps")
            
            # Run verification steps
            passed_steps = []
            failed_steps = []
            
            for step in steps:
                result = await self.runner.run_step(step, state)
                
                if result["success"]:
                    passed_steps.append(step.name)
                    state = state.add_message(f"Clean verification step '{step.name}' passed")
                else:
                    failed_steps.append({
                        "name": step.name,
                        "error": result["error"]
                    })
                    
                    error_msg = f"Clean verification step '{step.name}' failed: {result['error']}"
                    logger.warning(error_msg)
                    state = state.add_warning(error_msg)
            
            # Summarize results
            verification_summary = {
                "passed": passed_steps,
                "failed": failed_steps,
                "total": len(steps),
                "success": len(failed_steps) == 0
            }
            
            state = state.set_verification_result("clean_check", verification_summary)
            
            if verification_summary["success"]:
                logger.info("All clean verification steps passed")
                state = state.add_message("System is clean after rollback")
            else:
                logger.warning("Some clean verification steps failed")
                state = state.add_warning("System may not be completely clean after rollback")
                
            return state
            
        except Exception as e:
            logger.error(f"Clean verification error: {e}", exc_info=True)
            return state.set_error(f"Clean verification error: {str(e)}")
            
    def _generate_clean_verification_steps(self, state: WorkflowState) -> List[VerificationStep]:
        """Generate verification steps based on changes that were rolled back."""
        steps = []
        is_windows = state.system_context.get('is_windows', 'win' in state.system_context.get('platform', {}).get('system', '').lower())
        
        # Track which types we've handled to avoid duplicates
        handled_types = set()
        
        for change in state.changes:
            # Skip if we've already handled this type
            if change.type in handled_types:
                continue
                
            # Generate verification based on change type
            if change.type == 'file_created' or change.type.startswith('file_'):
                # Verify file doesn't exist
                script = f'Test-Path "{change.target}" | Write-Output' if is_windows else f'[ -f "{change.target}" ] && echo "File exists" || echo "File not found"'
                expected = 'False' if is_windows else 'File not found'
                
                steps.append(VerificationStep(
                    name=f"Verify File Removed: {change.target}",
                    description=f"Verify file {change.target} was removed",
                    script=script,
                    expected_result=expected,
                    required=False  # Not critical as failures here are typically okay
                ))
                
                handled_types.add(change.type)
                
            elif change.type == 'directory_created' or change.type.startswith('directory_'):
                # Verify directory doesn't exist
                script = f'Test-Path -PathType Container "{change.target}" | Write-Output' if is_windows else f'[ -d "{change.target}" ] && echo "Directory exists" || echo "Directory not found"'
                expected = 'False' if is_windows else 'Directory not found'
                
                steps.append(VerificationStep(
                    name=f"Verify Directory Removed: {change.target}",
                    description=f"Verify directory {change.target} was removed",
                    script=script,
                    expected_result=expected,
                    required=False
                ))
                
                handled_types.add(change.type)
                
            elif change.type.startswith('service_'):
                # Verify service isn't running/installed
                if is_windows:
                    script = f'Get-Service "{change.target}" -ErrorAction SilentlyContinue | Write-Output'
                    # No expected_result - absence of service is success
                else:
                    script = f'systemctl status {change.target} 2>/dev/null || echo "Service not found"'
                    expected = 'Service not found'
                    
                steps.append(VerificationStep(
                    name=f"Verify Service Not Running: {change.target}",
                    description=f"Verify service {change.target} is not running",
                    script=script,
                    expected_result=None if is_windows else expected,
                    required=False
                ))
                
                handled_types.add(change.type)
                
            elif change.type.startswith('package_'):
                # Verify package isn't installed
                if is_windows:
                    script = f'Get-WmiObject -Class Win32_Product | Where-Object {{ $_.Name -like "*{change.target}*" }} | Write-Output'
                    # No expected_result - absence of package is success
                else:
                    script = f'dpkg -l | grep -q "{change.target}" || rpm -q "{change.target}" >/dev/null 2>&1 || echo "Package not found"'
                    expected = 'Package not found'
                    
                steps.append(VerificationStep(
                    name=f"Verify Package Not Installed: {change.target}",
                    description=f"Verify package {change.target} is not installed",
                    script=script,
                    expected_result=None if is_windows else expected,
                    required=False
                ))
                
                handled_types.add(change.type)
                
        # Add generic system health checks
        # Process checks - make sure no unexpected processes are running
        process_name = state.integration_type.lower()
        if is_windows:
            script = f'Get-Process | Where-Object {{ $_.ProcessName -like "*{process_name}*" }} | ForEach-Object {{ $_.ProcessName }}'
        else:
            script = f'ps aux | grep -i "{process_name}" | grep -v grep || echo "No matching processes"'
            
        steps.append(VerificationStep(
            name=f"Verify No Integration Processes",
            description=f"Verify no {state.integration_type} processes are running",
            script=script,
            expected_result=None,  # Just check exit code
            required=False
        ))
            
        return steps
    
    async def verify_uninstall(self, state: WorkflowState) -> WorkflowState:
        """
        Verify that an uninstallation was successful.
        
        Args:
            state: Workflow state after uninstallation
            
        Returns:
            Updated workflow state with verification results
        """
        logger.info(f"Verifying uninstallation for {state.integration_type}")
        
        # For uninstall, we can use the same clean verification
        return await self.verify_system_clean(state)
        
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
