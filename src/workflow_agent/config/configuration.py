import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pydantic import BaseModel, Field, validator
import yaml
import json

logger = logging.getLogger(__name__)

# Valid isolation methods
VALID_ISOLATION_METHODS = {"docker", "chroot", "venv", "none"}

class WorkflowConfiguration(BaseModel):
    """Configuration for the workflow agent."""
    user_id: str = "cli-user"
    model_name: str = "openai/gpt-3.5-turbo"
    system_prompt: str = "You are a helpful workflow agent."
    template_dir: str = "./templates"
    custom_template_dir: Optional[str] = None  # Added: for user-defined templates
    use_isolation: bool = True  # Changed default to True for security
    enforce_isolation: bool = False  # New: Whether to fail if isolation method is not available
    isolation_method: str = "docker"  # Added: docker, chroot, venv, none
    execution_timeout: int = 30000  # in milliseconds
    skip_verification: bool = False
    use_llm_optimization: bool = False  # Added: make LLM optimization optional
    rule_based_optimization: bool = False  # Added: alternative to LLM optimization
    use_static_analysis: bool = False  # Added: for script validation
    db_connection_string: Optional[str] = None  # Added: for database scaling
    prune_history_days: Optional[int] = None  # Added: for history management
    plugin_dirs: List[str] = Field(default_factory=lambda: ["./plugins"])  # Added: for plugin architecture
    async_execution: bool = False  # Added: for concurrent execution
    max_concurrent_tasks: int = 5  # Added: for concurrent execution
    least_privilege_execution: bool = True  # Added: for security
    sandbox_isolation: bool = False  # Added: for stronger isolation
    log_level: str = "INFO"
    
    @validator('isolation_method')
    def validate_isolation_method(cls, v):
        if v not in VALID_ISOLATION_METHODS:
            raise ValueError(f"Invalid isolation method: {v}. Must be one of {', '.join(VALID_ISOLATION_METHODS)}")
        return v
    
    @validator('use_isolation', 'sandbox_isolation')
    def validate_isolation_settings(cls, v, values):
        if v and values.get('isolation_method') == 'none':
            raise ValueError("Cannot use isolation with isolation_method='none'")
        return v
    
    class Config:
        """Configuration for the model."""
        extra = "allow"  # Allow extra fields for extensions

def ensure_workflow_config(config: Optional[Dict[str, Any]] = None) -> WorkflowConfiguration:
    """
    Ensure a valid workflow configuration exists.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Validated WorkflowConfiguration object
        
    Raises:
        ValueError: If configuration is invalid
    """
    if config is None:
        config = {}
    
    try:
        # Handle nested config structure
        if "configurable" in config:
            config = config["configurable"]
        
        # Validate isolation settings
        if config.get("use_isolation", True):
            isolation_method = config.get("isolation_method")
            if not isolation_method:
                if config.get("enforce_isolation", False):
                    raise ValueError(
                        "Isolation is enforced but no isolation method specified. "
                        "Please specify an isolation method or set enforce_isolation=False."
                    )
                logger.warning(
                    "Isolation requested but no isolation method specified. "
                    "This may lead to direct execution without isolation. "
                    "Consider specifying an isolation method or explicitly setting use_isolation=False."
                )
            elif isolation_method not in VALID_ISOLATION_METHODS:
                raise ValueError(
                    f"Invalid isolation method: {isolation_method}. "
                    f"Must be one of {', '.join(VALID_ISOLATION_METHODS)}"
                )
        
        return WorkflowConfiguration(**config)
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise ValueError(f"Invalid configuration: {e}") from e

# Global verification commands for supported targets/actions.
verification_commands: Dict[str, str] = {
    # Example: key "postgres-verify" can include a shell command template.
    "postgres-verify": "psql -h {{ parameters.db_host }} -p {{ parameters.db_port }} -c '\\l'",
    "mysql-verify": "mysql -h {{ parameters.db_host }} -P {{ parameters.db_port }} -e 'SHOW DATABASES;'"
}

# Function to load verification commands from external files
def load_verification_commands(verif_dir: str) -> None:
    """
    Load verification commands from external files.
    
    Args:
        verif_dir: Directory containing verification command files
    """
    global verification_commands
    
    dir_path = Path(verif_dir)
    if not dir_path.exists():
        logger.warning(f"Verification directory not found: {verif_dir}")
        return
    
    for file_path in dir_path.glob("*.{json,yaml,yml}"):
        try:
            with open(file_path, "r") as f:
                if str(file_path).endswith((".yaml", ".yml")):
                    commands = yaml.safe_load(f)
                else:
                    commands = json.loads(f.read())
                
                if commands and isinstance(commands, dict):
                    verification_commands.update(commands)
                    logger.info(f"Loaded verification commands from {file_path}")
        except Exception as e:
            logger.error(f"Error loading verification commands from {file_path}: {e}")

# List of dangerous command patterns for script validation
dangerous_patterns: List[str] = [
    r"rm\s+(-rf?\s+)?\/(?!\w)",
    r"mkfs",
    r"dd\s+if=.*\s+of=\/dev",
    r">\s*\/dev\/[hs]d[a-z]",
    r"chmod\s+777",
    r"chmod\s+-R\s+777",
    r"wget.*\s+\|\s+bash",
    r"curl.*\s+\|\s+bash",
    r":(){:\|:&};:",
    r"rm\s+-rf\s+~",
    r"wipe\s+.*\/dev",
    r"fdisk\s+\/dev.*\s+(d|n)",
    # Added more dangerous patterns
    r"chown\s+-R\s+root",
    r"killall\s+.*",
    r"rm\s+-rf\s+\*",
    r"rm\s+-rf\s+\/\w+\/\*",
    r">\s*\/etc\/passwd",
    r">\s*\/etc\/shadow",
    r"chmod\s+[0-7]*777[0-7]*\s+",
    r"shutdown\s+(now|-h|-r)",
    r"reboot\s+",
    r"init\s+[06]"
]

# Function to load dangerous patterns from external file
def load_dangerous_patterns(pattern_file: str) -> None:
    """
    Load dangerous command patterns from a file.
    
    Args:
        pattern_file: File containing patterns, one per line
    """
    global dangerous_patterns
    
    try:
        with open(pattern_file, "r") as f:
            patterns = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            if patterns:
                dangerous_patterns.extend(patterns)
                logger.info(f"Loaded {len(patterns)} dangerous patterns from {pattern_file}")
    except Exception as e:
        logger.error(f"Error loading dangerous patterns from {pattern_file}: {e}")