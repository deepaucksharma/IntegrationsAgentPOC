"""
Script generation system with template-based and LLM-driven capabilities.
"""
import logging
import os
import json
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, PackageLoader, select_autoescape, TemplateNotFound
from pathlib import Path
from ..core.state import WorkflowState
from ..error.exceptions import ScriptError

logger = logging.getLogger(__name__)

class ScriptGenerator:
    """Base class for script generation."""

    def __init__(self, template_dir: Optional[str] = None):
        """Initialize script generator with template directory."""
        self.template_dir = template_dir or "./templates"
        self._setup_template_env()
        
    def _setup_template_env(self):
        """Set up the Jinja2 template environment."""
        try:
            # Create a list of template loaders
            template_loaders = []
            
            # Add the provided template directory if it exists
            template_dir = Path(self.template_dir)
            if template_dir.exists() and template_dir.is_dir():
                template_loaders.append(FileSystemLoader(str(template_dir)))
                logger.debug(f"Added template directory: {template_dir}")
                
            # Try to find common template directories
            alt_template_dirs = [
                Path("./integrations/common_templates"),
                Path("./src/workflow_agent/integrations/common_templates"),
                Path("./templates")
            ]
            
            for alt_dir in alt_template_dirs:
                if alt_dir.exists() and alt_dir.is_dir():
                    template_loaders.append(FileSystemLoader(str(alt_dir)))
                    logger.debug(f"Added alternative template directory: {alt_dir}")
            
            # Try to add package templates
            try:
                template_loaders.append(PackageLoader("workflow_agent", "templates"))
                logger.debug("Added package templates")
            except Exception as e:
                logger.debug(f"Failed to add package templates: {e}")
            
            # Create the Jinja2 environment with all loaders
            self.jinja_env = Environment(
                loader=ChoiceLoader(template_loaders),
                autoescape=select_autoescape(['html', 'xml']),
                trim_blocks=True,
                lstrip_blocks=True
            )
            
            logger.info("Template environment initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize template environment: {e}", exc_info=True)
            raise ScriptError(f"Template environment initialization failed: {e}")

    async def generate_script(self, state: WorkflowState) -> Dict[str, Any]:
        """Generate a script from a workflow state using templates."""
        try:
            logger.info(f"Generating {state.action} script for {state.target_name}")
            
            # Get template path
            template_path = self._resolve_template_path(state)
            if not template_path:
                return {"error": f"No template found for {state.action} action on {state.target_name}"}
            
            logger.debug(f"Using template: {template_path}")
            
            # Prepare template variables
            template_vars = self._prepare_template_variables(state)
            
            # Render the template
            template_name = Path(template_path).name
            try:
                template = self.jinja_env.get_template(f"{state.action}/{template_name}")
            except TemplateNotFound:
                # Try using default template instead
                is_windows = state.system_context.get("platform", {}).get("system", "").lower() == "windows"
                default_template = f"default.{'ps1' if is_windows else 'sh'}.j2"
                try:
                    template = self.jinja_env.get_template(f"{state.action}/{default_template}")
                    logger.warning(f"Template {template_name} not found, using default template: {default_template}")
                    template_name = default_template
                except TemplateNotFound:
                    return {"error": f"Template not found: {template_name} and no default template available"}
                
            script = template.render(**template_vars)
            
            # Save the generated script
            script_path = self._save_script(state, script)
            
            return {
                "success": True,
                "script": script,
                "script_path": str(script_path),
                "template_used": template_name
            }
        except Exception as e:
            logger.error(f"Error generating script: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
            
    def _resolve_template_path(self, state: WorkflowState) -> Optional[str]:
        """Resolve the template path based on the workflow state."""
        # Start with the template key from the state if available
        if state.template_key:
            return state.template_key
            
        # Check for Windows vs Linux platform-specific templates
        is_windows = state.system_context.get("platform", {}).get("system", "").lower() == "windows"
        ext = ".ps1.j2" if is_windows else ".sh.j2"
            
        # Try to construct a template path based on action and target
        template_paths = [
            f"{state.target_name}{ext}",
            f"{state.integration_type}{ext}",
            f"default{ext}"
        ]
        
        # Check if any of these templates exist
        for path in template_paths:
            try:
                full_path = f"{state.action}/{path}"
                if self.jinja_env.get_template(full_path):
                    return path
            except Exception:
                pass
                
        # Just return the most likely path even if it doesn't exist
        return f"{state.integration_type}{ext}"
            
    def _prepare_template_variables(self, state: WorkflowState) -> Dict[str, Any]:
        """Prepare variables for template rendering."""
        variables = {
            "action": state.action,
            "target_name": state.target_name,
            "integration_type": state.integration_type,
            "parameters": state.parameters,
            "system": state.system_context.get("platform", {}),
            "timestamp": self._get_timestamp()
        }
        
        # Add template data if available
        if state.template_data:
            variables.update(state.template_data)
            
        return variables
        
    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    def _save_script(self, state: WorkflowState, script: str) -> Path:
        """Save the generated script to a file."""
        # Create scripts directory if it doesn't exist
        script_dir = Path("generated_scripts")
        script_dir.mkdir(exist_ok=True)
        
        # Determine file extension based on platform
        is_windows = state.system_context.get("platform", {}).get("system", "").lower() == "windows"
        ext = ".ps1" if is_windows else ".sh"
        
        # Create filename
        timestamp = self._get_timestamp().replace(" ", "_").replace(":", "")
        filename = f"{state.target_name}_{state.action}_{timestamp}{ext}"
        
        # Save the script
        script_path = script_dir / filename
        with open(script_path, "w") as f:
            f.write(script)
            
        logger.info(f"Script saved to: {script_path}")
        return script_path
