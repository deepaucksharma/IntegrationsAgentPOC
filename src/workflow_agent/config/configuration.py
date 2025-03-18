"""
Configuration management for workflow agent.
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..error.exceptions import ConfigurationError

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
    """Container for agent-level configuration."""
    def __init__(
        self,
        user_id: str = "cli-user",
        template_dir: Optional[str] = None,
        custom_template_dir: Optional[str] = None,
        use_isolation: bool = True,
        isolation_method: str = "docker",
        execution_timeout: int = 30000,
        skip_verification: bool = False,
        rule_based_optimization: bool = False,
        use_static_analysis: bool = False,
        db_connection_string: Optional[str] = None,
        prune_history_days: Optional[int] = None,
        plugin_dirs: List[str] = None,
        max_concurrent_tasks: int = 5,
        least_privilege_execution: bool = True,
        log_level: str = "INFO"
    ):
        if isolation_method not in VALID_ISOLATION_METHODS:
            raise ValueError(f"Invalid isolation method: {isolation_method}")
        
        self.user_id = user_id
        
        # Use absolute path for template_dir
        if template_dir is None:
            self.template_dir = str(Path(__file__).resolve().parent.parent / "integrations" / "common_templates")
        else:
            self.template_dir = os.path.abspath(template_dir)
            
        self.custom_template_dir = custom_template_dir
        if custom_template_dir:
            self.custom_template_dir = os.path.abspath(custom_template_dir)
            
        self.use_isolation = use_isolation
        self.isolation_method = isolation_method
        self.execution_timeout = execution_timeout
        self.skip_verification = skip_verification
        self.rule_based_optimization = rule_based_optimization
        self.use_static_analysis = use_static_analysis
        self.db_connection_string = db_connection_string
        self.prune_history_days = prune_history_days
        self.plugin_dirs = plugin_dirs or ["./plugins"]
        self.max_concurrent_tasks = max_concurrent_tasks
        self.least_privilege_execution = least_privilege_execution
        self.log_level = log_level

def ensure_workflow_config(config: Optional[Dict[str, Any]] = None) -> "WorkflowConfiguration":
    """Ensure a valid WorkflowConfiguration object exists."""
    if not config:
        config = {}
    if "configurable" in config:
        config = config["configurable"]
    try:
        return WorkflowConfiguration(**config)
    except Exception as e:
        raise ConfigurationError(f"Invalid configuration: {e}")