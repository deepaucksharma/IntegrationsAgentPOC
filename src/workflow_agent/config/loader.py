"""Configuration loader for workflow agent."""
import os
import json
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

# Default configuration paths to check
DEFAULT_CONFIG_PATHS = [
    "./workflow_config.yaml",
    "./workflow_config.yml",
    "./workflow_config.json",
    "~/.workflow_agent/config.yaml",
    "~/.workflow_agent/config.json",
]

def load_config_file(file_path: str) -> Dict[str, Any]:
    """Load configuration from a file."""
    path = Path(file_path).expanduser()
    
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")
    
    content = path.read_text()
    
    if file_path.endswith(('.yaml', '.yml')):
        try:
            return yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {e}")
    elif file_path.endswith('.json'):
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
    else:
        raise ValueError(f"Unsupported configuration file format: {file_path}")

def find_default_config() -> Optional[str]:
    """Find the first available default configuration file."""
    for path in DEFAULT_CONFIG_PATHS:
        expanded_path = Path(path).expanduser()
        if expanded_path.exists():
            return str(expanded_path)
    return None

def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two configuration dictionaries."""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    
    return result