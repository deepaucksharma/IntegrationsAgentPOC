"""
Centralized configuration loading module for the workflow agent.
This module provides a unified way to load configuration from files and environment
variables for use by both the framework and example scripts.
"""
import os
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union, List

from .configuration import (
    WorkflowConfiguration, 
    load_configuration_from_file, 
    load_configuration_from_env,
    merge_configs,
    ensure_workflow_config
)

logger = logging.getLogger(__name__)

def load_config(
    config_path: Optional[str] = None,
    env_prefix: str = "WORKFLOW_",
    defaults: Optional[Dict[str, Any]] = None,
    search_paths: Optional[List[str]] = None
) -> WorkflowConfiguration:
    """
    Centralized configuration loading from files and environment.
    
    Args:
        config_path: Path to the configuration file (optional)
        env_prefix: Prefix for environment variables to consider
        defaults: Default configuration values
        search_paths: Additional paths to search for config files
        
    Returns:
        WorkflowConfiguration object with loaded configuration
    """
    # Start with default configuration
    config = defaults or {}
    
    # Default search paths
    if search_paths is None:
        search_paths = [
            os.getcwd(),  # Current directory
            str(Path(os.getcwd()) / "config"),  # ./config directory
            str(Path(__file__).parent.parent.parent.parent)  # Project root
        ]
    
    # Try to load configuration from specified file
    if config_path and os.path.exists(config_path):
        logger.info(f"Loading configuration from specified file: {config_path}")
        file_config = load_configuration_from_file(config_path)
        config = merge_configs(config, file_config)
    else:
        # Try to find config file in search paths
        for path in search_paths:
            for filename in ["workflow_config.yaml", "workflow_config.yml", "config.yaml", "config.yml"]:
                full_path = os.path.join(path, filename)
                if os.path.exists(full_path):
                    logger.info(f"Loading configuration from discovered file: {full_path}")
                    file_config = load_configuration_from_file(full_path)
                    config = merge_configs(config, file_config)
                    break
            else:
                continue
            break
        else:
            logger.info("No configuration file found, using defaults and environment variables")
    
    # Load configuration from environment variables
    env_config = load_configuration_from_env()
    
    # Merge environment configuration (taking precedence)
    config = merge_configs(config, env_config)
    
    # Convert to WorkflowConfiguration object
    return ensure_workflow_config(config)

def create_example_config(
    license_key: Optional[str] = None,
    integration_type: str = "infra_agent",
    target_name: str = "infrastructure-agent",
    is_windows: Optional[bool] = None,
    **additional_params
) -> Dict[str, Any]:
    """
    Create a standard configuration for example scripts.
    
    Args:
        license_key: New Relic license key
        integration_type: Integration type
        target_name: Target name
        is_windows: Whether running on Windows (auto-detected if None)
        additional_params: Additional configuration parameters
        
    Returns:
        Configuration dictionary
    """
    # Auto-detect Windows if not specified
    if is_windows is None:
        import platform
        is_windows = platform.system() == "Windows"
    
    # Get license key from environment if not provided
    if not license_key:
        license_key = os.environ.get("NEW_RELIC_LICENSE_KEY", "YOUR_LICENSE_KEY")
    
    # Create basic configuration
    config = {
        "license_key": license_key,
        "integration_type": integration_type,
        "target_name": target_name,
        "system_context": {
            "is_windows": is_windows,
            "platform": {
                "system": "Windows" if is_windows else "Linux",
            }
        },
        "parameters": {
            "license_key": license_key,
            "host": "localhost",
            "port": "8080",
            "install_dir": r"C:\Program Files\New Relic" if is_windows else "/opt/newrelic",
            "config_path": r"C:\ProgramData\New Relic" if is_windows else "/etc/newrelic",
            "log_path": r"C:\ProgramData\New Relic\logs" if is_windows else "/var/log/newrelic"
        },
        "action": additional_params.get("action", "install")
    }
    
    # Merge additional parameters
    if additional_params:
        # Handle nested dictionaries properly
        for key, value in additional_params.items():
            if key in config and isinstance(config[key], dict) and isinstance(value, dict):
                config[key].update(value)
            else:
                config[key] = value
    
    return config

def load_example_config(**kwargs) -> Dict[str, Any]:
    """
    Load configuration for example scripts.
    Combines environment variables, configuration files, and provided parameters.
    
    Args:
        **kwargs: Configuration parameters to override
        
    Returns:
        Configuration dictionary
    """
    # Create base example configuration
    example_config = create_example_config(**kwargs)
    
    # Load configuration from files and environment
    config = load_config(defaults=example_config)
    
    # Make sure the "parameters" key is present for older scripts
    result = config.model_dump()
    if "parameters" not in result and hasattr(config, "parameters"):
        result["parameters"] = config.parameters
    
    # Make sure example_config parameters are included
    if "parameters" not in result and "parameters" in example_config:
        result["parameters"] = example_config["parameters"]
    
    return result
