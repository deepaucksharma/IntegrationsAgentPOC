"""Template management for script generation."""
import logging
import os
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
from .configuration import ensure_workflow_config

logger = logging.getLogger(__name__)

# Global template environment
template_env = None
# Global template cache
script_templates: Dict[str, str] = {}

def initialize_template_environment(template_dirs: List[str]) -> Environment:
    """Initialize Jinja2 environment with template directories."""
    global template_env
    
    existing_dirs = [d for d in template_dirs if os.path.exists(d)]
    if not existing_dirs:
        existing_dirs = ["."]
    
    template_env = Environment(
        loader=FileSystemLoader(existing_dirs),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True
    )
    
    # Add custom filters
    template_env.filters['to_json'] = lambda v: json.dumps(v)
    
    return template_env

def load_templates(refresh: bool = False) -> Dict[str, str]:
    """Load script templates from template directories."""
    global script_templates
    
    if script_templates and not refresh:
        return script_templates
    
    templates = {
        "default-install": """#!/usr/bin/env bash
set -e
echo "Installing {{ target_name }} with action {{ action }}"
# Add your installation commands here.
""",
        "default-remove": """#!/usr/bin/env bash
set -e
echo "Removing {{ target_name }}"
# Add your removal commands here.
""",
        "default-rollback": """#!/usr/bin/env bash
set -e
echo "Rolling back {{ target_name }} changes"
# Add your rollback commands here.
"""
    }
    
    config = ensure_workflow_config()
    dirs_to_check = [config.template_dir]
    if config.custom_template_dir:
        dirs_to_check.append(config.custom_template_dir)
    
    if not template_env:
        initialize_template_environment(dirs_to_check)
    
    for template_dir in dirs_to_check:
        if not os.path.exists(template_dir):
            continue
        
        template_dir_path = Path(template_dir)
        for file_path in template_dir_path.glob("**/*.j2"):
            try:
                key = file_path.stem.replace(".sh", "")
                with open(file_path, "r") as f:
                    templates[key] = f.read()
            except Exception as e:
                logger.error(f"Error loading template {file_path}: {e}")
    
    script_templates = templates
    return templates

def get_template(key: str) -> Optional[str]:
    """Get a template by key, loading if necessary."""
    if not script_templates:
        load_templates()
    
    if key in script_templates:
        return script_templates[key]
    
    if '-' in key:
        action = key.split('-')[-1]
        default_key = f"default-{action}"
        if default_key in script_templates:
            return script_templates[default_key]
    
    return None

def render_template(template_key: str, context: Dict[str, Any]) -> Optional[str]:
    """Render a template with the given context."""
    template_str = get_template(template_key)
    if not template_str:
        return None
    
    try:
        template = Template(template_str)
        return template.render(**context)
    except Exception as e:
        logger.error(f"Error rendering template {template_key}: {e}")
        return None

def reload_templates() -> None:
    """Reload script templates from template directories."""
    global script_templates
    script_templates = load_templates(refresh=True)