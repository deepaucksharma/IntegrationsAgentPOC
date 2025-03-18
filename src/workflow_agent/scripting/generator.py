import logging
import os
import json
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, ChoiceLoader
from pathlib import Path
from ..core.state import WorkflowState
from ..config.configuration import ensure_workflow_config

logger = logging.getLogger(__name__)

class ScriptGenerator:
    def __init__(self, history_manager=None):
        self.history_manager = history_manager

    async def generate_script(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not state.template_path:
            return {"error": "No template path provided by integration."}
        
        workflow_config = ensure_workflow_config(config or {})
        template_full_path = Path(state.template_path)
        if not template_full_path.is_absolute():
            template_full_path = (Path(".") / state.template_path).resolve()
        
        # Define all possible template directories
        template_dirs = [
            Path(__file__).parent.parent / "integrations" / "common_templates",
            Path.cwd() / "src" / "workflow_agent" / "integrations" / "common_templates",
            template_full_path.parent
        ]
        
        # Filter to only existing directories
        template_dirs = [str(d) for d in template_dirs if d.exists()]
        if not template_dirs:
            return {"error": "No valid template directories found"}
        
        try:
            # Set up Jinja2 environment with multiple template directories
            env = Environment(
                loader=ChoiceLoader([FileSystemLoader(d) for d in template_dirs]),
                trim_blocks=True,
                lstrip_blocks=True
            )
            
            # Add necessary filters
            env.filters['to_json'] = lambda v: json.dumps(v)
            
            # Load and render the template
            template = env.get_template(template_full_path.name)
            script = template.render(
                action=state.action,
                target_name=state.target_name,
                parameters=state.parameters,
                template_data=state.template_data or {},
                verification_data=state.verification_data or {}
            )
            return {"script": script}
        except Exception as e:
            logger.error(f"Error rendering script: {e}")
            return {"error": str(e)}