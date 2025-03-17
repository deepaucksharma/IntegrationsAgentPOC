import logging
import os
import json
from pathlib import Path
from typing import Dict, Any, Set, Optional, List
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
from .configuration import ensure_workflow_config

logger = logging.getLogger(__name__)

# Global template environment
template_env = None
# Global template cache
script_templates: Dict[str, str] = {}
# Integration categories
INTEGRATION_CATEGORIES = [
    "aws", "azure", "gcp", "database", "webserver", "monitoring", 
    "container", "network", "security", "custom"
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
    for file_path in base_path.glob("*.j2"):
        result["uncategorized"].append(file_path)
    
    # Process templates in category subdirectories
    for category in INTEGRATION_CATEGORIES:
        category_dir = base_path / category
        if category_dir.exists() and category_dir.is_dir():
            for file_path in category_dir.glob("**/*.j2"):
                result[category].append(file_path)
    
    return result

def load_templates(refresh: bool = False) -> Dict[str, str]:
    """
    Load script templates from template directories.
    
    Checks both the default template directory and user-defined custom directory.
    Organizes templates by category.
    
    Args:
        refresh: Whether to force a refresh of all templates
    
    Returns:
        Dictionary mapping template keys to template content
    """
    global script_templates
    
    # Skip if templates are already loaded and refresh is not requested
    if script_templates and not refresh:
        return script_templates
    
    templates = {}
    
    # Default templates (these are hardcoded fallbacks)
    templates.update({
        "default-install": """#!/usr/bin/env bash
set -e
echo "Installing {{ target_name }} with action {{ action }}"
# Add your installation commands here.
""",
        "default-rollback": """#!/usr/bin/env bash
set -e
echo "Rolling back {{ target_name }} changes"
# Add your rollback commands here.
"""
    })
    
    # Load from template directories
    config = ensure_workflow_config()
    dirs_to_check = [config.template_dir]
    
    if config.custom_template_dir:
        dirs_to_check.append(config.custom_template_dir)
    
    # Initialize Jinja2 environment
    if not template_env:
        initialize_template_environment(dirs_to_check)
    
    # Load templates from each directory
    for template_dir in dirs_to_check:
        if not os.path.exists(template_dir):
            continue
        
        # Get templates by category
        template_paths = get_template_paths(template_dir)
        
        # Process templates in each category
        for category, paths in template_paths.items():
            for file_path in paths:
                try:
                    # Determine template key based on path
                    # For categorized templates: category/target-action
                    # For uncategorized: target-action
                    rel_path = file_path.relative_to(Path(template_dir))
                    template_name = str(rel_path).replace('.j2', '')
                    
                    # For root templates, get the key directly
                    if category == "uncategorized":
                        key = file_path.stem.replace(".sh", "")
                    else:
                        # For categorized templates, include category in key
                        key = f"{category}/{file_path.stem.replace('.sh', '')}"
                    
                    with open(file_path, "r") as f:
                        templates[key] = f.read()
                        
                    logger.debug(f"Loaded template: {key} from {file_path}")
                except Exception as e:
                    logger.error(f"Error loading template {file_path}: {e}")
    
    script_templates = templates
    logger.info(f"Loaded {len(templates)} templates")
    return templates

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