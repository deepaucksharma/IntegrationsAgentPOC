"""
Configuration loader for workflow agent.
"""
import os
import json
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

DEFAULT_CONFIG_PATHS = [
    "./workflow_config.yaml",
    "./workflow_config.yml",
    "./workflow_config.json",
    "~/.workflow_agent/config.yaml",
    "~/.workflow_agent/config.json",
]

def load_config_file(file_path: str) -> Dict[str, Any]:
    """Load configuration from a file (YAML or JSON)."""
    path = Path(file_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")
    
    try:
        content = path.read_text()
        if file_path.endswith((".yaml", ".yml")):
            return yaml.safe_load(content) or {}
        elif file_path.endswith(".json"):
            return json.loads(content) or {}
        else:
            raise ValueError(f"Unsupported config file format: {file_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format in {file_path}: {str(e)}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in {file_path}: {str(e)}")
    except Exception as e:
        raise Exception(f"Error reading config file {file_path}: {str(e)}")

def find_default_config() -> Optional[str]:
    """Find the first available default configuration file."""
    for path in DEFAULT_CONFIG_PATHS:
        expanded = Path(path).expanduser()
        if expanded.exists():
            return str(expanded)
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