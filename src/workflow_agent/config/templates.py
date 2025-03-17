import logging
from pathlib import Path
from typing import Dict, Any
from .configuration import ensure_workflow_config

logger = logging.getLogger(__name__)

# Load templates from template directories
def load_templates() -> Dict[str, str]:
    """
    Load script templates from template directories.
    
    Checks both the default template directory and user-defined custom directory.
    
    Returns:
        Dictionary mapping template keys to template content
    """
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
    
    for template_dir in dirs_to_check:
        dir_path = Path(template_dir)
        if not dir_path.exists():
            continue
            
        for file_path in dir_path.glob("*.sh.j2"):
            try:
                key = file_path.stem.replace(".sh", "")
                with open(file_path, "r") as f:
                    templates[key] = f.read()
                logger.debug(f"Loaded template: {key} from {file_path}")
            except Exception as e:
                logger.error(f"Error loading template {file_path}: {e}")
    
    return templates

# Dynamic loading of script templates
script_templates: Dict[str, str] = load_templates()

# Function to reload templates (for runtime updates)
def reload_templates() -> None:
    """Reload script templates from template directories."""
    global script_templates
    script_templates = load_templates()
    logger.info("Templates reloaded")