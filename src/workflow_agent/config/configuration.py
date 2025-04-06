"""
Configuration management with enhanced validation and security controls.
"""
import logging
import os
import yaml
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from pydantic import BaseModel, Field, field_validator, model_validator
import dotenv

from ..error.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
dotenv.load_dotenv()

# Security patterns that should be detected and blocked
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+[/]+",  # rm -rf / or similar
    r"dd\s+if=/dev/null\s+of=/dev/",  # Dangerous dd commands
    r"mkfs",  # Format filesystem commands
    r"chmod\s+-R\s+777\s+/",  # Recursive permissions on root
    r">?\s*[/]dev[/]sd[a-z]",  # Direct writes to disk devices
    r">?\s*[/]proc",  # Direct writes to proc filesystem
    r">?\s*[/]sys",  # Direct writes to sys filesystem
    r"curl\s+.*\s*\|\s*bash",  # Pipe curl to bash
    r"wget\s+.*\s*\|\s*bash",  # Pipe wget to bash
    r"shutdown",  # System shutdown
    r"reboot",  # System reboot
    r"factory[-_]reset",  # Factory reset
    r"format\s+[a-zA-Z]:",  # Format disk in Windows
]

class SecuritySettings(BaseModel):
    """Security settings for the workflow agent."""
    
    # Security validation
    disable_security_validation: bool = Field(
        default=False, 
        description="Disable security validation entirely (DANGEROUS)"
    )
    
    # Script execution security
    least_privilege_execution: bool = Field(
        default=True, 
        description="Execute scripts with minimum necessary privileges"
    )
    script_execution_timeout: int = Field(
        default=600, 
        description="Script execution timeout in seconds"
    )
    allowed_commands: List[str] = Field(
        default=[], 
        description="List of allowed commands (if empty, all non-dangerous commands are allowed)"
    )
    blocked_commands: List[str] = Field(
        default=[], 
        description="List of blocked commands (in addition to dangerous patterns)"
    )
    allow_sudo: bool = Field(
        default=False, 
        description="Allow sudo commands in scripts"
    )
    allow_network_access: bool = Field(
        default=True, 
        description="Allow network access during script execution"
    )
    
    # Isolation settings
    use_docker_isolation: bool = Field(
        default=False, 
        description="Use Docker for script isolation"
    )
    docker_image: str = Field(
        default="ubuntu:latest", 
        description="Docker image to use for isolation"
    )
    
    # Recovery settings
    enable_recovery: bool = Field(
        default=True, 
        description="Enable automatic recovery on failure"
    )
    verify_recoveries: bool = Field(
        default=True, 
        description="Verify system state after recovery"
    )
    
    @field_validator('script_execution_timeout')
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is reasonable."""
        if v < 10:
            raise ValueError("Timeout must be at least 10 seconds")
        return v
    
    @field_validator('blocked_commands')
    @classmethod
    def validate_blocked_commands(cls, v: List[str]) -> List[str]:
        """Validate blocked commands don't include essential utilities."""
        essential_commands = ['ls', 'cd', 'pwd', 'echo', 'cat', 'grep']
        for cmd in v:
            if cmd in essential_commands:
                raise ValueError(f"Cannot block essential command: {cmd}")
        return v

class WorkflowConfiguration(BaseModel):
    """Configuration for workflow execution."""
    
    # Basic settings
    version: str = Field(default="1.0.0", description="Configuration version")
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default=None, description="Log file path")
    
    # Path settings
    config_dir: Path = Field(default=Path("./config"), description="Configuration directory")
    template_dir: Path = Field(default=Path("./templates"), description="Template directory")
    custom_template_dir: Optional[Path] = Field(default=None, description="Custom template directory")
    script_dir: Path = Field(default=Path("./generated_scripts"), description="Generated script directory")
    backup_dir: Path = Field(default=Path("./backup"), description="Backup directory")
    
    # Security settings
    security: SecuritySettings = Field(default_factory=SecuritySettings, description="Security settings")
    
    # Script generation settings
    script_generator: str = Field(default="template", description="Script generator type: template, llm, or enhanced")
    use_static_analysis: bool = Field(default=True, description="Use static analysis for scripts")
    
    # Execution settings
    isolation_method: str = Field(default="direct", description="Script isolation method: direct, docker, or vm")
    execution_timeout: int = Field(default=300, description="Script execution timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts for operations")
    
    # Verification settings
    skip_verification: bool = Field(default=False, description="Skip verification steps")
    verify_rollback: bool = Field(default=True, description="Verify system state after rollback")
    
    # Features
    use_recovery: bool = Field(default=True, description="Enable recovery on failure")
    use_llm: bool = Field(default=False, description="Use LLM for script enhancement")
    
    # Shortcuts for common security settings
    @property
    def least_privilege_execution(self) -> bool:
        """Shortcut for security.least_privilege_execution."""
        return self.security.least_privilege_execution
    
    @property
    def enable_recovery(self) -> bool:
        """Shortcut for security.enable_recovery."""
        return self.security.enable_recovery
    
    @field_validator('isolation_method')
    @classmethod
    def validate_isolation_method(cls, v: str) -> str:
        """Validate isolation method."""
        valid_methods = ['direct', 'docker', 'vm']
        if v not in valid_methods:
            raise ValueError(f"Invalid isolation method: {v}. Must be one of {valid_methods}")
        return v
    
    @field_validator('script_generator')
    @classmethod
    def validate_script_generator(cls, v: str) -> str:
        """Validate script generator type."""
        valid_types = ['template', 'llm', 'enhanced']
        if v not in valid_types:
            raise ValueError(f"Invalid script generator type: {v}. Must be one of {valid_types}")
        return v
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v
    
    @model_validator(mode='after')
    def validate_paths(self) -> 'WorkflowConfiguration':
        """Validate and create paths if needed."""
        # Prepare configuration directory
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create template directory if it doesn't exist
        self.template_dir.mkdir(parents=True, exist_ok=True)
        
        # Create script directory if it doesn't exist
        self.script_dir.mkdir(parents=True, exist_ok=True)
        
        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Check custom template directory if specified
        if self.custom_template_dir and not self.custom_template_dir.exists():
            logger.warning(f"Custom template directory does not exist: {self.custom_template_dir}")
            
        return self
    
    @model_validator(mode='after')
    def validate_docker_settings(self) -> 'WorkflowConfiguration':
        """Validate Docker settings if Docker isolation is enabled."""
        if self.isolation_method == 'docker':
            # Check if Docker image is specified
            if not self.security.docker_image:
                raise ValueError("Docker image must be specified when using Docker isolation")
            
            # Check if Docker is available
            try:
                import shutil
                if not shutil.which('docker'):
                    logger.warning("Docker isolation selected but docker command not found")
            except ImportError:
                logger.warning("Could not check for docker command")
                
        return self
    
    @model_validator(mode='after')
    def validate_script_settings(self) -> 'WorkflowConfiguration':
        """Validate script generation settings."""
        if self.script_generator == 'llm' and not self.use_llm:
            logger.warning("LLM script generation selected but use_llm is False, enabling use_llm")
            self.use_llm = True
            
        return self
        
    @model_validator(mode='after')
    def validate_security_settings(self) -> 'WorkflowConfiguration':
        """Validate security settings."""
        if not self.security.least_privilege_execution:
            logger.warning("Least privilege execution is disabled, this is potentially dangerous")
            
        if self.security.disable_security_validation:
            logger.warning("Security validation is disabled, this is EXTREMELY dangerous")
            
        return self
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.model_dump(mode='json')
    
    def save(self, path: Optional[str] = None) -> None:
        """
        Save configuration to a file.
        
        Args:
            path: Optional path to save to
        """
        if not path:
            path = self.config_dir / "workflow_config.yaml"
            
        # Create parent directory if it doesn't exist
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dictionary, handling Path objects
        config_dict = self.to_dict()
        
        # Convert Path objects to strings
        for key, value in config_dict.items():
            if isinstance(value, Path):
                config_dict[key] = str(value)
                
        # Write YAML file
        with open(path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False)
            
        logger.info(f"Configuration saved to {path}")

def load_configuration_from_file(file_path: str) -> Dict[str, Any]:
    """
    Load configuration from a file.
    
    Args:
        file_path: Path to configuration file
        
    Returns:
        Configuration dictionary
        
    Raises:
        ConfigurationError: If file not found or invalid format
    """
    try:
        with open(file_path, 'r') as f:
            if file_path.endswith('.yaml') or file_path.endswith('.yml'):
                return yaml.safe_load(f) or {}
            elif file_path.endswith('.json'):
                return json.load(f)
            else:
                raise ConfigurationError(f"Unsupported configuration file format: {file_path}")
    except FileNotFoundError:
        raise ConfigurationError(f"Configuration file not found: {file_path}")
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        raise ConfigurationError(f"Error parsing configuration file: {e}")

def load_configuration_from_env() -> Dict[str, Any]:
    """
    Load configuration from environment variables.
    
    Environment variables must have the prefix 'WORKFLOW_' to be considered.
    Nested configuration keys are specified with double underscore,
    e.g. WORKFLOW_SECURITY__LEAST_PRIVILEGE_EXECUTION.
    
    Returns:
        Configuration dictionary
    """
    env_config = {}
    prefix = 'WORKFLOW_'
    
    for key, value in os.environ.items():
        if key.startswith(prefix):
            # Remove prefix
            config_key = key[len(prefix):].lower()
            
            # Handle nested keys (e.g. WORKFLOW_SECURITY__LEAST_PRIVILEGE_EXECUTION)
            if '__' in config_key:
                parts = config_key.split('__')
                current = env_config
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = parse_env_value(value)
            else:
                env_config[config_key] = parse_env_value(value)
                
    return env_config

def parse_env_value(value: str) -> Any:
    """
    Parse environment variable value to appropriate type.
    
    Args:
        value: String value from environment variable
        
    Returns:
        Parsed value (bool, int, float, or string)
    """
    # Boolean
    if value.lower() in ('true', 'yes', '1'):
        return True
    elif value.lower() in ('false', 'no', '0'):
        return False
    
    # Try integer
    try:
        return int(value)
    except ValueError:
        pass
    
    # Try float
    try:
        return float(value)
    except ValueError:
        pass
    
    # Default to string
    return value

def load_configuration(config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from file and environment variables.
    Environment variables override file settings.
    
    Args:
        config_file: Optional configuration file path
        
    Returns:
        Merged configuration dictionary
    """
    config = {}
    
    # Default configuration file
    default_config_file = os.path.join(os.getcwd(), 'workflow_config.yaml')
    
    # Try to load configuration from file
    if config_file and os.path.exists(config_file):
        logger.info(f"Loading configuration from {config_file}")
        config.update(load_configuration_from_file(config_file))
    elif os.path.exists(default_config_file):
        logger.info(f"Loading configuration from {default_config_file}")
        config.update(load_configuration_from_file(default_config_file))
    else:
        logger.info("No configuration file found, using defaults and environment variables")
    
    # Load configuration from environment variables
    env_config = load_configuration_from_env()
    
    # Merge environment configuration into file configuration
    # Environment variables take precedence
    for key, value in env_config.items():
        if isinstance(value, dict) and key in config and isinstance(config[key], dict):
            # Deep merge dictionaries
            config[key] = {**config[key], **value}
        else:
            # Override or add value
            config[key] = value
    
    return config

def ensure_workflow_config(config: Optional[Union[Dict[str, Any], WorkflowConfiguration]] = None) -> WorkflowConfiguration:
    """
    Ensure we have a valid WorkflowConfiguration object.
    
    Args:
        config: Optional configuration as dictionary or WorkflowConfiguration
        
    Returns:
        WorkflowConfiguration object
        
    Raises:
        ConfigurationError: If configuration is invalid
    """
    try:
        if isinstance(config, WorkflowConfiguration):
            return config
        
        # Load configuration from file/env if not provided
        if config is None:
            config = load_configuration()
        
        # Convert to WorkflowConfiguration
        return WorkflowConfiguration.model_validate(config)
        
    except Exception as e:
        raise ConfigurationError(f"Invalid configuration: {str(e)}")

def validate_script_security(script_content: str) -> Dict[str, Any]:
    """
    Validate script security using pattern matching.
    
    Args:
        script_content: Script content to validate
        
    Returns:
        Dictionary with validation results
    """
    warnings = []
    errors = []
    
    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        matches = re.finditer(pattern, script_content, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            line_num = script_content[:match.start()].count('\n') + 1
            matched_text = match.group(0)
            errors.append(f"Line {line_num}: Dangerous pattern detected: {matched_text}")
    
    # Check for sudo usage
    if re.search(r"sudo\s+", script_content, re.MULTILINE):
        warnings.append("Script uses sudo, which can be dangerous")
    
    # Check for running commands from internet
    if re.search(r"(curl|wget)\s+[^|]*\|\s*(bash|sh)", script_content, re.MULTILINE):
        errors.append("Script attempts to download and execute code from internet")
    
    # Check for rm -rf or deltree with variables (dangerous)
    if re.search(r"rm\s+-[rf].*\$\{?[a-zA-Z0-9_]+\}?", script_content, re.MULTILINE):
        warnings.append("Script uses rm -rf with variables, which can be dangerous")
    
    # Check for eval or similar
    if re.search(r"eval\s+[\"\'].*[\$\[]", script_content, re.MULTILINE):
        warnings.append("Script uses eval with variables, which can be dangerous")
    
    # Check for common system commands that should be used carefully
    system_cmds = [
        "shutdown", "reboot", "init", "halt",
        "mkfs", "fdisk", "dd", "mkswap",
        "mount", "umount"
    ]
    
    for cmd in system_cmds:
        if re.search(r"\b" + cmd + r"\b", script_content, re.MULTILINE):
            warnings.append(f"Script uses system command '{cmd}', which should be used carefully")
    
    return {
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors
    }

def sanitize_command(command: str) -> str:
    """
    Sanitize a command to prevent command injection.
    
    Args:
        command: Command to sanitize
        
    Returns:
        Sanitized command
    """
    # Remove shell special characters
    sanitized = re.sub(r'[;&|`$]', '', command)
    
    # Remove potentially dangerous options
    sanitized = re.sub(r'\s+-[rf]+\s+/', ' ', sanitized)
    
    return sanitized.strip()
