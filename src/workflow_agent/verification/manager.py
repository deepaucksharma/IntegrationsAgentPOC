"""
Enhanced verification manager with LLM-driven verification strategy and analysis.
"""
import logging
import asyncio
import json
import re
import hashlib
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime
import yaml
from pathlib import Path

from ..core.state import WorkflowState, Change, WorkflowStatus
from ..error.exceptions import VerificationError
from ..config.configuration import WorkflowConfiguration
from ..templates.manager import TemplateManager
from .runner import VerificationRunner
from ..llm.service import LLMService, LLMProvider

logger = logging.getLogger(__name__)

class VerificationStep:
    """Represents a verification step to be executed with enhanced metadata."""
    
    def __init__(
        self,
        name: str,
        description: str,
        script: str,
        expected_result: Optional[str] = None,
        required: bool = True,
        timeout_seconds: int = 60,
        category: str = "general",
        importance: str = "medium",
        verification_type: str = "existence",
        reasoning: Optional[str] = None
    ):
        """
        Initialize verification step with enhanced metadata.
        
        Args:
            name: Step name
            description: Description of what the step verifies
            script: Script content to execute
            expected_result: Expected output (if None, exit code 0 is sufficient)
            required: Whether this step must pass
            timeout_seconds: Timeout for the step in seconds
            category: Category of verification (e.g., "files", "services", "connectivity")
            importance: Importance level ("high", "medium", "low")
            verification_type: Type of verification ("existence", "content", "status", "connectivity")
            reasoning: Reasoning for including this step
        """
        self.name = name
        self.description = description
        self.script = script
        self.expected_result = expected_result
        self.required = required
        self.timeout_seconds = timeout_seconds
        self.category = category
        self.importance = importance
        self.verification_type = verification_type
        self.reasoning = reasoning
        self.result = None
        self.executed_at = None
        self.duration_ms = None
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation with enhanced metadata."""
        return {
            "name": self.name,
            "description": self.description,
            "script": self.script,
            "expected_result": self.expected_result,
            "required": self.required,
            "timeout_seconds": self.timeout_seconds,
            "category": self.category,
            "importance": self.importance,
            "verification_type": self.verification_type,
            "reasoning": self.reasoning,
            "result": self.result,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "duration_ms": self.duration_ms
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VerificationStep':
        """Create step from dictionary with enhanced metadata support."""
        return cls(
            name=data.get("name", "Unnamed Step"),
            description=data.get("description", ""),
            script=data.get("script", ""),
            expected_result=data.get("expected_result"),
            required=data.get("required", True),
            timeout_seconds=data.get("timeout_seconds", 60),
            category=data.get("category", "general"),
            importance=data.get("importance", "medium"),
            verification_type=data.get("verification_type", "existence"),
            reasoning=data.get("reasoning")
        )

class VerificationManager:
    """Enhanced verification manager with LLM-driven verification strategies."""
    
    def __init__(
        self, 
        config: WorkflowConfiguration, 
        template_manager: TemplateManager,
        llm_service: Optional[LLMService] = None
    ):
        """
        Initialize verification manager with LLM capabilities.
        
        Args:
            config: Workflow configuration
            template_manager: Template manager for script generation
            llm_service: LLM service for enhanced verification
        """
        self.config = config
        self.template_manager = template_manager
        self.runner = VerificationRunner(config)
        self.llm_service = llm_service or LLMService()
        
        # Performance metrics and learning
        self.verification_metrics = {}
        self.verification_history = {}
        
        logger.info("Enhanced verification manager initialized with LLM capabilities")
        
    async def verify_system_clean(self, state: WorkflowState) -> WorkflowState:
        """
        Verify that the system is in a clean state after rollback using LLM-enhanced strategies.
        
        Args:
            state: Workflow state after rollback
            
        Returns:
            Updated workflow state with verification results
        """
        logger.info(f"Verifying system is clean after rollback for {state.integration_type}")
        
        try:
            # Use LLM to generate clean verification steps
            steps = await self._generate_clean_verification_steps(state)
            
            if not steps:
                logger.warning(f"No clean verification steps created for {state.integration_type}")
                return state.add_warning("No clean verification steps available")
                
            logger.info(f"Running {len(steps)} LLM-generated clean verification steps")
            
            # Run verification steps
            passed_steps = []
            failed_steps = []
            
            for step in steps:
                start_time = datetime.now()
                result = await self.runner.run_step(step, state)
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                
                # Update step with execution data
                step.executed_at = start_time
                step.duration_ms = duration_ms
                step.result = result
                
                if result["success"]:
                    passed_steps.append(step.to_dict())
                    state = state.add_message(f"Clean verification step '{step.name}' passed")
                else:
                    failed_steps.append({
                        **step.to_dict(),
                        "error": result["error"]
                    })
                    
                    error_msg = f"Clean verification step '{step.name}' failed: {result['error']}"
                    logger.warning(error_msg)
                    state = state.add_warning(error_msg)
            
            # Use LLM to analyze verification results
            verification_summary = await self._analyze_verification_results(
                passed_steps, 
                failed_steps, 
                len(steps),
                state,
                "clean_verification"
            )
            
            state = state.set_verification_result("clean_check", verification_summary)
            
            # Update state based on analysis
            if verification_summary.get("system_clean", False):
                logger.info("LLM analysis determines system is clean after rollback")
                state = state.add_message("System is clean after rollback")
            else:
                logger.warning("LLM analysis indicates system may not be completely clean")
                state = state.add_warning(
                    f"System may not be completely clean after rollback: {verification_summary.get('reasoning', '')}"
                )
                
            return state
            
        except Exception as e:
            logger.error(f"Clean verification error: {e}", exc_info=True)
            return state.set_error(f"Clean verification error: {str(e)}")
            
    async def _generate_clean_verification_steps(self, state: WorkflowState) -> List[VerificationStep]:
        """
        Generate verification steps for clean system check using LLM with awareness of changes made.
        
        Args:
            state: Workflow state with change tracking
            
        Returns:
            List of verification steps
        """
        # Extract information about changes made during installation
        changes_info = []
        for change in state.changes:
            changes_info.append({
                "type": change.type,
                "target": change.target,
                "revertible": change.revertible
            })
        
        # Get platform information
        is_windows = state.system_context.get('is_windows', False) or 'win' in state.system_context.get('platform', {}).get('system', '').lower()
        
        # Prepare prompt for LLM
        prompt = f"""
        Generate verification steps to check that a system is clean after uninstalling a New Relic {state.integration_type} integration.
        
        Integration details:
        - Type: {state.integration_type}
        - Target name: {state.target_name}
        - Platform: {"Windows" if is_windows else "Linux/Unix"}
        
        Changes that were made during installation:
        {json.dumps(changes_info, indent=2)}
        
        Generate 5-10 verification steps to confirm the system is clean, focusing on:
        1. Checking for removed files and directories
        2. Verifying services are stopped and removed
        3. Confirming configuration files are removed
        4. Checking for lingering processes
        5. Verifying environment variables or registry entries
        
        For each step, specify:
        - A descriptive name
        - A clear description of what is being verified
        - A {"PowerShell" if is_windows else "Bash"} script to perform the verification
        - Expected result (if applicable)
        - Whether the step is required for verification success
        - A timeout in seconds
        - Category of verification
        - Importance level (high, medium, low)
        - Verification type (existence, content, status, connectivity)
        
        Format your response as a JSON array of verification step objects.
        """
        
        try:
            # Generate verification steps using LLM
            verification_steps = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert in system verification and cleanup validation after software removal.",
                temperature=0.2  # Lower temperature for more deterministic results
            )
            
            # Convert to VerificationStep objects
            steps = []
            
            if isinstance(verification_steps, list):
                for step_data in verification_steps:
                    steps.append(VerificationStep.from_dict(step_data))
            else:
                logger.warning("LLM did not return a list of verification steps")
                # Fall back to simple verification steps based on changes
                steps = self._generate_basic_clean_verification_steps(state)
            
            return steps
            
        except Exception as e:
            logger.error(f"Error generating clean verification steps: {e}")
            # Fall back to basic verification
            return self._generate_basic_clean_verification_steps(state)
    
    def _generate_basic_clean_verification_steps(self, state: WorkflowState) -> List[VerificationStep]:
        """Generate basic verification steps based on changes that were rolled back."""
        steps = []
        
        # Safely determine if we're on Windows
        is_windows = False
        try:
            # Handle system_context safely, could be a dict, string, or something else
            if isinstance(state.system_context, dict):
                if 'is_windows' in state.system_context:
                    is_windows = bool(state.system_context['is_windows'])
                elif 'platform' in state.system_context:
                    platform_info = state.system_context['platform']
                    if isinstance(platform_info, dict) and 'system' in platform_info:
                        is_windows = 'win' in platform_info['system'].lower()
                    elif isinstance(platform_info, str):
                        is_windows = 'win' in platform_info.lower()
            elif isinstance(state.system_context, str):
                is_windows = 'win' in state.system_context.lower()
        except Exception:
            # Default to platform detection if context is problematic
            import platform as plt
            is_windows = 'win' in plt.system().lower()
        
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
                    required=False,  # Not critical as failures here are typically okay
                    category="files",
                    verification_type="existence"
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
                    required=False,
                    category="files",
                    verification_type="existence"
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
                    required=False,
                    category="services",
                    verification_type="status"
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
                    required=False,
                    category="packages",
                    verification_type="existence"
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
            required=False,
            category="processes",
            verification_type="status"
        ))
            
        return steps
    
    async def verify_uninstall(self, state: WorkflowState) -> WorkflowState:
        """
        Verify that an uninstallation was successful using LLM-enhanced verification.
        
        Args:
            state: Workflow state after uninstallation
            
        Returns:
            Updated workflow state with verification results
        """
        logger.info(f"Verifying uninstallation for {state.integration_type}")
        
        try:
            # Generate uninstall-specific verification steps
            steps = await self._generate_uninstall_verification_steps(state)
            
            if not steps:
                logger.warning(f"No uninstall verification steps created for {state.integration_type}")
                return state.add_warning("No uninstall verification steps available")
                
            logger.info(f"Running {len(steps)} LLM-generated uninstall verification steps")
            
            # Run verification steps
            passed_steps = []
            failed_steps = []
            
            for step in steps:
                start_time = datetime.now()
                result = await self.runner.run_step(step, state)
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                
                # Update step with execution data
                step.executed_at = start_time
                step.duration_ms = duration_ms
                step.result = result
                
                if result["success"]:
                    passed_steps.append(step.to_dict())
                    state = state.add_message(f"Uninstall verification step '{step.name}' passed")
                else:
                    failed_steps.append({
                        **step.to_dict(),
                        "error": result["error"]
                    })
                    
                    error_msg = f"Uninstall verification step '{step.name}' failed: {result['error']}"
                    logger.warning(error_msg)
                    
                    if step.required:
                        state = state.add_warning(error_msg)
                    else:
                        state = state.add_message(error_msg)
            
            # Use LLM to analyze verification results
            verification_summary = await self._analyze_verification_results(
                passed_steps, 
                failed_steps, 
                len(steps),
                state,
                "uninstall_verification"
            )
            
            state = state.set_verification_result("uninstall_check", verification_summary)
            
            # Update state based on analysis
            if verification_summary.get("uninstall_successful", False):
                logger.info("LLM analysis determines uninstallation was successful")
                state = state.add_message("Uninstallation verified successfully")
                return state.mark_completed()
            else:
                logger.warning("LLM analysis indicates uninstallation may not be complete")
                
                # If critical issues, set as error
                if verification_summary.get("critical_issues", False):
                    return state.set_error(
                        f"Uninstallation verification failed: {verification_summary.get('reasoning', '')}"
                    )
                    
                # Otherwise, just add warning but continue
                state = state.add_warning(
                    f"Uninstallation may not be complete: {verification_summary.get('reasoning', '')}"
                )
                return state.mark_completed()
                
        except Exception as e:
            logger.error(f"Uninstall verification error: {e}", exc_info=True)
            return state.set_error(f"Uninstall verification error: {str(e)}")
    
    async def _generate_uninstall_verification_steps(self, state: WorkflowState) -> List[VerificationStep]:
        """
        Generate verification steps for uninstallation using LLM.
        
        Args:
            state: Workflow state after uninstallation
            
        Returns:
            List of verification steps
        """
        # This could be customized for uninstallation, but for now, leveraging clean verification is sensible
        return await self._generate_clean_verification_steps(state)
        
    async def verify(self, state: WorkflowState) -> WorkflowState:
        """
        Verify an integration using the workflow state with LLM-enhanced strategies.
        
        Args:
            state: Workflow state with integration parameters
            
        Returns:
            Updated workflow state with verification results
        """
        # Allow verify both for dedicated 'verify' action and as post-install verification
        if state.action != "verify" and state.action != "install":
            logger.error(f"Cannot verify: Invalid action '{state.action}'")
            return state.set_error(f"Cannot verify: Invalid action '{state.action}'")
            
        try:
            # Generate verification strategy using LLM
            verification_strategy = await self._generate_verification_strategy(state)
            
            # Load verification steps based on strategy
            steps = await self._generate_verification_steps(state, verification_strategy)
            
            if not steps:
                logger.warning(f"No verification steps generated for {state.integration_type}")
                return state.add_warning("No verification steps could be generated")
                
            logger.info(f"Running {len(steps)} verification steps for {state.integration_type}")
            
            # Run verification steps
            passed_steps = []
            failed_steps = []
            
            for step in steps:
                logger.debug(f"Running verification step: {step.name}")
                
                start_time = datetime.now()
                result = await self.runner.run_step(step, state)
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
                        state = state.set_error(error_msg)
                        
                        # For required steps, we might want to run additional diagnostic steps
                        diagnostic_steps = await self._generate_diagnostic_steps(state, step, result["error"])
                        if diagnostic_steps:
                            logger.info(f"Running {len(diagnostic_steps)} diagnostic steps for failed verification")
                            diagnostic_results = await self._run_diagnostic_steps(diagnostic_steps, state)
                            state = state.evolve(
                                template_data={
                                    **state.template_data,
                                    "diagnostic_results": diagnostic_results
                                }
                            )
                        
                        return state
                    else:
                        logger.warning(error_msg)
                        state = state.add_warning(error_msg)
            
            # All steps passed or non-required steps failed
            verification_summary = await self._analyze_verification_results(
                passed_steps, 
                failed_steps, 
                len(steps),
                state,
                "verification"
            )
            
            state = state.evolve(
                template_data={
                    **state.template_data,
                    "verification_results": verification_summary
                }
            )
            
            # Update state based on analysis
            if verification_summary.get("verification_successful", False):
                logger.info("Verification analysis indicates successful integration")
                state = state.add_message("All verification steps passed")
                return state.mark_completed()
            else:
                logger.warning("Verification analysis indicates issues")
                state = state.add_warning(
                    f"Verification found issues: {verification_summary.get('reasoning', '')}"
                )
                
                # We successfully finished even with warnings
                return state.mark_completed()
            
        except Exception as e:
            logger.error(f"Verification error: {e}", exc_info=True)
            return state.set_error(f"Verification error: {str(e)}")
    
    async def _generate_verification_strategy(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Generate a verification strategy using LLM based on integration details.
        
        Args:
            state: Workflow state
            
        Returns:
            Verification strategy
        """
        # Extract integration details
        integration_type = state.integration_type
        target_name = state.target_name
        is_windows = state.system_context.get('is_windows', False) or 'win' in state.system_context.get('platform', {}).get('system', '').lower()
        
        # Prepare prompt for LLM
        prompt = f"""
        Create a verification strategy for a New Relic {integration_type} integration.
        
        Integration details:
        - Type: {integration_type}
        - Target name: {target_name}
        - Platform: {"Windows" if is_windows else "Linux/Unix"}
        - Parameters: {json.dumps(state.parameters, indent=2)}
        
        Create a comprehensive verification strategy covering:
        1. Files and directories to verify
        2. Services to check
        3. Network connections to test
        4. Processes to look for
        5. Logs to examine
        6. API endpoints to test
        7. Configurations to validate
        
        For each verification area, specify:
        - What needs to be verified
        - Why it's important
        - How critical it is (blocker, warning, informational)
        
        Format your response as a structured JSON object.
        """
        
        try:
            # Generate verification strategy using LLM
            strategy = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert in designing verification strategies for software integrations.",
                temperature=0.2
            )
            
            logger.info(f"Generated verification strategy with {len(strategy.keys() if isinstance(strategy, dict) else [])} components")
            return strategy
            
        except Exception as e:
            logger.warning(f"Error generating verification strategy: {e}")
            # Return basic strategy
            return {
                "files": {"verify": True, "critical": True},
                "services": {"verify": True, "critical": True},
                "network": {"verify": True, "critical": False},
                "processes": {"verify": True, "critical": True},
                "logs": {"verify": True, "critical": False},
                "configuration": {"verify": True, "critical": True}
            }
    
    async def _generate_verification_steps(self, state: WorkflowState, strategy: Dict[str, Any]) -> List[VerificationStep]:
        """
        Generate verification steps based on strategy and integration details.
        
        Args:
            state: Workflow state
            strategy: Verification strategy
            
        Returns:
            List of verification steps
        """
        # Extract integration details
        integration_type = state.integration_type
        target_name = state.target_name
        is_windows = state.system_context.get('is_windows', False) or 'win' in state.system_context.get('platform', {}).get('system', '').lower()
        
        # Prepare prompt for LLM
        prompt = f"""
        Generate verification steps for a New Relic {integration_type} integration based on the following strategy.
        
        Integration details:
        - Type: {integration_type}
        - Target name: {target_name}
        - Platform: {"Windows" if is_windows else "Linux/Unix"}
        - Parameters: {json.dumps(state.parameters, indent=2)}
        
        Verification strategy:
        {json.dumps(strategy, indent=2)}
        
        Generate 8-15 specific verification steps covering all areas in the strategy.
        For each step, provide:
        - A descriptive name
        - A clear description of what is being verified
        - A {"PowerShell" if is_windows else "Bash"} script to perform the verification
        - Expected result (if applicable)
        - Whether the step is required for verification success (based on criticality)
        - A reasonable timeout in seconds
        - Category of verification
        - Importance level (high, medium, low)
        - Verification type (existence, content, status, connectivity)
        - Reasoning for this verification step
        
        Format your response as a JSON array of verification step objects.
        """
        
        try:
            # Generate verification steps using LLM
            verification_steps = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert in creating precise and effective verification steps for system integrations.",
                temperature=0.2
            )
            
            # Convert to VerificationStep objects
            steps = []
            
            if isinstance(verification_steps, list):
                for step_data in verification_steps:
                    steps.append(VerificationStep.from_dict(step_data))
            else:
                logger.warning("LLM did not return a list of verification steps")
                # Fall back to template-based verification
                steps = await self._load_template_verification_steps(state)
            
            return steps
            
        except Exception as e:
            logger.error(f"Error generating verification steps: {e}")
            # Fall back to template-based verification
            return await self._load_template_verification_steps(state)
    
    async def _load_template_verification_steps(self, state: WorkflowState) -> List[VerificationStep]:
        """
        Load verification steps from templates as a fallback.
        
        Args:
            state: Workflow state
            
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
                    required=True,
                    category="template",
                    verification_type="custom"
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
            
        # If no steps found, generate basic verification steps
        if not steps:
            logger.info("No template verification steps found, generating basic steps")
            steps = await self._generate_basic_verification_steps(state)
            
        return steps
    
    async def _generate_basic_verification_steps(self, state: WorkflowState) -> List[VerificationStep]:
        """
        Generate basic verification steps for an integration.
        
        Args:
            state: Workflow state
            
        Returns:
            List of basic verification steps
        """
        steps = []
        is_windows = state.system_context.get('is_windows', False) or 'win' in state.system_context.get('platform', {}).get('system', '').lower()
        
        # Check for installation directory
        install_dir = state.parameters.get("install_dir", "")
        if install_dir:
            script = f'Test-Path "{install_dir}" | Write-Output' if is_windows else f'[ -d "{install_dir}" ] && echo "Directory exists" || echo "Directory not found"'
            expected = 'True' if is_windows else 'Directory exists'
            
            steps.append(VerificationStep(
                name="Check Installation Directory",
                description=f"Verify installation directory {install_dir} exists",
                script=script,
                expected_result=expected,
                required=True,
                category="files",
                verification_type="existence"
            ))
        
        # Check for configuration directory
        config_path = state.parameters.get("config_path", "")
        if config_path:
            script = f'Test-Path "{config_path}" | Write-Output' if is_windows else f'[ -d "{config_path}" ] && echo "Directory exists" || echo "Directory not found"'
            expected = 'True' if is_windows else 'Directory exists'
            
            steps.append(VerificationStep(
                name="Check Configuration Directory",
                description=f"Verify configuration directory {config_path} exists",
                script=script,
                expected_result=expected,
                required=True,
                category="files",
                verification_type="existence"
            ))
        
        # Check for service
        service_name = state.parameters.get("service_name", state.integration_type)
        if is_windows:
            script = f'Get-Service "{service_name}" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Status'
            expected = 'Running'
            
            steps.append(VerificationStep(
                name="Check Service Status",
                description=f"Verify service {service_name} is running",
                script=script,
                expected_result=expected,
                required=True,
                category="services",
                verification_type="status"
            ))
        else:
            script = f'systemctl is-active {service_name} 2>/dev/null || echo "inactive"'
            expected = 'active'
            
            steps.append(VerificationStep(
                name="Check Service Status",
                description=f"Verify service {service_name} is running",
                script=script,
                expected_result=expected,
                required=True,
                category="services",
                verification_type="status"
            ))
        
        # Check for processes
        process_name = state.integration_type.lower()
        if is_windows:
            script = f'Get-Process | Where-Object {{ $_.ProcessName -like "*{process_name}*" }} | Measure-Object | Select-Object -ExpandProperty Count'
            
            steps.append(VerificationStep(
                name="Check Processes",
                description=f"Verify {process_name} processes are running",
                script=script,
                expected_result=None,  # Any non-zero count is valid
                required=False,
                category="processes",
                verification_type="count"
            ))
        else:
            script = f'ps aux | grep -i "{process_name}" | grep -v grep | wc -l'
            
            steps.append(VerificationStep(
                name="Check Processes",
                description=f"Verify {process_name} processes are running",
                script=script,
                expected_result=None,  # Any non-zero count is valid
                required=False,
                category="processes",
                verification_type="count"
            ))
        
        return steps
    
    async def _generate_diagnostic_steps(
        self, 
        state: WorkflowState, 
        failed_step: VerificationStep,
        error: str
    ) -> List[VerificationStep]:
        """
        Generate diagnostic steps for a failed verification step using LLM.
        
        Args:
            state: Workflow state
            failed_step: Failed verification step
            error: Error message
            
        Returns:
            List of diagnostic steps
        """
        # Extract information about the failed step
        is_windows = state.system_context.get('is_windows', False) or 'win' in state.system_context.get('platform', {}).get('system', '').lower()
        
        # Prepare prompt for LLM
        prompt = f"""
        Generate diagnostic steps to investigate a failed verification for a New Relic {state.integration_type} integration.
        
        Failed verification step:
        {json.dumps(failed_step.to_dict(), indent=2)}
        
        Error message:
        {error}
        
        Integration details:
        - Type: {state.integration_type}
        - Target name: {state.target_name}
        - Platform: {"Windows" if is_windows else "Linux/Unix"}
        
        Generate 3-5 diagnostic steps to investigate the root cause of the failure, such as:
        1. Checking dependencies
        2. Examining more detailed logs
        3. Checking permissions
        4. Inspecting related configurations
        5. Testing related functionality
        
        For each step, specify:
        - A descriptive name with "Diagnostic: " prefix
        - A clear description of what is being diagnosed
        - A {"PowerShell" if is_windows else "Bash"} script to perform the diagnostic
        - Expected result is not needed (these are exploratory)
        - A reasonable timeout in seconds
        - Category should be "diagnostic"
        - Importance level should be "medium"
        - Verification type should be "diagnostic"
        
        Format your response as a JSON array of diagnostic step objects.
        """
        
        try:
            # Generate diagnostic steps using LLM
            diagnostic_steps = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert in diagnosing integration issues and generating diagnostic steps.",
                temperature=0.3  # Slightly higher temperature for more creative diagnostics
            )
            
            # Convert to VerificationStep objects
            steps = []
            
            if isinstance(diagnostic_steps, list):
                for step_data in diagnostic_steps:
                    steps.append(VerificationStep.from_dict(step_data))
            
            return steps
            
        except Exception as e:
            logger.warning(f"Error generating diagnostic steps: {e}")
            return []
    
    async def _run_diagnostic_steps(self, steps: List[VerificationStep], state: WorkflowState) -> Dict[str, Any]:
        """
        Run diagnostic steps and collect results.
        
        Args:
            steps: Diagnostic steps to run
            state: Workflow state
            
        Returns:
            Diagnostic results
        """
        results = {
            "steps": [],
            "findings": [],
            "possible_issues": []
        }
        
        for step in steps:
            logger.info(f"Running diagnostic step: {step.name}")
            
            start_time = datetime.now()
            result = await self.runner.run_step(step, state)
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Update step with execution data
            step.executed_at = start_time
            step.duration_ms = duration_ms
            step.result = result
            
            # Add to results
            step_result = {
                **step.to_dict(),
                "output": result.get("output", ""),
                "success": result.get("success", False)
            }
            
            results["steps"].append(step_result)
        
        # Use LLM to analyze diagnostic results
        if results["steps"]:
            diagnosis = await self._analyze_diagnostic_results(results["steps"], state)
            
            if diagnosis:
                results["findings"] = diagnosis.get("findings", [])
                results["possible_issues"] = diagnosis.get("possible_issues", [])
                results["recommendations"] = diagnosis.get("recommendations", [])
        
        return results
    
    async def _analyze_diagnostic_results(self, diagnostic_results: List[Dict[str, Any]], state: WorkflowState) -> Dict[str, Any]:
        """
        Analyze diagnostic results using the consolidated analysis manager.
        
        Args:
            diagnostic_results: Results from diagnostic steps
            state: Workflow state
            
        Returns:
            Analysis of diagnostic results
        """
        # Import the consolidated analysis manager
        from .analysis_manager import VerificationAnalysisManager
        
        # Create the analysis manager if not already set up
        analysis_manager = VerificationAnalysisManager(self.llm_service)
        
        # Extract the steps from diagnostic results
        passed_steps = [step for step in diagnostic_results if step.get("success", False)]
        failed_steps = [step for step in diagnostic_results if not step.get("success", False)]
        total_steps = len(diagnostic_results)
        
        # Prepare context information
        context = {
            "integration_type": state.integration_type,
            "target_name": state.target_name,
            "parameters": state.parameters,
            "workflow_id": getattr(state, "workflow_id", None)
        }
        
        # Use the consolidated analysis method with diagnostic type
        return await analysis_manager.analyze_verification_results(
            passed_steps=passed_steps,
            failed_steps=failed_steps,
            total_steps=total_steps,
            context=context,
            analysis_type="diagnostic"
        )
    
    async def _analyze_verification_results(
        self, 
        passed_steps: List[Dict[str, Any]], 
        failed_steps: List[Dict[str, Any]], 
        total_steps: int,
        state: WorkflowState,
        verification_type: str
    ) -> Dict[str, Any]:
        """
        Analyze verification results using the consolidated analysis manager.
        
        Args:
            passed_steps: Steps that passed
            failed_steps: Steps that failed
            total_steps: Total number of steps
            state: Workflow state
            verification_type: Type of verification
            
        Returns:
            Analysis of verification results
        """
        # Import the consolidated analysis manager
        from .analysis_manager import VerificationAnalysisManager
        
        # Create the analysis manager if not already set up
        analysis_manager = VerificationAnalysisManager(self.llm_service)
        
        # Prepare context information
        context = {
            "integration_type": state.integration_type,
            "target_name": state.target_name,
            "parameters": state.parameters,
            "workflow_id": getattr(state, "workflow_id", None)
        }
        
        # Use the consolidated analysis method
        return await analysis_manager.analyze_verification_results(
            passed_steps=passed_steps,
            failed_steps=failed_steps,
            total_steps=total_steps,
            context=context,
            analysis_type=verification_type
        )
