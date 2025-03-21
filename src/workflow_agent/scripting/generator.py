import logging
import os
import json
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, PackageLoader
from pathlib import Path
from ..core.state import WorkflowState
from ..config.configuration import ensure_workflow_config

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, history_manager=None):
        self.history_manager = history_manager
        self.template_dirs = [
            Path(__file__).parent.parent / "integrations" / "common_templates",
            Path.cwd() / "src" / "workflow_agent" / "integrations" / "common_templates"
        ]
        self.env = self._create_environment()
    
    def _create_environment(self) -> Environment:
        """Create a Jinja2 environment with proper template loading configuration."""
        # Filter to only existing directories
        template_dirs = [str(d) for d in self.template_dirs if d.exists()]
        if not template_dirs:
            raise ValueError("No valid template directories found")
        
        # Set up Jinja2 environment with multiple template directories
        env = Environment(
            loader=ChoiceLoader([
                FileSystemLoader(d, followlinks=True) for d in template_dirs
            ]),
            trim_blocks=True,
            lstrip_blocks=True,
            enable_async=True
        )
        
        # Add necessary filters
        env.filters['to_json'] = lambda v: json.dumps(v)
        
        return env

    def _get_template_path(self, template_path: str) -> Path:
        """Get the absolute path of a template."""
        if not template_path:
            raise ValueError("No template path provided")
        
        template_full_path = Path(template_path)
        if not template_full_path.is_absolute():
            template_full_path = (Path(".") / template_path).resolve()
        
        # Add the template's parent directory to the search path if it's not already included
        template_parent = template_full_path.parent
        if template_parent not in self.template_dirs:
            self.template_dirs.append(template_parent)
            self.env = self._create_environment()
        
        return template_full_path

    async def generate_script(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            template_path = state.template_data.get("template_path")
            if not template_path:
                return {"error": "No template path provided by integration."}
            
            workflow_config = ensure_workflow_config(config or {})
            template_full_path = self._get_template_path(template_path)
            
            # Load and render the template
            template = self.env.get_template(template_full_path.name)
            script = await template.render_async(
                action=state.action,
                target_name=state.target_name,
                parameters=state.parameters,
                template_data=state.template_data or {},
                verification_data=state.template_data.get("verification", {}),
                system_context=state.system_context,
                version=state.template_data.get("version", "1.0.0"),
                is_windows=os.name == "nt"
            )
            return {"script": script}
        except Exception as e:
            logger.error(f"Error rendering script: {e}", exc_info=True)
            return {"error": str(e)}