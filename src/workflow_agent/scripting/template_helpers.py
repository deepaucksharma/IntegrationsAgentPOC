import os
import re
import shlex
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template

logger = logging.getLogger(__name__)

# Template fragment directory
FRAGMENT_DIR = "fragments"

def get_fragment_path(base_dir: str) -> Path:
    """Get path to template fragments directory."""
    return Path(base_dir) / FRAGMENT_DIR

def load_template_fragment(fragment_name: str, template_dirs: List[str]) -> Optional[str]:
    """
    Load a template fragment from the fragments directory.
    
    Args:
        fragment_name: Name of the fragment to load
        template_dirs: List of template directories to search
    
    Returns:
        Template fragment content or None if not found
    """
    for template_dir in template_dirs:
        fragment_dir = get_fragment_path(template_dir)
        fragment_path = fragment_dir / f"{fragment_name}.j2"
        
        if fragment_path.exists():
            try:
                with open(fragment_path, "r") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error loading template fragment {fragment_name}: {e}")
    
    return None

def create_fragment_environment(template_dirs: List[str]) -> Environment:
    """
    Create a Jinja2 environment for fragments.
    
    Args:
        template_dirs: List of template directories
    
    Returns:
        Jinja2 Environment
    """
    # Collect fragment directories
    fragment_dirs = []
    for template_dir in template_dirs:
        fragment_dir = get_fragment_path(template_dir)
        if fragment_dir.exists():
            fragment_dirs.append(str(fragment_dir))
    
    # Create environment with fragment loader
    env = Environment(
        loader=FileSystemLoader(fragment_dirs),
        trim_blocks=True,
        lstrip_blocks=True
    )
    
    return env

def sanitize_input(value: Any) -> str:
    """
    Sanitize input for shell scripts.
    
    Args:
        value: Value to sanitize
        
    Returns:
        Sanitized string
    """
    if value is None:
        return ""
    
    # Convert to string and escape shell special characters
    return shlex.quote(str(value))

def compose_template(
    base_template: str,
    fragments: Dict[str, str],
    context: Dict[str, Any]
) -> str:
    """
    Compose a template from base template and fragments.
    
    Args:
        base_template: Base template string
        fragments: Dictionary of fragment names to templates
        context: Rendering context
        
    Returns:
        Composed template string
    """
    # Create environment with fragment loader
    env = Environment()
    
    # Add custom filters
    env.filters['quote'] = sanitize_input
    
    # Add fragments as templates
    fragment_templates = {}
    for name, content in fragments.items():
        fragment_templates[name] = env.from_string(content)
    
    # Create template function to render fragments
    def render_fragment(name: str, **kwargs):
        if name not in fragment_templates:
            return f"<!-- Fragment {name} not found -->"
        
        # Merge context with kwargs
        merged_context = {**context, **kwargs}
        return fragment_templates[name].render(**merged_context)
    
    # Add render_fragment to context
    context['render_fragment'] = render_fragment
    
    # Create and render the base template
    template = env.from_string(base_template)
    return template.render(**context)

def extract_placeholder_variables(template_str: str) -> List[str]:
    """
    Extract variables from a template string.
    
    Args:
        template_str: Template string to analyze
        
    Returns:
        List of variable names
    """
    # Find all Jinja2 variables ({{ variable }})
    pattern = r'{{\s*([a-zA-Z0-9_\.]+)\s*}}'
    matches = re.findall(pattern, template_str)
    
    # Find all Jinja2 conditionals and loops ({% if variable %}, {% for x in variable %})
    pattern2 = r'{%\s*(?:if|for\s+\w+\s+in)\s+([a-zA-Z0-9_\.]+)\s*%}'
    matches2 = re.findall(pattern2, template_str)
    
    # Combine and filter out duplicates
    variables = list(set(matches + matches2))
    
    # Handle dotted notation (parameters.host -> parameters)
    root_vars = set()
    for var in variables:
        if '.' in var:
            root_vars.add(var.split('.')[0])
        else:
            root_vars.add(var)
    
    return sorted(list(root_vars))

def validate_template_variables(template_str: str, context: Dict[str, Any]) -> List[str]:
    """
    Validate that all required variables are in the context.
    
    Args:
        template_str: Template string to validate
        context: Context dictionary
        
    Returns:
        List of missing variables
    """
    variables = extract_placeholder_variables(template_str)
    missing = []
    
    for var in variables:
        if var not in context:
            missing.append(var)
    
    return missing 