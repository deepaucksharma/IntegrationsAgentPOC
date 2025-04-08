"""
LLM-driven verification agent with adaptive verification strategy.
"""
import logging
import os
import json
import time
import asyncio
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

from ..core.state import WorkflowState, WorkflowStatus
from ..error.exceptions import VerificationError
from ..llm.service import LLMService, LLMProvider
from .manager import VerificationStep

logger = logging.getLogger(__name__)

class LLMVerifier:
    """
    Advanced verification agent that uses LLM to dynamically generate and adapt verification strategies.
    """
    
    def __init__(
        self, 
        llm_service: Optional[LLMService] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the LLM verifier.
        
        Args:
            llm_service: LLM service
            config: Configuration
        """
        self.config = config or {}
        self.llm_service = llm_service or LLMService()
        
        # Directory for storing verification patterns and results
        self.verification_dir = Path(self.config.get("verification_dir", "verification"))
        self.verification_dir.mkdir(exist_ok=True)
        
        # Cache for verification strategies
        self.verification_cache = {}
        
        # Learning store for successful verification patterns
        self.learning_store = {}
        
        logger.info("LLM-driven verifier initialized")
    
    async def verify(self, state: WorkflowState) -> WorkflowState:
        """
        Verify an integration using adaptive LLM-driven strategy.
        
        Args:
            state: Workflow state
            
        Returns:
            Updated workflow state with verification results
        """
        logger.info(f"Starting LLM-driven verification for {state.integration_type}/{state.target_name}")
        
        try:
            # 1. Generate verification context
            context = await self._create_verification_context(state)
            
            # 2. Generate verification strategy
            verification_steps = await self._generate_verification_strategy(state, context)
            
            if not verification_steps:
                logger.warning(f"No verification steps generated for {state.integration_type}")
                return state.add_warning("No verification steps were generated")
                
            logger.info(f"Generated {len(verification_steps)} verification steps")
            
            # 3. Execute verification steps
            updated_state = state
            verification_results = []
            passed_count = 0
            failed_steps = []
            
            for i, step in enumerate(verification_steps):
                logger.info(f"Executing verification step {i+1}/{len(verification_steps)}: {step.name}")
                
                # Execute the step
                result = await self._execute_verification_step(step, updated_state)
                verification_results.append(result)
                
                # Process result
                if result["success"]:
                    passed_count += 1
                    updated_state = updated_state.add_message(f"Verification step passed: {step.name}")
                else:
                    failure_message = f"Verification step failed: {step.name} - {result.get('error', 'Unknown error')}"
                    logger.warning(failure_message)
                    failed_steps.append({
                        "step": step.name,
                        "error": result.get("error", "Unknown error"),
                        "output": result.get("output", ""),
                        "required": step.required
                    })
                    
                    # Add warning or error based on whether step is required
                    if step.required:
                        updated_state = updated_state.add_warning(failure_message)
                    else:
                        updated_state = updated_state.add_message(failure_message)
                        
                # Run adaptive verification if configured and step failed
                if not result["success"] and self.config.get("adaptive_verification", True):
                    logger.info(f"Running adaptive verification for failed step: {step.name}")
                    adaptive_result = await self._run_adaptive_verification(step, result, updated_state, context)
                    
                    if adaptive_result.get("success", False):
                        logger.info(f"Adaptive verification succeeded for {step.name}")
                        passed_count += 1
                        updated_state = updated_state.add_message(
                            f"Adaptive verification passed for: {step.name} - {adaptive_result.get('message', '')}"
                        )
                        
                        # Remove from failed steps if it was there
                        failed_steps = [fs for fs in failed_steps if fs["step"] != step.name]
                    else:
                        logger.warning(f"Adaptive verification also failed for {step.name}")
                
            # 4. Generate verification summary with LLM
            verification_summary = await self._generate_verification_summary(
                verification_steps, 
                verification_results,
                failed_steps,
                state,
                context
            )
            
            # 5. Update state with verification results
            updated_state = updated_state.set_verification_result(
                "llm_verification", 
                verification_summary
            )
            
            # 6. Determine overall verification status
            if verification_summary["overall_status"] == "passed":
                logger.info(f"Verification passed: {passed_count}/{len(verification_steps)} steps succeeded")
                return updated_state.mark_completed()
            elif verification_summary["overall_status"] == "partially_passed":
                logger.warning(f"Verification partially passed: {passed_count}/{len(verification_steps)} steps succeeded")
                return updated_state.mark_partially_completed().add_warning(
                    "Verification partially passed - non-critical issues detected"
                )
            else:
                error_message = f"Verification failed: {passed_count}/{len(verification_steps)} steps succeeded. "
                error_message += verification_summary.get("failure_reason", "Critical verification checks failed")
                logger.error(error_message)
                return updated_state.set_error(error_message)
                
        except Exception as e:
            logger.error(f"Error during LLM verification: {e}", exc_info=True)
            return state.set_error(f"Verification error: {str(e)}")
    
    async def verify_uninstall(self, state: WorkflowState) -> WorkflowState:
        """
        Verify uninstallation using LLM-driven verification.
        
        Args:
            state: Workflow state
            
        Returns:
            Updated workflow state with verification results
        """
        logger.info(f"Starting LLM-driven uninstall verification for {state.integration_type}")
        
        try:
            # Create context specific to uninstall verification
            context = await self._create_verification_context(state)
            context["verification_type"] = "uninstall"
            
            # Generate verification strategy specific to uninstall
            verification_steps = await self._generate_uninstall_verification_strategy(state, context)
            
            if not verification_steps:
                logger.warning(f"No uninstall verification steps generated for {state.integration_type}")
                return state.add_warning("No uninstall verification steps were generated")
                
            logger.info(f"Generated {len(verification_steps)} uninstall verification steps")
            
            # Execute verification steps (similar to regular verify)
            updated_state = state
            verification_results = []
            passed_count = 0
            failed_steps = []
            
            for i, step in enumerate(verification_steps):
                logger.info(f"Executing uninstall verification step {i+1}/{len(verification_steps)}: {step.name}")
                
                # Execute the step
                result = await self._execute_verification_step(step, updated_state)
                verification_results.append(result)
                
                # Process result
                if result["success"]:
                    passed_count += 1
                    updated_state = updated_state.add_message(f"Uninstall verification step passed: {step.name}")
                else:
                    failure_message = f"Uninstall verification step failed: {step.name} - {result.get('error', 'Unknown error')}"
                    logger.warning(failure_message)
                    failed_steps.append({
                        "step": step.name,
                        "error": result.get("error", "Unknown error"),
                        "output": result.get("output", ""),
                        "required": step.required
                    })
                    
                    # For uninstall verification, steps are generally less critical
                    updated_state = updated_state.add_warning(failure_message)
            
            # Generate verification summary
            verification_summary = await self._generate_verification_summary(
                verification_steps, 
                verification_results,
                failed_steps,
                state,
                context
            )
            
            # Update state with verification results
            updated_state = updated_state.set_verification_result(
                "llm_uninstall_verification", 
                verification_summary
            )
            
            # For uninstall, we're more lenient with failures as remnants may be acceptable
            if verification_summary["overall_status"] in ["passed", "partially_passed"]:
                logger.info(f"Uninstall verification passed: {passed_count}/{len(verification_steps)} steps succeeded")
                return updated_state.mark_completed()
            else:
                warning_message = f"Uninstall verification found issues: {passed_count}/{len(verification_steps)} steps succeeded. "
                warning_message += verification_summary.get("failure_reason", "Some components may not be fully removed")
                logger.warning(warning_message)
                
                # For uninstall verification, we treat failures as warnings unless configured otherwise
                if self.config.get("strict_uninstall_verification", False):
                    return updated_state.set_error(warning_message)
                else:
                    return updated_state.mark_completed().add_warning(warning_message)
                
        except Exception as e:
            logger.error(f"Error during LLM uninstall verification: {e}", exc_info=True)
            return state.set_error(f"Uninstall verification error: {str(e)}")
    
    async def verify_system_clean(self, state: WorkflowState) -> WorkflowState:
        """
        Verify system is clean after recovery or rollback.
        
        Args:
            state: Workflow state
            
        Returns:
            Updated workflow state with verification results
        """
        # System clean verification is very similar to uninstall verification
        return await self.verify_uninstall(state)
    
    async def _create_verification_context(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Create verification context with system and integration details.
        
        Args:
            state: Workflow state
            
        Returns:
            Verification context
        """
        # Extract platform details
        platform_info = state.system_context.get('platform', {})
        is_windows = state.system_context.get('is_windows', False) or 'win' in platform_info.get('system', '').lower()
        
        # Extract integration details
        integration_details = {
            "type": state.integration_type,
            "name": state.target_name,
            "action": state.action,
            "parameters": state.parameters
        }
        
        # Extract changes made during installation
        installation_changes = []
        for change in state.changes:
            installation_changes.append({
                "type": change.type,
                "target": change.target,
                "timestamp": change.timestamp.isoformat() if hasattr(change.timestamp, 'isoformat') else str(change.timestamp)
            })
        
        # Extract documentation for verification
        verification_docs = {}
        if state.template_data and "definition" in state.template_data:
            definition = state.template_data["definition"]
            
            if "verification" in definition:
                verification_docs["steps"] = definition["verification"]
                
            if "installation" in definition:
                verification_docs["installation"] = definition["installation"]
                
            if "configuration" in definition:
                verification_docs["configuration"] = definition["configuration"]
        
        # Extract script if available
        script_excerpt = ""
        if state.script:
            # Get first 1000 chars of script
            script_excerpt = state.script[:1000]
        
        # Extract output if available
        output_excerpt = ""
        if state.output:
            # Get first 1000 chars of output
            output_excerpt = state.output.stdout[:1000] if hasattr(state.output, 'stdout') else str(state.output)[:1000]
        
        # Create context
        context = {
            "platform_info": platform_info,
            "is_windows": is_windows,
            "integration_details": integration_details,
            "installation_changes": installation_changes,
            "verification_docs": verification_docs,
            "script_excerpt": script_excerpt,
            "output_excerpt": output_excerpt,
            "verification_type": "standard"
        }
        
        return context
    
    async def _generate_verification_strategy(self, state: WorkflowState, context: Dict[str, Any]) -> List[VerificationStep]:
        """
        Generate verification strategy using LLM.
        
        Args:
            state: Workflow state
            context: Verification context
            
        Returns:
            List of verification steps
        """
        # Check cache for existing strategy
        cache_key = f"{state.integration_type}_{state.action}_verification"
        
        if cache_key in self.verification_cache and not self.config.get("skip_cache", False):
            logger.info(f"Using cached verification strategy for {cache_key}")
            return self.verification_cache[cache_key]
        
        # Generate verification strategy with LLM
        logger.info(f"Generating verification strategy for {state.integration_type} with LLM")
        
        # Create platform-specific section
        platform_section = ""
        if context["is_windows"]:
            platform_section = f"""
This integration is installed on Windows:
- Windows version: {context['platform_info'].get('version', 'Unknown')}
- PowerShell will be used for verification commands
"""
        else:
            platform_section = f"""
This integration is installed on a Unix-like system:
- OS: {context['platform_info'].get('system', 'Linux/Unix')}
- Distribution: {context['platform_info'].get('distribution', 'Unknown')}
- Shell scripts will be used for verification commands
"""
        
        # Create integration section
        integration_section = f"""
Integration details:
- Type: {state.integration_type}
- Name: {state.target_name}
- Action: {state.action}
- Parameters used: {json.dumps(state.parameters, indent=2)}
"""
        
        # Create changes section
        changes_section = ""
        if context["installation_changes"]:
            changes_section = "Changes made during installation:\n"
            
            for change in context["installation_changes"][:10]:  # Limit to first 10 changes
                changes_section += f"- {change['type']} to {change['target']}\n"
        
        # Create documentation section
        docs_section = ""
        if context["verification_docs"]:
            docs_section = "Verification documentation:\n"
            
            if "steps" in context["verification_docs"]:
                docs_section += "Documented verification steps:\n"
                for step in context["verification_docs"]["steps"]:
                    docs_section += f"- {step.get('description', '')}\n"
                    if "command" in step:
                        docs_section += f"  Command: {step['command']}\n"
                    if "expected_output" in step:
                        docs_section += f"  Expected: {step['expected_output']}\n"
        
        # Create prompt for verification strategy
        prompt = f"""
Generate a comprehensive verification strategy for a New Relic {state.integration_type} integration.

{platform_section}

{integration_section}

{changes_section}

{docs_section}

Create 5-10 verification steps that will thoroughly verify the integration is correctly installed and functioning.
Each step should include:
1. A descriptive name
2. A detailed description of what's being verified
3. The exact command to run for verification
4. Expected output or success criteria
5. Whether this step is required for verification to pass

For a Windows system, use PowerShell commands. For Unix-like systems, use Bash commands.
Include steps to verify:
- Installation files and directories
- Configuration files
- Services or processes
- Network connectivity
- Log files
- Integration functionality
- Any other relevant aspects

Format your response as a JSON array of verification step objects with these fields:
- name: Short name of the step
- description: Detailed description of what's being verified
- script: The exact command to run for verification
- expected_result: Expected output or success criteria
- required: Whether this step is required for verification to pass (boolean)
"""
        
        try:
            # Generate verification strategy
            strategy_json = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert in verifying New Relic integrations. Generate thorough, practical verification steps.",
                temperature=0.2
            )
            
            # Convert to verification steps
            verification_steps = []
            
            if isinstance(strategy_json, list):
                for step_data in strategy_json:
                    step = VerificationStep(
                        name=step_data.get("name", "Unnamed Step"),
                        description=step_data.get("description", ""),
                        script=step_data.get("script", ""),
                        expected_result=step_data.get("expected_result"),
                        required=step_data.get("required", True)
                    )
                    verification_steps.append(step)
            else:
                logger.warning("LLM did not return an array of verification steps")
                # Create a basic default verification step
                verification_steps.append(
                    VerificationStep(
                        name="Basic Verification",
                        description=f"Verify {state.integration_type} installation",
                        script="echo 'Verification running'",
                        expected_result=None,
                        required=True
                    )
                )
            
            # Cache the strategy
            self.verification_cache[cache_key] = verification_steps
            
            return verification_steps
            
        except Exception as e:
            logger.error(f"Error generating verification strategy: {e}", exc_info=True)
            # Return a basic default verification step
            return [
                VerificationStep(
                    name="Basic Verification",
                    description=f"Verify {state.integration_type} installation",
                    script="echo 'Verification running'",
                    expected_result=None,
                    required=True
                )
            ]
    
    async def _generate_uninstall_verification_strategy(self, state: WorkflowState, context: Dict[str, Any]) -> List[VerificationStep]:
        """
        Generate uninstall verification strategy using LLM.
        
        Args:
            state: Workflow state
            context: Verification context
            
        Returns:
            List of verification steps
        """
        # Similar to regular verification but with uninstall-specific focus
        cache_key = f"{state.integration_type}_uninstall_verification"
        
        if cache_key in self.verification_cache and not self.config.get("skip_cache", False):
            logger.info(f"Using cached uninstall verification strategy for {cache_key}")
            return self.verification_cache[cache_key]
        
        logger.info(f"Generating uninstall verification strategy for {state.integration_type} with LLM")
        
        # Create platform-specific section
        platform_section = ""
        if context["is_windows"]:
            platform_section = f"""
This integration was uninstalled from Windows:
- Windows version: {context['platform_info'].get('version', 'Unknown')}
- PowerShell will be used for verification commands
"""
        else:
            platform_section = f"""
This integration was uninstalled from a Unix-like system:
- OS: {context['platform_info'].get('system', 'Linux/Unix')}
- Distribution: {context['platform_info'].get('distribution', 'Unknown')}
- Shell scripts will be used for verification commands
"""
        
        # Create integration section
        integration_section = f"""
Integration details:
- Type: {state.integration_type}
- Name: {state.target_name}
- Parameters used: {json.dumps(state.parameters, indent=2)}
"""
        
        # Create changes section
        changes_section = ""
        if context["installation_changes"]:
            changes_section = "These changes should be reverted after uninstallation:\n"
            
            for change in context["installation_changes"][:10]:  # Limit to first 10 changes
                changes_section += f"- {change['type']} to {change['target']}\n"
        
        # Create prompt for uninstall verification strategy
        prompt = f"""
Generate a comprehensive uninstall verification strategy for a New Relic {state.integration_type} integration.

{platform_section}

{integration_section}

{changes_section}

Create 5-8 verification steps that will thoroughly verify the integration is completely uninstalled.
Each step should include:
1. A descriptive name
2. A detailed description of what's being verified
3. The exact command to run for verification
4. Expected output or success criteria (typically confirming absence of files, services, etc.)
5. Whether this step is required for verification to pass

For a Windows system, use PowerShell commands. For Unix-like systems, use Bash commands.
Include steps to verify:
- Installation files and directories have been removed
- Configuration files have been removed
- Services or processes are not running
- No remnants of the integration exist
- System is in a clean state

Format your response as a JSON array of verification step objects with these fields:
- name: Short name of the step
- description: Detailed description of what's being verified
- script: The exact command to run for verification
- expected_result: Expected output or success criteria
- required: Whether this step is required for verification to pass (boolean)
"""
        
        try:
            # Generate verification strategy
            strategy_json = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert in verifying New Relic integration uninstallations. Generate thorough verification steps.",
                temperature=0.2
            )
            
            # Convert to verification steps
            verification_steps = []
            
            if isinstance(strategy_json, list):
                for step_data in strategy_json:
                    step = VerificationStep(
                        name=step_data.get("name", "Unnamed Step"),
                        description=step_data.get("description", ""),
                        script=step_data.get("script", ""),
                        expected_result=step_data.get("expected_result"),
                        required=step_data.get("required", True)
                    )
                    verification_steps.append(step)
            else:
                logger.warning("LLM did not return an array of verification steps")
                # Create a basic default verification step
                verification_steps.append(
                    VerificationStep(
                        name="Basic Uninstall Verification",
                        description=f"Verify {state.integration_type} was uninstalled",
                        script="echo 'Uninstall verification running'",
                        expected_result=None,
                        required=True
                    )
                )
            
            # Cache the strategy
            self.verification_cache[cache_key] = verification_steps
            
            return verification_steps
            
        except Exception as e:
            logger.error(f"Error generating uninstall verification strategy: {e}", exc_info=True)
            # Return a basic default verification step
            return [
                VerificationStep(
                    name="Basic Uninstall Verification",
                    description=f"Verify {state.integration_type} uninstallation",
                    script="echo 'Uninstall verification running'",
                    expected_result=None,
                    required=True
                )
            ]
    
    async def _execute_verification_step(self, step: VerificationStep, state: WorkflowState) -> Dict[str, Any]:
        """
        Execute a verification step.
        
        Args:
            step: Verification step
            state: Workflow state
            
        Returns:
            Result of verification step
        """
        logger.info(f"Executing verification step: {step.name}")
        
        # Check for empty script
        if not step.script:
            return {
                "step": step.name,
                "success": False,
                "error": "Verification script is empty",
                "output": "",
                "expected": step.expected_result
            }
        
        # Determine execution environment
        is_windows = state.system_context.get('is_windows', False) or 'win' in state.system_context.get('platform', {}).get('system', '').lower()
        
        try:
            # Create temporary script file
            script_dir = Path("generated_scripts")
            script_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if is_windows:
                script_path = script_dir / f"verify_{timestamp}.ps1"
                with open(script_path, "w") as f:
                    f.write(step.script)
                
                # Execute PowerShell script
                cmd = f'powershell.exe -ExecutionPolicy Bypass -File "{script_path}"'
            else:
                script_path = script_dir / f"verify_{timestamp}.sh"
                with open(script_path, "w") as f:
                    f.write("#!/bin/bash\n")
                    f.write(step.script)
                
                # Make executable
                os.chmod(script_path, 0o755)
                
                # Execute shell script
                cmd = f'bash "{script_path}"'
            
            # Execute the script
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for process to complete with timeout
            timeout = self.config.get("verification_timeout", 60)
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
                stdout_str = stdout.decode().strip()
                stderr_str = stderr.decode().strip()
                exit_code = process.returncode
            except asyncio.TimeoutError:
                # Kill the process if it times out
                try:
                    process.kill()
                except Exception:
                    pass
                
                return {
                    "step": step.name,
                    "success": False,
                    "error": f"Verification timed out after {timeout} seconds",
                    "output": "",
                    "expected": step.expected_result
                }
            
            # Check if verification was successful
            success = False
            error_message = ""
            
            if exit_code == 0:
                # If no expected result, exit code 0 is success
                if not step.expected_result:
                    success = True
                else:
                    # Check stdout against expected result
                    if re.search(re.escape(step.expected_result), stdout_str, re.IGNORECASE):
                        success = True
                    else:
                        error_message = f"Output does not match expected result: {step.expected_result}"
            else:
                error_message = f"Script exited with code {exit_code}"
                
                if stderr_str:
                    error_message += f": {stderr_str}"
            
            # Create result
            result = {
                "step": step.name,
                "success": success,
                "error": error_message,
                "output": stdout_str,
                "stderr": stderr_str,
                "exit_code": exit_code,
                "expected": step.expected_result
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing verification step: {e}", exc_info=True)
            return {
                "step": step.name,
                "success": False,
                "error": f"Verification execution error: {str(e)}",
                "output": "",
                "expected": step.expected_result
            }
    
    async def _run_adaptive_verification(
        self, 
        step: VerificationStep, 
        result: Dict[str, Any], 
        state: WorkflowState,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run adaptive verification for a failed step.
        
        Args:
            step: Original verification step
            result: Original verification result
            state: Workflow state
            context: Verification context
            
        Returns:
            Result of adaptive verification
        """
        logger.info(f"Running adaptive verification for failed step: {step.name}")
        
        is_windows = context["is_windows"]
        
        prompt = f"""
A verification step failed for a New Relic {state.integration_type} integration. Generate an alternative verification approach.

Failed verification step:
- Name: {step.name}
- Description: {step.description}
- Script: {step.script}
- Expected Result: {step.expected_result}

Failure details:
- Error: {result.get('error', 'Unknown error')}
- Output: {result.get('output', '')}
- Exit Code: {result.get('exit_code', 'Unknown')}

Generate an alternative verification command that:
1. Checks for the same component or functionality from a different angle
2. Uses a different approach or command
3. Has more robust error handling
4. Has more relaxed matching criteria if appropriate

Target system: {"Windows" if is_windows else "Unix/Linux"}

Format your response as a JSON object with:
- name: Short name of the alternative verification step
- description: Detailed description of what's being verified
- script: The exact command to run for verification
- expected_result: Expected output or success criteria (can be null if not needed)
"""
        
        try:
            # Generate alternative verification approach
            alternative_json = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert in troubleshooting verification failures. Generate effective alternative verification approaches.",
                temperature=0.3
            )
            
            if not isinstance(alternative_json, dict) or "script" not in alternative_json:
                logger.warning("LLM did not return a valid alternative verification step")
                return {
                    "success": False,
                    "error": "Failed to generate alternative verification"
                }
            
            # Create alternative verification step
            alternative_step = VerificationStep(
                name=alternative_json.get("name", f"Alternative {step.name}"),
                description=alternative_json.get("description", "Alternative verification approach"),
                script=alternative_json.get("script", ""),
                expected_result=alternative_json.get("expected_result"),
                required=step.required
            )
            
            # Execute alternative verification step
            alternative_result = await self._execute_verification_step(alternative_step, state)
            
            if alternative_result["success"]:
                logger.info(f"Alternative verification succeeded: {alternative_step.name}")
                
                # Learn from successful alternative
                self._learn_from_successful_alternative(step, alternative_step, state.integration_type)
                
                return {
                    "success": True,
                    "message": f"Alternative verification successful: {alternative_step.name}",
                    "alternative_step": alternative_step.to_dict(),
                    "result": alternative_result
                }
            else:
                logger.warning(f"Alternative verification also failed: {alternative_step.name}")
                return {
                    "success": False,
                    "error": f"Alternative verification failed: {alternative_result.get('error', 'Unknown error')}",
                    "alternative_step": alternative_step.to_dict(),
                    "result": alternative_result
                }
                
        except Exception as e:
            logger.error(f"Error in adaptive verification: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Adaptive verification error: {str(e)}"
            }
    
    async def _generate_verification_summary(
        self,
        steps: List[VerificationStep],
        results: List[Dict[str, Any]],
        failed_steps: List[Dict[str, Any]],
        state: WorkflowState,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate verification summary using LLM.
        
        Args:
            steps: Verification steps
            results: Verification results
            failed_steps: Failed steps
            state: Workflow state
            context: Verification context
            
        Returns:
            Verification summary
        """
        logger.info("Generating verification summary with LLM")
        
        # Count required failures
        required_failures = [step for step in failed_steps if step.get("required", True)]
        
        # Create results summary
        results_summary = []
        for i, result in enumerate(results):
            if i < len(steps):
                step = steps[i]
                results_summary.append({
                    "step": step.name,
                    "description": step.description,
                    "success": result.get("success", False),
                    "error": result.get("error", ""),
                    "required": step.required
                })
        
        # Create prompt for verification summary
        prompt = f"""
Analyze the results of a verification process for a New Relic {state.integration_type} integration and provide a comprehensive summary.

Integration details:
- Type: {state.integration_type}
- Name: {state.target_name}
- Action: {state.action}

Verification results summary:
{json.dumps(results_summary, indent=2)}

Failed steps:
{json.dumps(failed_steps, indent=2)}

Generate a verification summary that includes:
1. Overall assessment of the integration state
2. Analysis of the failed steps and their impact
3. Possible reasons for any failures
4. Recommendations for addressing issues
5. An overall status: "passed", "partially_passed", or "failed"

Format your response as a JSON object with these fields:
- overall_status: "passed", "partially_passed", or "failed"
- passed_count: Number of passed steps
- failed_count: Number of failed steps
- critical_failures: Number of required steps that failed
- integration_state: Brief description of the integration state
- failure_reason: Summary of why verification failed (if applicable)
- recommendations: Array of recommendations to address issues
- potential_causes: Array of potential causes for failures
"""
        
        try:
            # Generate verification summary
            summary_json = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert in analyzing New Relic integration verification results. Provide clear, insightful analysis.",
                temperature=0.2
            )
            
            # Ensure the summary has the required fields
            if not isinstance(summary_json, dict):
                logger.warning("LLM did not return a valid verification summary")
                # Create a basic summary
                summary_json = {
                    "overall_status": "failed" if required_failures else "partially_passed",
                    "passed_count": len(steps) - len(failed_steps),
                    "failed_count": len(failed_steps),
                    "critical_failures": len(required_failures),
                    "integration_state": "Unknown",
                    "failure_reason": "Failed to generate verification summary",
                    "recommendations": [],
                    "potential_causes": []
                }
            else:
                # Ensure all required fields are present
                required_fields = [
                    "overall_status", "passed_count", "failed_count", 
                    "critical_failures", "integration_state", 
                    "recommendations", "potential_causes"
                ]
                
                for field in required_fields:
                    if field not in summary_json:
                        if field in ["recommendations", "potential_causes"]:
                            summary_json[field] = []
                        elif field in ["passed_count", "failed_count", "critical_failures"]:
                            summary_json[field] = 0
                        else:
                            summary_json[field] = "Unknown"
            
            # Add timestamp
            summary_json["timestamp"] = datetime.now().isoformat()
            
            # Add verification context
            summary_json["context"] = {
                "integration_type": state.integration_type,
                "target_name": state.target_name,
                "action": state.action,
                "verification_type": context.get("verification_type", "standard")
            }
            
            return summary_json
            
        except Exception as e:
            logger.error(f"Error generating verification summary: {e}", exc_info=True)
            # Create a basic summary
            return {
                "overall_status": "failed" if required_failures else "partially_passed",
                "passed_count": len(steps) - len(failed_steps),
                "failed_count": len(failed_steps),
                "critical_failures": len(required_failures),
                "integration_state": "Unknown",
                "failure_reason": f"Error generating verification summary: {str(e)}",
                "recommendations": [],
                "potential_causes": [],
                "timestamp": datetime.now().isoformat()
            }
    
    def _learn_from_successful_alternative(self, original_step: VerificationStep, alternative_step: VerificationStep, integration_type: str) -> None:
        """
        Learn from successful alternative verification steps.
        
        Args:
            original_step: Original failed verification step
            alternative_step: Successful alternative step
            integration_type: Integration type
        """
        if integration_type not in self.learning_store:
            self.learning_store[integration_type] = {
                "alternative_steps": [],
                "common_failures": {},
                "successful_patterns": []
            }
        
        # Add alternative step
        self.learning_store[integration_type]["alternative_steps"].append({
            "original": {
                "name": original_step.name,
                "script": original_step.script,
                "expected_result": original_step.expected_result
            },
            "alternative": {
                "name": alternative_step.name,
                "script": alternative_step.script,
                "expected_result": alternative_step.expected_result
            }
        })
        
        # Track common failures
        command_type = "powershell" if "powershell" in original_step.script.lower() else "bash"
        
        if command_type not in self.learning_store[integration_type]["common_failures"]:
            self.learning_store[integration_type]["common_failures"][command_type] = {}
        
        # Extract command pattern
        command_pattern = ""
        try:
            # Extract first word of command
            command_pattern = original_step.script.strip().split()[0]
        except:
            command_pattern = "unknown"
        
        if command_pattern not in self.learning_store[integration_type]["common_failures"][command_type]:
            self.learning_store[integration_type]["common_failures"][command_type][command_pattern] = 0
            
        self.learning_store[integration_type]["common_failures"][command_type][command_pattern] += 1
        
        logger.debug(f"Updated learning store for {integration_type}")
