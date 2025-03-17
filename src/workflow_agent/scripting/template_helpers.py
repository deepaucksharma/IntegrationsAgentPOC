import os
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

def compose_template(
    base_template: str,
    fragments: Dict[str, str],
    template_dirs: List[str]
) -> str:
    """
    Compose a template from a base template and fragments.
    
    Args:
        base_template: Base template content
        fragments: Dict of fragment names to include
        template_dirs: List of template directories
    
    Returns:
        Composed template string
    """
    # Create a Jinja2 environment for fragments
    env = create_fragment_environment(template_dirs)
    
    # Load and preprocess fragments
    processed_fragments = {}
    
    for key, fragment_name in fragments.items():
        fragment_content = load_template_fragment(fragment_name, template_dirs)
        if fragment_content:
            processed_fragments[key] = fragment_content
    
    # Prepare special rendering context with fragments
    context = {
        "fragments": processed_fragments
    }
    
    # Render base template with fragments
    template = Template(base_template, env)
    return template.render(**context) 