"""
Configuration components for workflow agent.
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from .configuration import (
    WorkflowConfiguration,
    ensure_workflow_config,
    merge_configs,
)
from .templates import (
    initialize_template_environment,
    load_templates,
    get_template,
    render_template,
    reload_templates,
)

def load_config_file(config_path: str) -> Dict[str, Any]:
    """Load configuration from a YAML file."""
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Error loading config file: {e}")

def find_default_config() -> Optional[str]:
    """Find the default configuration file."""
    default_paths = [
        "./config.yaml",
        "./config/config.yaml",
        os.path.expanduser("~/.workflow_agent/config.yaml"),
        "/etc/workflow_agent/config.yaml"
    ]
    for path in default_paths:
        if os.path.exists(path):
            return path
    return None

__all__ = [
    "WorkflowConfiguration",
    "ensure_workflow_config",
    "merge_configs",
    "load_config_file",
    "find_default_config",
    "initialize_template_environment",
    "load_templates",
    "get_template",
    "render_template",
    "reload_templates",
]