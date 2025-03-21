"""LLM-driven script generation for workflow agent."""
import logging
import os
import json
from typing import Dict, Any, Optional, List, Tuple
import asyncio
import traceback
from datetime import datetime

from ..core.state import WorkflowState
from ..config.configuration import ensure_workflow_config
from ..error.exceptions import ScriptError, ErrorContext
from ..utils.system import get_system_context
from .minimal_templates import get_minimal_template, build_parameter_list, build_parameter_verification, build_prerequisite_checks, build_verification_steps

logger = logging.getLogger(__name__)

class LLMScriptGenerator:
    """Generates scripts using LLM with minimal templating."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        """
        Initialize the LLM script generator.
        
        Args:
            api_key: Optional API key for LLM service
            model: LLM model to use for generation
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.llm_client = None
        self.template_headers = {
            "linux": "#!/bin/bash\nset -e\ntrap 'echo \"Error on line $LINENO\"' ERR\n\n",
            "windows": "# PowerShell script\nSet-ExecutionPolicy Bypass -Scope Process -Force\n$ErrorActionPreference = \"Stop\"\n\n"
        }
        self.max_retries = 2
        self.initialized = False
        
    async def initialize(self) -> None:
        """Initialize the LLM client."""
        try:
            if self.initialized:
                return
                
            # Import dynamically to make the dependency optional
            if self.api_key:
                try:
                    from langchain_openai import ChatOpenAI
                    from langchain.schema import HumanMessage, SystemMessage
                    
                    self.llm_client = ChatOpenAI(
                        model=self.model,
                        openai_api_key=self.api_key,
                        temperature=0.2  # Low temperature for more deterministic output
                    )
                    logger.info(f"Initialized LLM client with model: {self.model}")
                    self.initialized = True
                except ImportError:
                    logger.error("Required packages for LLM generation not installed. Run 'pip install -e \".[llm]\"' to install dependencies.")
                    raise ScriptError("Required LLM packages not installed",
                                    context=ErrorContext(component="LLMScriptGenerator",
                                                      operation="initialize"),
                                    details={"fix": "Run 'pip install -e \".[llm]\"' to install dependencies"})
            else:
                logger.warning("No API key provided. LLM script generation will not be available.")
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise ScriptError("Failed to initialize LLM client",
                             context=ErrorContext(component="LLMScriptGenerator",
                                               operation="initialize"),
                             details={"error": str(e)})
    
    async def generate_script(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a script using LLM with minimal templating.
        
        Args:
            state: Workflow state containing context information
            config: Optional configuration parameters
            
        Returns:
            Dictionary containing generated script or error
        """
        if not self.api_key:
            logger.warning("No API key available. Falling back to template-based generation.")
            return {"error": "No API key available for LLM generation"}
            
        try:
            if not self.initialized:
                await self.initialize()
                
            if not self.llm_client:
                logger.warning("LLM client initialization failed.")
                return {"error": "LLM client initialization failed"}
            
            # Build context for the LLM
            context = await self._build_script_context(state)
            
            # Generate script with the LLM
            script = await self._generate_with_llm(context, state)
            
            if not script:
                logger.warning("LLM generation failed to produce a script.")
                return {"error": "LLM generation failed to produce a valid script"}
            
            # Validate generated script
            validation_result = await self._validate_script(script, state)
            if validation_result.get("error"):
                logger.warning(f"Script validation failed: {validation_result['error']}")
                if validation_result.get("fixable", False):
                    logger.info("Attempting to fix script issues...")
                    script = await self._fix_script_issues(script, validation_result, state)
                else:
                    return {"error": f"Script validation failed: {validation_result['error']}"}
            
            return {"script": script, "source": "llm"}
            
        except Exception as e:
            logger.error(f"Error generating script with LLM: {e}", exc_info=True)
            context = ErrorContext(
                component="LLMScriptGenerator",
                operation="generate_script",
                details={"error": str(e), "state": str(state)}
            )
            return {"error": f"LLM script generation failed: {str(e)}"}
    
    async def _build_script_context(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Build context information for script generation.
        
        Args:
            state: Workflow state
            
        Returns:
            Dictionary with context information for LLM
        """
        # Get platform information
        platform_info = state.system_context.get("platform", {})
        system = platform_info.get("system", "").lower()
        if "win" in system:
            system = "windows"
        elif "linux" in system or "unix" in system:
            system = "linux"
        elif "darwin" in system or "mac" in system:
            system = "macos"  # Normalize macOS system name
            # Note: We treat macOS like Linux for script generation purposes
        else:
            system = "linux"  # Default to Linux
        
        # Determine script type
        if system == "windows":
            script_type = "PowerShell"
            file_extension = ".ps1"
        else:
            script_type = "Bash"
            file_extension = ".sh"
        
        # Get integration details
        integration_name = state.target_name
        integration_type = state.integration_type
        action = state.action
        
        # Get documentation if available
        docs = state.template_data.get("docs", {})
        platform_specific = state.template_data.get("platform_specific", {})
        
        # Get any available installation methods
        methods = platform_specific.get("installation_methods", [])
        if not methods:
            methods = docs.get("installation_methods", [])
        
        # Get selected method if available
        selected_method = state.template_data.get("selected_method", {})
        if not selected_method and methods:
            selected_method = methods[0]
        
        # Compile context
        context = {
            "action": action,
            "integration_name": integration_name,
            "integration_type": integration_type,
            "target_name": state.target_name,
            "parameters": state.parameters,
            "system": system,
            "platform": platform_info,
            "script_type": script_type,
            "file_extension": file_extension,
            "installation_method": selected_method,
            "prerequisites": platform_specific.get("prerequisites", docs.get("prerequisites", [])),
            "verification_steps": docs.get("verification_steps", []),
            "configuration_options": docs.get("configuration_options", {}),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return context
    
    async def _generate_with_llm(self, context: Dict[str, Any], state: WorkflowState) -> Optional[str]:
        """
        Generate script using LLM.
        
        Args:
            context: Context information for script generation
            state: Workflow state
            
        Returns:
            Generated script or None if generation failed
        """
        # Import dynamically to keep the dependency optional
        try:
            from langchain.schema import HumanMessage, SystemMessage
        except ImportError:
            logger.error("langchain not installed. Cannot generate with LLM.")
            return None
        
        # Create prompt
        system_prompt = self._create_system_prompt(context)
        human_prompt = self._create_human_prompt(context, state)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        # Try generating with retries
        for attempt in range(self.max_retries + 1):
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, lambda: self.llm_client.invoke(messages))
                script = response.content
                
                # Add header if not present
                if context["system"] == "linux" and not script.startswith("#!/bin/bash"):
                    script = self.template_headers["linux"] + script
                elif context["system"] == "windows" and not (script.startswith("#") or script.startswith("Set-")):
                    script = self.template_headers["windows"] + script
                
                return script
            except Exception as e:
                logger.error(f"Error in LLM generation (attempt {attempt+1}/{self.max_retries+1}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(1)  # Wait before retry
                    continue
                return None
        
        return None  # Should not reach here, but just in case
    
    def _create_system_prompt(self, context: Dict[str, Any]) -> str:
        """Create system prompt for LLM."""
        if context["system"] == "windows":
            return """You are an expert PowerShell script writer specializing in system automation.
            Your task is to write a PowerShell script that handles the requested operation robustly.
            
            Guidelines:
            1. Include proper error handling with try/catch blocks
            2. Add detailed logging with timestamps
            3. Include verification steps to confirm successful operation
            4. Make the script idempotent when possible
            5. Use best practices for PowerShell
            6. Include comments explaining key sections
            7. Never use placeholders - provide fully functional code
            8. Structure the script with clear sections
            9. Return ONLY the script content without additional explanations
            """
        else:
            return """You are an expert Bash script writer specializing in system automation.
            Your task is to write a Bash script that handles the requested operation robustly.
            
            Guidelines:
            1. Include proper error handling with set -e and trap
            2. Add detailed logging with timestamps
            3. Include verification steps to confirm successful operation
            4. Make the script idempotent when possible
            5. Use best practices for shell scripting
            6. Include comments explaining key sections
            7. Never use placeholders - provide fully functional code
            8. Structure the script with clear sections
            9. Return ONLY the script content without additional explanations
            """
    
    def _create_human_prompt(self, context: Dict[str, Any], state: WorkflowState) -> str:
        """Create human prompt for LLM."""
        action = context["action"]
        integration_name = context["integration_name"]
        system = context["system"]
        
        prompt = f"Write a script to {action} the {integration_name} on {system} with these requirements:\n\n"
        
        # Add parameters
        prompt += "Parameters:\n"
        for name, value in context["parameters"].items():
            prompt += f"- {name}: {value}\n"
        
        # Add prerequisites if available
        if context["prerequisites"]:
            prompt += "\nPrerequisites to check and install if missing:\n"
            for prereq in context["prerequisites"]:
                if isinstance(prereq, dict) and "name" in prereq:
                    prompt += f"- {prereq['name']}\n"
                elif isinstance(prereq, str):
                    prompt += f"- {prereq}\n"
        
        # Add installation method steps if available
        if context["installation_method"] and "steps" in context["installation_method"]:
            prompt += "\nInstallation steps to follow:\n"
            for step in context["installation_method"]["steps"]:
                if isinstance(step, dict) and "command" in step:
                    prompt += f"- {step['command']}\n"
                elif isinstance(step, str):
                    prompt += f"- {step}\n"
        
        # Add verification steps if available
        if context["verification_steps"]:
            prompt += "\nVerification steps:\n"
            for step in context["verification_steps"]:
                if isinstance(step, dict) and "command" in step:
                    prompt += f"- {step['command']}\n"
                elif isinstance(step, str):
                    prompt += f"- {step}\n"
        
        # Add specific requirements based on action
        if action == "install":
            prompt += "\nRequirements:\n"
            prompt += "- Create appropriate directories\n"
            prompt += "- Download and configure the software\n"
            prompt += "- Set up appropriate permissions\n"
            prompt += "- Start any necessary services\n"
            prompt += "- Verify the installation is working\n"
        elif action == "remove" or action == "uninstall":
            prompt += "\nRequirements:\n"
            prompt += "- Stop any running services\n"
            prompt += "- Remove the software completely\n"
            prompt += "- Clean up any related files or configurations\n"
            prompt += "- Verify the removal is complete\n"
        elif action == "verify":
            prompt += "\nRequirements:\n"
            prompt += "- Check if the service is running\n"
            prompt += "- Validate all necessary components are present\n"
            prompt += "- Verify the configuration is correct\n"
            prompt += "- Report the status clearly\n"
        
        return prompt
    
    async def _validate_script(self, script: str, state: WorkflowState) -> Dict[str, Any]:
        """
        Validate the generated script.
        
        Args:
            script: Generated script content
            state: Workflow state
            
        Returns:
            Dictionary with validation results
        """
        # Basic validation
        result = {"valid": True}
        
        # Check for empty script
        if not script or len(script.strip()) < 50:
            result["valid"] = False
            result["error"] = "Generated script is too short or empty"
            result["fixable"] = False
            return result
        
        # Check for common script issues
        system = state.system_context.get("platform", {}).get("system", "").lower()
        if "win" in system:
            # Check PowerShell script
            if "Set-ExecutionPolicy" not in script:
                result["valid"] = False
                result["error"] = "Missing Set-ExecutionPolicy in PowerShell script"
                result["fixable"] = True
            if "$ErrorActionPreference" not in script:
                result["valid"] = False
                result["error"] = "Missing ErrorActionPreference in PowerShell script"
                result["fixable"] = True
        else:
            # Check Bash script
            if not script.startswith("#!/bin/bash") and not script.startswith("#!/usr/bin/env bash"):
                result["valid"] = False
                result["error"] = "Missing shebang in Bash script"
                result["fixable"] = True
            if "set -e" not in script:
                result["valid"] = False
                result["error"] = "Missing 'set -e' in Bash script"
                result["fixable"] = True
            if "trap" not in script:
                result["valid"] = False
                result["error"] = "Missing error trap in Bash script"
                result["fixable"] = True
        
        # Check for proper parameters usage
        for param_name in state.parameters:
            if param_name not in script:
                result["valid"] = False
                result["error"] = f"Parameter '{param_name}' not used in script"
                result["fixable"] = True
        
        return result
    
    async def _fix_script_issues(self, script: str, validation_result: Dict[str, Any], state: WorkflowState) -> str:
        """
        Fix common issues in the generated script.
        
        Args:
            script: Original script content
            validation_result: Validation results with identified issues
            state: Workflow state
            
        Returns:
            Fixed script
        """
        system = state.system_context.get("platform", {}).get("system", "").lower()
        
        # Apply fixes based on system
        if "win" in system:
            # Fix PowerShell script
            if "Set-ExecutionPolicy" not in script:
                script = "Set-ExecutionPolicy Bypass -Scope Process -Force\n" + script
            if "$ErrorActionPreference" not in script:
                script = "$ErrorActionPreference = \"Stop\"\n" + script
        else:
            # Fix Bash script
            if not script.startswith("#!/bin/bash") and not script.startswith("#!/usr/bin/env bash"):
                script = "#!/bin/bash\n" + script
            if "set -e" not in script:
                script = script.replace("#!/bin/bash", "#!/bin/bash\nset -e")
            if "trap" not in script:
                trap_line = "trap 'echo \"Error on line $LINENO\"' ERR\n"
                if "set -e" in script:
                    script = script.replace("set -e", f"set -e\n{trap_line}")
                else:
                    script = script.replace("#!/bin/bash", f"#!/bin/bash\n{trap_line}")
        
        # Make sure all parameters are used
        for param_name, param_value in state.parameters.items():
            if param_name not in script:
                if "win" in system:
                    # Add parameter to PowerShell script
                    param_line = f"$param_{param_name} = \"{param_value}\"\n"
                    script = script.replace("$ErrorActionPreference = \"Stop\"", 
                                            f"$ErrorActionPreference = \"Stop\"\n\n# Parameters\n{param_line}")
                else:
                    # Add parameter to Bash script
                    param_line = f"{param_name}=\"{param_value}\"\n"
                    script = script.replace("set -e", f"set -e\n\n# Parameters\n{param_line}")
        
        return script