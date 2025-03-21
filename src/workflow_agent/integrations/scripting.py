"""Scripting support for integrations."""
from typing import Dict, Any, Optional
import os
import jinja2

class ScriptGenerator:
    """Generates scripts from templates."""
    
    def __init__(self, template_dir: str):
        self.template_dir = template_dir
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=True
        )
        
    def generate(self, template_name: str, data: Dict[str, Any]) -> str:
        """Generate a script from a template."""
        try:
            template = self.env.get_template(template_name)
            return template.render(**data)
        except Exception as e:
            raise ValueError(f"Script generation failed: {str(e)}")
            
    def list_templates(self) -> list:
        """List available templates."""
        return self.env.list_templates()
        
    def validate_template(self, template_name: str) -> bool:
        """Validate a template exists."""
        return template_name in self.list_templates() 