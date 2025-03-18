"""
Configuration management for workflow agent.
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator
from ..error.exceptions import ConfigurationError
import yaml

logger = logging.getLogger(__name__)

class WorkflowConfiguration(BaseModel):
    """Configuration for workflow agent with validation."""
    
    user_id: str = Field(default="default_user", description="User identifier")
    template_dir: Path = Field(default=Path("templates"), description="Main template directory")
    custom_template_dir: Optional[Path] = Field(default=None, description="Custom template directory")
    use_isolation: bool = Field(default=False, description="Whether to use isolation")
    isolation_method: str = Field(default="direct", description="Isolation method to use")
    execution_timeout: int = Field(default=300, description="Execution timeout in seconds")
    skip_verification: bool = Field(default=False, description="Skip verification steps")
    rule_based_optimization: bool = Field(default=True, description="Use rule-based optimization")
    use_static_analysis: bool = Field(default=True, description="Use static analysis")
    db_connection_string: str = Field(default="workflow_history.db", description="Database connection string")
    prune_history_days: int = Field(default=90, description="Days to keep history")
    plugin_dirs: List[Path] = Field(default_factory=lambda: [Path("plugins")], description="Plugin directories")
    max_concurrent_tasks: int = Field(default=5, description="Maximum concurrent tasks")
    least_privilege_execution: bool = Field(default=True, description="Use least privilege execution")
    log_level: str = Field(default="INFO", description="Logging level")

    @validator("isolation_method")
    def validate_isolation_method(cls, v):
        valid_methods = {"docker", "chroot", "venv", "direct", "none"}
        if v not in valid_methods:
            raise ValueError(f"Invalid isolation method. Must be one of: {valid_methods}")
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
        return v

    @validator("template_dir", "custom_template_dir", "plugin_dirs", each_item=True)
    def validate_paths(cls, v):
        if v is not None:
            return Path(v).resolve()
        return v

    class Config:
        arbitrary_types_allowed = True

def load_config(config_path: Optional[Union[str, Path]] = None) -> WorkflowConfiguration:
    """Load configuration from file or use defaults."""
    try:
        if config_path:
            path = Path(config_path).resolve()
            if not path.exists():
                logger.warning(f"Configuration file not found at {path}, using defaults")
                return WorkflowConfiguration()
            
            with open(path, 'r') as f:
                config_dict = yaml.safe_load(f) or {}
            
            # Handle nested 'configurable' structure
            if "configurable" in config_dict:
                config_dict = config_dict["configurable"]
            
            return WorkflowConfiguration(**config_dict)
        return WorkflowConfiguration()
    
    except Exception as e:
        raise ConfigurationError(f"Failed to load configuration: {str(e)}")

def find_config_file() -> Optional[Path]:
    """Find configuration file in standard locations."""
    search_paths = [
        Path.cwd() / "workflow_config.yaml",
        Path.cwd() / "config" / "workflow_config.yaml",
        Path.home() / ".workflow_agent" / "config.yaml"
    ]
    
    for path in search_paths:
        if path.exists():
            return path
    return None

def ensure_workflow_config(config: Optional[Dict[str, Any]] = None) -> WorkflowConfiguration:
    """Ensures the configuration is valid and complete."""
    if config is None:
        config = {}
    
    # If we're getting a dict with a 'configurable' key, extract that
    if isinstance(config, dict) and "configurable" in config:
        config = config["configurable"]
    
    # If it's already a WorkflowConfiguration, return it directly
    if isinstance(config, WorkflowConfiguration):
        return config
        
    # If config is a string, assume it's a path and load it
    if isinstance(config, str):
        config = load_config(config)
    
    # Resolve workspace paths
    config = resolve_workspace_paths(config)
    
    try:
        return WorkflowConfiguration(**config)
    except Exception as e:
        raise ConfigurationError(f"Invalid configuration: {e}")

def resolve_workspace_paths(config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve ${WORKSPACE_ROOT} in paths to absolute paths."""
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    def resolve_path(value: str) -> str:
        if isinstance(value, str) and "${WORKSPACE_ROOT}" in value:
            return value.replace("${WORKSPACE_ROOT}", workspace_root)
        return value
    
    resolved_config = {}
    for key, value in config.items():
        if isinstance(value, dict):
            resolved_config[key] = resolve_workspace_paths(value)
        elif isinstance(value, list):
            resolved_config[key] = [resolve_path(item) for item in value]
        else:
            resolved_config[key] = resolve_path(value)
    
    return resolved_config

def load_templates() -> None:
    """Load templates from the template directory."""
    # This is a placeholder for template loading
    pass