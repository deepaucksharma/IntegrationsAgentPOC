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
    """
    Load configuration from a file.
    
    Args:
        file_path: Path to configuration file
        
    Returns:
        Dictionary containing configuration data
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file format is not supported or content is invalid
    """
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
    """
    Find the first available default configuration file.
    
    Returns:
        Path to the first found configuration file, or None if none found
    """
    for path in DEFAULT_CONFIG_PATHS:
        expanded_path = Path(path).expanduser()
        if expanded_path.exists():
            return str(expanded_path)
    return None

def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two configuration dictionaries.
    
    Args:
        base: Base configuration
        override: Configuration to override base values
        
    Returns:
        Merged configuration dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    
    return result

def get_env_config_prefix() -> str:
    """
    Get the environment variable prefix for configuration.
    
    Returns:
        Prefix string for environment variables
    """
    return os.environ.get("WORKFLOW_CONFIG_PREFIX", "WORKFLOW_")

def load_env_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables.
    
    Environment variables should be prefixed with WORKFLOW_
    (or the value of WORKFLOW_CONFIG_PREFIX environment variable).
    
    Returns:
        Dictionary with configuration from environment variables
    """
    prefix = get_env_config_prefix()
    config = {}
    
    for key, value in os.environ.items():
        if key.startswith(prefix):
            config_key = key[len(prefix):].lower()
            
            # Handle nested keys with double underscore
            if "__" in config_key:
                parts = config_key.split("__")
                temp = config
                for i, part in enumerate(parts[:-1]):
                    if part not in temp:
                        temp[part] = {}
                    temp = temp[part]
                temp[parts[-1]] = value
            else:
                config[config_key] = value
    
    return config