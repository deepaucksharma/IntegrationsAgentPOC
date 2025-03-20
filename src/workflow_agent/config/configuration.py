"""
Configuration management for workflow agent with enhanced validation.
"""
import logging
import os
import yaml
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Set
from pydantic import BaseModel, Field, validator, root_validator
from ..error.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Patterns that might indicate dangerous operations
dangerous_patterns = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+~",
    r"chmod\s+-R\s+777",
    r"dd\s+if=/dev/urandom",
    r":\(\)\s*{\s*:\|:&\s*};:",  # Fork bomb pattern
    r"eval.*\$\(curl",
    r"wget.*\|\s*bash",
    r"curl.*\|\s*bash",
]

class WorkflowConfiguration(BaseModel):
    """Configuration for workflow agent with enhanced validation."""
    
    user_id: str = Field(default="test_user", description="User identifier")
    template_dir: Path = Field(default="./src/workflow_agent/integrations/common_templates", description="Main template directory")
    custom_template_dir: Optional[Path] = Field(default=None, description="Custom template directory")
    use_isolation: bool = Field(default=False, description="Whether to use isolation")
    isolation_method: str = Field(default="direct", description="Isolation method to use")
    execution_timeout: int = Field(default=300, description="Execution timeout in seconds", ge=1, le=3600)
    skip_verification: bool = Field(default=False, description="Skip verification steps")
    rule_based_optimization: bool = Field(default=True, description="Use rule-based optimization")
    use_static_analysis: bool = Field(default=True, description="Use static analysis")
    db_connection_string: str = Field(default="./workflow_history.db", description="Database connection string")
    prune_history_days: int = Field(default=90, description="Days to keep history", ge=1)
    plugin_dirs: List[Path] = Field(default_factory=lambda: [Path("./plugins")], description="Plugin directories")
    max_concurrent_tasks: int = Field(default=5, description="Maximum concurrent tasks", ge=1, le=100)
    least_privilege_execution: bool = Field(default=True, description="Use least privilege execution")
    log_level: str = Field(default="DEBUG", description="Logging level")
    docs_cache_dir: Optional[Path] = Field(default="./cache/docs", description="Documentation cache directory")
    docs_cache_ttl: int = Field(default=86400, description="Documentation cache TTL in seconds", ge=1)
    use_recovery: bool = Field(default=True, description="Use recovery")

    @validator("isolation_method")
    def validate_isolation_method(cls, value: str) -> str:
        """Validate isolation method."""
        valid_methods = {"docker", "chroot", "venv", "direct", "none"}
        if value.lower() not in valid_methods:
            raise ValueError(f"Invalid isolation method '{value}'. Must be one of: {valid_methods}")
        return value.lower()

    @validator("log_level")
    def validate_log_level(cls, value: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        value_upper = value.upper()
        if value_upper not in valid_levels:
            raise ValueError(f"Invalid log level '{value}'. Must be one of: {valid_levels}")
        return value_upper

    @validator("template_dir", "custom_template_dir", "docs_cache_dir")
    def convert_single_path(cls, value: Any) -> Optional[Path]:
        """Convert single path strings to Path objects."""
        if value is None:
            return None
        if isinstance(value, str):
            return Path(value).resolve()
        if isinstance(value, Path):
            return value.resolve()
        raise ValueError(f"Invalid path value: {value}")

    @validator("plugin_dirs", each_item=True)
    def convert_path_list(cls, value: Any) -> Path:
        """Convert path strings in lists to Path objects."""
        if isinstance(value, str):
            return Path(value).resolve()
        if isinstance(value, Path):
            return value.resolve()
        raise ValueError(f"Invalid path value: {value}")

    @root_validator(pre=True)
    def resolve_workspace_paths(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve ${WORKSPACE_ROOT} in paths."""
        workspace_root = os.environ.get("WORKSPACE_ROOT", os.getcwd())
        
        processed = {}
        
        for key, value in values.items():
            if isinstance(value, str) and "${WORKSPACE_ROOT}" in value:
                processed[key] = value.replace("${WORKSPACE_ROOT}", workspace_root)
            elif isinstance(value, list):
                processed[key] = [
                    item.replace("${WORKSPACE_ROOT}", workspace_root) 
                    if isinstance(item, str) and "${WORKSPACE_ROOT}" in item
                    else item
                    for item in value
                ]
            else:
                processed[key] = value
                
        return processed
    
    class Config:
        """Pydantic configuration."""
        extra = "forbid"  # Disallow extra fields
        validate_assignment = True  # Validate when attributes are assigned
        arbitrary_types_allowed = True  # Allow arbitrary types (like Path)

def load_config_file(file_path: str) -> Dict[str, Any]:
    """
    Load configuration from a file (YAML or JSON).
    
    Args:
        file_path: Path to the configuration file
        
    Returns:
        Dictionary with configuration
        
    Raises:
        ConfigurationError: If the file is not found or cannot be parsed
    """
    path = Path(file_path).expanduser()
    
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {file_path}")
    
    try:
        content = path.read_text(encoding='utf-8')
        
        if file_path.endswith((".yaml", ".yml")):
            loaded_config = yaml.safe_load(content) or {}
        elif file_path.endswith(".json"):
            loaded_config = json.loads(content) or {}
        else:
            raise ConfigurationError(f"Unsupported config file format: {file_path}")
        
        logger.debug(f"Loaded configuration from {file_path}")
        return loaded_config
        
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML format in {file_path}: {str(e)}")
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON format in {file_path}: {str(e)}")
    except Exception as e:
        raise ConfigurationError(f"Error reading config file {file_path}: {str(e)}")

def find_default_config() -> Optional[Dict[str, Any]]:
    """
    Find and load the default configuration file from standard locations.
    
    Returns:
        Configuration dictionary or None if no config file found
    """
    search_paths = [
        Path.cwd() / "workflow_config.yaml",
        Path.cwd() / "workflow_config.yml",
        Path.cwd() / "workflow_config.json",
        Path.home() / ".workflow_agent" / "config.yaml",
        Path.home() / ".workflow_agent" / "config.json",
    ]
    
    for path in search_paths:
        try:
            if path.exists():
                return load_config_file(str(path))
        except Exception as e:
            logger.warning(f"Error loading config from {path}: {e}")
    
    logger.info("No configuration file found, using defaults")
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

def ensure_workflow_config(config_input: Any) -> WorkflowConfiguration:
    """
    Ensures a valid WorkflowConfiguration object from various input types.
    
    Args:
        config_input: Configuration input (dict, string path, or WorkflowConfiguration)
        
    Returns:
        Validated WorkflowConfiguration object
        
    Raises:
        ConfigurationError: If validation fails
    """
    try:
        # If it's already a WorkflowConfiguration, return it
        if isinstance(config_input, WorkflowConfiguration):
            return config_input
            
        # If it's a string, assume it's a path and load it
        if isinstance(config_input, str):
            config_dict = load_config_file(config_input)
        elif isinstance(config_input, dict):
            config_dict = config_input
        elif config_input is None:
            # Find default config or use empty dict
            config_dict = find_default_config() or {}
        else:
            raise ConfigurationError(f"Unsupported configuration input type: {type(config_input)}")
        
        # Handle nested 'configurable' key if present
        if isinstance(config_dict, dict) and "configurable" in config_dict:
            config_dict = config_dict["configurable"]
            
        # Create and validate configuration object
        return WorkflowConfiguration(**config_dict)
        
    except Exception as e:
        if isinstance(e, ConfigurationError):
            raise
        logger.error(f"Configuration validation failed: {e}")
        raise ConfigurationError(f"Invalid configuration: {str(e)}")

def validate_script_security(script_content: str) -> Dict[str, Any]:
    """
    Validate script content for potentially dangerous operations.
    
    Args:
        script_content: Script content to validate
        
    Returns:
        Dict with validation results (valid: bool, warnings: list)
    """
    warnings = []
    
    # Check for dangerous patterns
    for pattern in dangerous_patterns:
        if re.search(pattern, script_content, re.IGNORECASE):
            warnings.append(f"Potentially dangerous pattern detected: {pattern}")
    
    # Check for suspicious commands based on context
    suspicious_cmds = [
        "format",
        "mkfs",
        "fdisk",
        "wget.*sudo",
        "curl.*sudo",
        "shutdown",
        "reboot"
    ]
    
    for cmd in suspicious_cmds:
        if re.search(rf"\b{cmd}\b", script_content, re.IGNORECASE):
            warnings.append(f"Suspicious command detected: {cmd}")
    
    return {
        "valid": len(warnings) == 0,
        "warnings": warnings
    }