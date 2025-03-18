"""
Configuration management for workflow agent.
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..error.exceptions import ConfigurationError
import yaml

logger = logging.getLogger(__name__)

VALID_ISOLATION_METHODS = {"docker", "chroot", "venv", "direct", "none"}

dangerous_patterns: List[str] = [
    r"rm\s+(-rf?\s+)?\/(?!\w)",
    r"mkfs",
    r"dd\s+if=.*\s+of=\/dev",
    r">\s*\/dev\/[hs]d[a-z]",
    r"chmod\s+777",
    r"wget.*\s+\|\s+bash",
    r"curl.*\s+\|\s+bash",
    r":(){:\|:&};:",
    r"rm\s+-rf\s+~",
    r">\s*\/etc\/passwd"
]

class WorkflowConfiguration:
    """Configuration for workflow agent."""
    
    def __init__(
        self,
        user_id: str = "default_user",
        template_dir: str = "templates",
        custom_template_dir: Optional[str] = None,
        use_isolation: bool = False,
        isolation_method: str = "direct",
        execution_timeout: int = 300,
        skip_verification: bool = False,
        rule_based_optimization: bool = True,
        use_static_analysis: bool = True,
        db_connection_string: str = "workflow_history.db",
        prune_history_days: int = 90,
        plugin_dirs: List[str] = None,
        max_concurrent_tasks: int = 5,
        least_privilege_execution: bool = True,
        log_level: str = "INFO"
    ):
        self.user_id = user_id
        self.template_dir = template_dir
        self.custom_template_dir = custom_template_dir
        self.use_isolation = use_isolation
        self.isolation_method = isolation_method
        self.execution_timeout = execution_timeout
        self.skip_verification = skip_verification
        self.rule_based_optimization = rule_based_optimization
        self.use_static_analysis = use_static_analysis
        self.db_connection_string = db_connection_string
        self.prune_history_days = prune_history_days
        self.plugin_dirs = plugin_dirs or ["plugins"]
        self.max_concurrent_tasks = max_concurrent_tasks
        self.least_privilege_execution = least_privilege_execution
        self.log_level = log_level

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

def load_config_file(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from a file."""
    if not config_path:
        return {}
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            if not config:
                return {}
            return config.get("configurable", {})
    except Exception as e:
        logger.error(f"Error loading configuration file: {e}")
        return {}

def find_default_config() -> Dict[str, Any]:
    """Find and load the default configuration file."""
    default_paths = [
        "workflow_config.yaml",
        "config/workflow_config.yaml",
        os.path.join(os.path.dirname(__file__), "workflow_config.yaml"),
    ]
    
    for path in default_paths:
        if os.path.exists(path):
            return load_config_file(path)
    
    logger.warning("No configuration file found, using defaults")
    return {}

def ensure_workflow_config(config: Optional[Dict[str, Any]] = None) -> WorkflowConfiguration:
    """Ensures the configuration is valid and complete."""
    if config is None:
        config = {}
    
    # If config is a string, assume it's a path and load it
    if isinstance(config, str):
        config = load_config_file(config)
    
    # Resolve workspace paths
    config = resolve_workspace_paths(config)
    
    try:
        return WorkflowConfiguration(**config)
    except Exception as e:
        raise ConfigurationError(f"Invalid configuration: {e}")

def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two configurations, with override_config taking precedence."""
    merged = base_config.copy()
    for key, value in override_config.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    return merged

def initialize_template_environment(template_dirs: List[str]) -> None:
    """Initialize the template environment."""
    # This is a placeholder for template initialization
    pass

def load_templates() -> None:
    """Load templates from the template directory."""
    # This is a placeholder for template loading
    pass