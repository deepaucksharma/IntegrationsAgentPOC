import logging
import abc
from typing import Dict, Any, Optional, List, Type

from ..core.state import WorkflowState

logger = logging.getLogger(__name__)

class ScriptGeneratorStrategy(abc.ABC):
    """Base abstract class for script generator strategies."""    
    @abc.abstractmethod
    async def generate(self, state: WorkflowState, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a script for the given state.
        
        Args:
            state: Workflow state
            config: Configuration dictionary
            
        Returns:
            Dictionary with script and optional metadata
        """
        raise NotImplementedError
    
    @classmethod
    @abc.abstractmethod
    def can_handle(cls, state: WorkflowState) -> bool:
        """
        Determine if this strategy can handle the given state.
        
        Args:
            state: Workflow state
            
        Returns:
            True if this strategy can handle the state
        """
        raise NotImplementedError

class TemplateScriptGenerator(ScriptGeneratorStrategy):
    """Generate scripts from templates."""    
    def __init__(self, template_renderer):
        self.template_renderer = template_renderer
    
    async def generate(self, state: WorkflowState, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate script from a template."""
        try:
            if not state.template_path:
                return {"error": "No template path provided"}
            
            logger.debug(f"Generating script from template: {state.template_path}")
            
            # Render template with state data
            template_context = {
                "action": state.action,
                "target_name": state.target_name,
                "parameters": state.parameters,
                "template_data": state.template_data or {},
                "verification_data": state.verification_data or {}
            }
            
            script = await self.template_renderer.render_template(
                template_path=state.template_path,
                context=template_context
            )
            
            if not script:
                return {"error": f"Failed to render template: {state.template_path}"}
                
            return {
                "script": script,
                "template_key": state.template_path
            }
            
        except Exception as e:
            logger.error(f"Error generating script from template: {e}")
            return {"error": f"Template generation error: {str(e)}"}
    
    @classmethod
    def can_handle(cls, state: WorkflowState) -> bool:
        """Check if this strategy can handle the state."""
        return state.template_path is not None and state.template_path != ""

class DynamicScriptGenerator(ScriptGeneratorStrategy):
    """Generate scripts dynamically based on integration knowledge."""    
    def __init__(self, knowledge_base=None):
        self.knowledge_base = knowledge_base
    
    async def generate(self, state: WorkflowState, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate script dynamically."""
        try:
            logger.debug(f"Generating dynamic script for {state.action} on {state.target_name}")
            
            # Check if we have knowledge data
            if not state.template_data or not state.template_data.get("docs"):
                return {"error": "Insufficient knowledge data for dynamic script generation"}
            
            # Get platform information
            platform_info = state.template_data.get("platform_info", {})
            system = platform_info.get("system", "").lower()
            
            # Get available methods and select one if not already selected
            selected_method = state.template_data.get("selected_method")
            if not selected_method:
                methods = state.template_data.get("platform_specific", {}).get("installation_methods", [])
                if not methods:
                    methods = state.template_data.get("docs", {}).get("installation_methods", [])
                    
                if not methods:
                    return {"error": "No installation methods available"}
                    
                # Select first method (better selection would be done by strategy agent)
                selected_method = methods[0]
            
            # Generate appropriate script header
            script_lines = []
            
            # Add platform-specific header
            if "windows" in system:
                script_lines.extend([
                    "# Windows script",
                    "Set-ExecutionPolicy Bypass -Scope Process -Force",
                    "$ErrorActionPreference = \"Stop\"",
                    "function Log-Message($message) {",
                    "    Write-Host \"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $message\"",
                    "}",
                    ""
                ])
            else:
                script_lines.extend([
                    "#!/bin/bash",
                    "set -e",
                    "",
                    "log_message() {",
                    "    echo \"[$(date '+%Y-%m-%d %H:%M:%S')] $1\"",
                    "}",
                    ""
                ])
            
            # Add action information
            script_lines.append(f"log_message \"Starting {state.action} for {state.target_name}\"")
            script_lines.append("")
            
            # Add parameters
            script_lines.append("# Parameters")
            for key, value in state.parameters.items():
                if "windows" in system:
                    script_lines.append(f"$param_{key} = \"{value}\"")
                else:
                    script_lines.append(f"param_{key}=\"{value}\"")
            
            script_lines.append("")
            
            # Add method steps
            script_lines.append("# Installation steps")
            steps = selected_method.get("steps", [])
            for i, step in enumerate(steps, 1):
                # Get step details
                if isinstance(step, dict):
                    step_name = step.get("name", f"Step {i}")
                    step_cmd = step.get("command", "")
                else:
                    step_name = f"Step {i}"
                    step_cmd = step
                
                if not step_cmd:
                    continue
                    
                # Process step command - replace parameters
                for key, value in state.parameters.items():
                    placeholder = "{{ parameters." + key + " }}"
                    step_cmd = step_cmd.replace(placeholder, str(value))
                
                # Add step to script
                script_lines.append("")
                script_lines.append(f"log_message \"Executing: {step_name}\"")
                script_lines.append(step_cmd)
            
            # Add verification if it's an installation
            if state.action in ["install", "setup"]:
                script_lines.append("")
                script_lines.append("# Verification")
                verification_steps = state.template_data.get("docs", {}).get("verification_steps", [])
                
                if not verification_steps:
                    script_lines.append('log_message "No verification steps available"')
                else:
                    for i, step in enumerate(verification_steps, 1):
                        if isinstance(step, str):
                            # Process verification step - replace parameters
                            for key, value in state.parameters.items():
                                placeholder = "{{ parameters." + key + " }}"
                                step = step.replace(placeholder, str(value))
                                
                            script_lines.append(f'log_message "Verification step {i}"')
                            script_lines.append(step)
            
            # Add completion message
            script_lines.append("")
            script_lines.append(f'log_message "{state.action.capitalize()} completed successfully"')
            
            # Combine script lines
            script = "\n".join(script_lines)
            
            return {
                "script": script,
                "generated": "dynamic"
            }
            
        except Exception as e:
            logger.error(f"Error generating dynamic script: {e}")
            return {"error": f"Dynamic generation error: {str(e)}"}
    
    @classmethod
    def can_handle(cls, state: WorkflowState) -> bool:
        """Check if this strategy can handle the state."""
        # Can handle any state with template_data and docs
        docs_present = (
            state.template_data is not None and 
            state.template_data.get("docs") is not None
        )
        
        # And needs to be a common action
        common_actions = ["install", "setup", "remove", "uninstall", "verify"]
        return docs_present and state.action in common_actions

class ScriptGeneratorFactory:
    """Factory for creating script generators."""
    
    _strategies: List[Type[ScriptGeneratorStrategy]] = []
    
    @classmethod
    def register_strategy(cls, strategy_class: Type[ScriptGeneratorStrategy]) -> None:
        """Register a strategy class."""
        if strategy_class not in cls._strategies:
            cls._strategies.append(strategy_class)
    
    @classmethod
    def create_for_state(cls, state: WorkflowState) -> Optional[ScriptGeneratorStrategy]:
        """Create appropriate generator for the state."""
        for strategy_class in cls._strategies:
            if strategy_class.can_handle(state):
                # This would need actual initialization logic to pass dependencies
                # For now, we use a placeholder
                return strategy_class()
        
        return None

# Register standard strategies
ScriptGeneratorFactory.register_strategy(TemplateScriptGenerator)
ScriptGeneratorFactory.register_strategy(DynamicScriptGenerator) 