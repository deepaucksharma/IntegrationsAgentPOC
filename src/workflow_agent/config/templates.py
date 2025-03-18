"""Template management for workflow agent."""
import logging
import os
import json
from pathlib import Path
from typing import Dict, Any, Set, Optional, List
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
from .configuration import ensure_workflow_config

logger = logging.getLogger(__name__)

# Global template environment
template_env: Optional[Environment] = None
# Global template cache
script_templates: Dict[str, str] = {}
# Integration categories
INTEGRATION_CATEGORIES = [
    "infra_agent",
    "database",
    "monitoring",
    "security",
    "network",
    "storage",
    "container",
    "cloud",
    "custom"
]

def initialize_template_environment(template_dirs: List[str]) -> Environment:
    """Initialize Jinja2 environment with template directories."""
    global template_env
    
    # Filter to only existing directories
    existing_dirs = [d for d in template_dirs if os.path.exists(d)]
    if not existing_dirs:
        logger.warning("No valid template directories found")
        existing_dirs = ["."]
    
    # Create Jinja2 environment with directory loader and inheritance support
    template_env = Environment(
        loader=FileSystemLoader(existing_dirs),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True
    )
    
    # Add custom filters
    template_env.filters['to_json'] = lambda v: json.dumps(v)
    
    logger.info(f"Initialized template environment with directories: {existing_dirs}")
    return template_env

def get_template_paths(base_dir: str) -> Dict[str, List[Path]]:
    """
    Get all template paths organized by category.
    
    Args:
        base_dir: Base template directory
    
    Returns:
        Dict of category -> list of template paths
    """
    result = {category: [] for category in INTEGRATION_CATEGORIES}
    result["uncategorized"] = []
    
    base_path = Path(base_dir)
    if not base_path.exists():
        return result
    
    # Process templates in the root templates directory (uncategorized)
    for file_path in base_path.glob("*.sh"):
        result["uncategorized"].append(file_path)
    
    # Process templates in category subdirectories
    for category in INTEGRATION_CATEGORIES:
        category_dir = base_path / category
        if category_dir.exists() and category_dir.is_dir():
            for file_path in category_dir.glob("**/*.sh"):
                result[category].append(file_path)
    
    return result

def load_templates(refresh: bool = False) -> Dict[str, str]:
    """
    Load script templates from template directories.
    
    Args:
        refresh: Whether to force reload templates
        
    Returns:
        Dictionary of template key to content
    """
    global script_templates, template_env
    
    if script_templates and not refresh:
        return script_templates
    
    script_templates = {}
    
    # Get template directories from configuration
    template_dirs = ["templates"]  # Default directory
    custom_dirs = ["custom_templates"]  # Custom templates directory
    
    # Create Jinja2 environment
    search_paths = []
    for base_dir in template_dirs + custom_dirs:
        if os.path.exists(base_dir):
            search_paths.append(base_dir)
    
    if search_paths:
        template_env = Environment(
            loader=FileSystemLoader(search_paths),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    # Load templates from each directory
    for base_dir in template_dirs + custom_dirs:
        if not os.path.exists(base_dir):
            continue
        
        for root, _, files in os.walk(base_dir):
            for file in files:
                if file.endswith(('.sh', '.bash', '.yaml', '.yml')):
                    # Get relative path for template key
                    rel_path = os.path.relpath(root, base_dir)
                    if rel_path == ".":
                        key = file
                    else:
                        key = f"{rel_path}/{file}"
                    
                    # Load template content
                    try:
                        with open(os.path.join(root, file), 'r') as f:
                            script_templates[key] = f.read()
                    except Exception as e:
                        logger.error(f"Error loading template {key}: {e}")
    
    logger.info(f"Loaded {len(script_templates)} templates")
    return script_templates

def get_template(key: str) -> Optional[str]:
    """
    Get a template by key, loading if necessary.
    
    Args:
        key: Template key
    
    Returns:
        Template string or None if not found
    """
    if not script_templates:
        load_templates()
    
    # Try direct key lookup
    if key in script_templates:
        return script_templates[key]
    
    # Try with category prefixes if key doesn't contain category
    if '/' not in key:
        for category in INTEGRATION_CATEGORIES:
            category_key = f"{category}/{key}"
            if category_key in script_templates:
                return script_templates[category_key]
    
    # Try default template for the action
    if '-' in key:
        action = key.split('-')[-1]
        default_key = f"default-{action}"
        if default_key in script_templates:
            return script_templates[default_key]
    
    return None

def render_template(template_key: str, context: Dict[str, Any]) -> Optional[str]:
    """
    Render a template with the given context.
    
    Args:
        template_key: Key of the template to render
        context: Dictionary of context variables
    
    Returns:
        Rendered template string or None if template not found
    """
    template_str = get_template(template_key)
    if not template_str:
        return None
    
    try:
        # Use Jinja2 environment if available, otherwise create a Template directly
        if template_env:
            # Create a template object from the string
            template = Template(template_str, environment=template_env)
        else:
            template = Template(template_str)
        
        # Render the template with the context
        return template.render(**context)
    except Exception as e:
        logger.error(f"Error rendering template {template_key}: {e}")
        return None

def reload_templates() -> None:
    """Reload script templates from template directories."""
    global script_templates
    script_templates = load_templates(refresh=True)
    logger.info("Templates reloaded")

def get_available_templates(category: Optional[str] = None) -> List[str]:
    """
    Get list of available templates, optionally filtered by category.
    
    Args:
        category: Optional category to filter by
    
    Returns:
        List of template keys
    """
    if not script_templates:
        load_templates()
    
    if not category:
        return list(script_templates.keys())
    
    return [k for k in script_templates.keys() if k.startswith(f"{category}/")]

def get_template_categories() -> List[str]:
    """
    Get list of template categories in use.
    
    Returns:
        List of categories
    """
    if not script_templates:
        load_templates()
    
    categories = set()
    for key in script_templates.keys():
        if '/' in key:
            categories.add(key.split('/')[0])
    
    return list(categories)