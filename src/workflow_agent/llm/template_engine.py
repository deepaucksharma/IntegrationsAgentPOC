"""Template-based script generation engine."""
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import os
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, PackageLoader, select_autoescape
from ..core.state import WorkflowState
from ..error.exceptions import ScriptError

logger = logging.getLogger(__name__)

class TemplateEngine:
    """Generates scripts using templates."""
    
    def __init__(self, template_dir: Optional[str] = None):
        """Initialize template engine with template directory."""
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
            logger.info(f"Generating {state.action} script for {state.target_name} using template engine")
            
            # Try to get template from state
            template_path = None
            if state.template_key:
                template_path = state.template_key
            else:
                # Try to find an appropriate template
                template_path = self._resolve_template_path(state)
                
            if not template_path:
                return {
                    "success": False, 
                    "error": f"No template found for {state.action} action on {state.target_name}"
                }
                
            logger.debug(f"Using template: {template_path}")
            
            # Prepare template variables
            template_vars = self._prepare_template_variables(state)
            
            # Get just the filename from the template path
            template_name = Path(template_path).name
            
            # Try to get the template from the environment
            try:
                template = self.jinja_env.get_template(template_name)
            except Exception as e:
                logger.error(f"Failed to load template {template_name}: {e}")
                # Try alternate approach - look for template with exact path
                try:
                    # Try with and without .j2 extension
                    if not template_path.endswith(".j2"):
                        alt_path = template_path + ".j2"
                    else:
                        alt_path = template_path
                        
                    template = self.jinja_env.get_template(alt_path)
                except Exception as e2:
                    logger.error(f"Failed to load template with alternate path {alt_path}: {e2}")
                    return {"success": False, "error": f"Template not found: {template_path}"}
            
            # Render the template
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
        # Try to construct a template path based on action and target
        template_paths = [
            f"{state.action}/{state.target_name}.j2",
            f"{state.action}/{state.integration_type}.j2",
            f"{state.action}/default.j2"
        ]
        
        # Check for Windows vs Linux platform-specific templates
        is_windows = state.system_context.get("platform", {}).get("system", "").lower() == "windows"
        ext = ".ps1.j2" if is_windows else ".sh.j2"
        
        template_paths.extend([
            f"{state.action}/{state.target_name}{ext}",
            f"{state.action}/{state.integration_type}{ext}",
            f"{state.action}/default{ext}"
        ])
        
        # Check if any of these templates exist
        for path in template_paths:
            try:
                if self.jinja_env.get_template(path):
                    return path
            except Exception:
                pass
                
        return None
            
    def _prepare_template_variables(self, state: WorkflowState) -> Dict[str, Any]:
        """Prepare variables for template rendering."""
        from datetime import datetime
        
        variables = {
            "action": state.action,
            "target_name": state.target_name,
            "integration_type": state.integration_type,
            "parameters": state.parameters,
            "system": state.system_context.get("platform", {}),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Add template data if available
        if state.template_data:
            variables.update(state.template_data)
            
        return variables
            
    def _save_script(self, state: WorkflowState, script: str) -> Path:
        """Save the generated script to a file."""
        from datetime import datetime
        
        # Create scripts directory if it doesn't exist
        script_dir = Path("generated_scripts")
        script_dir.mkdir(exist_ok=True)
        
        # Determine file extension based on platform
        is_windows = state.system_context.get("platform", {}).get("system", "").lower() == "windows"
        ext = ".ps1" if is_windows else ".sh"
        
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{state.target_name}_{state.action}_template_{timestamp}{ext}"
        
        # Save the script
        script_path = script_dir / filename
        with open(script_path, "w") as f:
            f.write(script)
            
        logger.info(f"Script saved to: {script_path}")
        return script_path
