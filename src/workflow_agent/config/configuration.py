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
from pydantic import BaseModel, Field, field_validator, model_validator
from ..error.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Patterns that might indicate dangerous operations
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",                # Delete root directory
    r"rm\s+-rf\s+~",                # Delete home directory
    r"rm\s+-rf\s+\.\.",             # Delete parent directory
    r"chmod\s+-R\s+777",            # Set insecure permissions
    r"dd\s+if=/dev/urandom",        # Potentially destructive disk operations
    r":\(\)\s*{\s*:\|:&\s*};:",     # Fork bomb pattern
    r"eval.*\$\(curl",              # Execute code from internet
    r"wget.*\|\s*bash",             # Execute code from internet
    r"curl.*\|\s*bash",             # Execute code from internet
    r".*>\s*/dev/sd[a-z]",          # Write directly to disk device
    r"rm\s+-rf\s+/\*",              # Delete all files in root
    r"mkfs\..*\s+/dev/sd[a-z]",     # Format disk
    r"fdisk\s+/dev/sd[a-z]",        # Partition disk
    r"dd\s+.*\s+of=/dev/sd[a-z]",   # Low-level disk writing
    r"shutdown",                    # System shutdown
    r"reboot",                      # System reboot
    r"poweroff",                    # System power off
    r"halt",                        # System halt
]

class WorkflowConfiguration(BaseModel):
    """Configuration for workflow execution."""
    
    # General settings
    debug: bool = False
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # Script generation settings
    script_generator: str = "basic"  # basic, llm, enhanced
    template_dir: Path = Path("./templates")
    
    # LLM settings
    llm_provider: str = "openai"  # openai, gemini
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    
    # Execution settings
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 300.0
    
    # Storage settings
    storage_dir: Path = Path("./storage")
    knowledge_dir: Path = Path("./knowledge")
    
    user_id: str = Field(default="test_user", description="User identifier")
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
    docs_cache_dir: Optional[Path] = Field(default=Path("./cache/docs"), description="Documentation cache directory")
    docs_cache_ttl: int = Field(default=86400, description="Documentation cache TTL in seconds", ge=1)
    use_recovery: bool = Field(default=True, description="Use recovery")
    error_handling: Dict[str, Any] = Field(
        default_factory=lambda: {
            "continue_on_error": False,
            "max_retries": 3,
            "retry_delay": 5
        },
        description="Error handling configuration"
    )

    @field_validator("isolation_method")
    @classmethod
    def validate_isolation_method(cls, value: str) -> str:
        """Validate isolation method."""
        valid_methods = {"docker", "chroot", "venv", "direct", "none"}
        if value.lower() not in valid_methods:
            raise ValueError(f"Invalid isolation method '{value}'. Must be one of: {valid_methods}")
        return value.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        value_upper = value.upper()
        if value_upper not in valid_levels:
            raise ValueError(f"Invalid log level '{value}'. Must be one of: {valid_levels}")
        return value_upper

    @field_validator("template_dir", "custom_template_dir", "docs_cache_dir", "storage_dir", "knowledge_dir")
    @classmethod
    def convert_single_path(cls, value: Any) -> Optional[Path]:
        """Convert single path strings to Path objects."""
        if value is None:
            return None
        if isinstance(value, str):
            return Path(value).resolve()
        if isinstance(value, Path):
            return value.resolve()
        raise ValueError(f"Invalid path value: {value}")

    @field_validator("plugin_dirs", mode="before")
    @classmethod
    def convert_path_list(cls, value: Any) -> List[Path]:
        """Convert path strings in lists to Path objects."""
        if not isinstance(value, list):
            raise ValueError("plugin_dirs must be a list")
        return [Path(v).resolve() if isinstance(v, (str, Path)) else v for v in value]

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, value: str) -> str:
        """Validate LLM provider."""
        valid_providers = {"openai", "gemini", "none"}
        if value.lower() not in valid_providers:
            raise ValueError(f"Invalid LLM provider '{value}'. Must be one of: {valid_providers}")
        return value.lower()

    @model_validator(mode="before")
    @classmethod
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
    
    @model_validator(mode="before")
    @classmethod
    def setup_api_keys(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Set up API keys from environment if not provided."""
        # Set up OpenAI API key
        if not values.get("openai_api_key"):
            values["openai_api_key"] = os.environ.get("OPENAI_API_KEY")
            if not values["openai_api_key"] and values.get("llm_provider") == "openai":
                logger.warning("No OpenAI API key found in config or environment")
        
        # Set up Gemini API key
        if not values.get("gemini_api_key"):
            values["gemini_api_key"] = os.environ.get("GEMINI_API_KEY")
            if not values["gemini_api_key"] and values.get("llm_provider") == "gemini":
                logger.warning("No Gemini API key found in config or environment")
        
        return values
        
    @model_validator(mode="after")
    def validate_paths_exist(self) -> 'WorkflowConfiguration':
        """Validate that specified paths exist and are accessible."""
        paths_to_check = {
            "template_dir": self.template_dir,
            "storage_dir": self.storage_dir,
            "knowledge_dir": self.knowledge_dir,
        }
        
        if self.custom_template_dir:
            paths_to_check["custom_template_dir"] = self.custom_template_dir
            
        if self.docs_cache_dir:
            paths_to_check["docs_cache_dir"] = self.docs_cache_dir
        
        for path_name, path in paths_to_check.items():
            if path is not None:
                try:
                    if not path.exists():
                        path.mkdir(parents=True, exist_ok=True)
                        logger.info(f"Created directory for {path_name}: {path}")
                except Exception as e:
                    logger.warning(f"Failed to create {path_name} directory: {e}")
                
        return self
    
    @model_validator(mode="after")
    def validate_security_settings(self) -> 'WorkflowConfiguration':
        """Validate security-related configuration settings."""
        if self.skip_verification and not self.least_privilege_execution:
            logger.warning("Security risk: Skip verification enabled without least privilege execution")
            
        if self.isolation_method == "none" and self.use_isolation:
            logger.warning("Conflicting settings: isolation_method is 'none' but use_isolation is True")
            
        if self.execution_timeout > 3600:
            logger.warning("Security risk: Long execution timeout may lead to resource exhaustion")
            
        return self

    class Config:
        """Pydantic configuration."""
        extra = "allow"  # Allow extra fields
        validate_assignment = True  # Validate when attributes are assigned
        arbitrary_types_allowed = True  # Allow arbitrary types (like Path)


def ensure_workflow_config(config: Optional[Dict[str, Any]] = None) -> WorkflowConfiguration:
    """Ensure a valid workflow configuration."""
    if isinstance(config, WorkflowConfiguration):
        return config
        
    # Start with empty config if none provided
    if config is None:
        config = {}
        
    # Try to load from default locations
    default_config = find_default_config() or {}
    
    # Merge with default config (default config has lower precedence)
    merged_config = {**default_config, **config}
    
    # Create and validate configuration
    try:
        return WorkflowConfiguration(**merged_config)
    except Exception as e:
        raise ConfigurationError(f"Invalid configuration: {str(e)}")


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


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two configuration dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result


def validate_script_security(script_content: str) -> Dict[str, Any]:
    """
    Validate script content for potentially dangerous operations using multiple methods.
    
    Args:
        script_content: Script content to validate
        
    Returns:
        Dict with validation results (valid: bool, warnings: list, errors: list)
    """
    warnings = []
    errors = []
    
    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, script_content, re.IGNORECASE):
            errors.append(f"Dangerous pattern detected: {pattern}")
    
    # Check for suspicious commands based on context
    suspicious_cmds = [
        r"\bformat\b",
        r"\bmkfs\b",
        r"\bfdisk\b",
        r"wget.*sudo",
        r"curl.*sudo",
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bservice\s+.*\s+stop\b",
        r"\bsystemctl\s+stop\b",
        r"\bkill\s+-9\b",
        r"\bkillall\b",
        r"\biptables\s+-F\b"
    ]
    
    for cmd in suspicious_cmds:
        if re.search(cmd, script_content, re.IGNORECASE):
            warnings.append(f"Suspicious command detected: {cmd}")
    
    # Check for common syntax errors
    syntax_errors = [
        r"if\s+\[\s*[^]]+$",                # Unclosed if statement brackets
        r"\bfi\b\s*\bfi\b",                 # Double "fi" closure
        r"\besac\b\s*\besac\b",             # Double "esac" closure
        r"\bdone\b\s*\bdone\b",             # Double "done" closure
        r"^\s*}\s*$",                       # Standalone closing brace
        r"\$\(\(",                          # Missing closing parenthesis in arithmetic expansion
    ]
    
    for error_pattern in syntax_errors:
        if re.search(error_pattern, script_content, re.MULTILINE):
            warnings.append(f"Potential syntax error: {error_pattern}")
    
    # Try to use shellcheck if available for shell scripts
    try:
        if "#!/bin/bash" in script_content or "#!/bin/sh" in script_content:
            with tempfile.NamedTemporaryFile(suffix=".sh", delete=False) as temp:
                temp_path = temp.name
                temp.write(script_content.encode())
            
            try:
                # Run shellcheck to find issues
                result = subprocess.run(
                    ["shellcheck", "-f", "json", temp_path],
                    capture_output=True, text=True, check=False
                )
                
                if result.returncode == 0:
                    logger.debug("Shellcheck validation passed")
                else:
                    try:
                        shellcheck_output = json.loads(result.stdout)
                        for issue in shellcheck_output:
                            level = issue.get("level", "").lower()
                            message = issue.get("message", "")
                            
                            if level == "error":
                                errors.append(f"Shellcheck error: {message}")
                            else:
                                warnings.append(f"Shellcheck warning: {message}")
                    except json.JSONDecodeError:
                        warnings.append("Failed to parse shellcheck output")
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass
    except FileNotFoundError:
        logger.warning("Shellcheck not available for additional validation")
    except Exception as e:
        logger.warning(f"Shellcheck validation error: {e}")
    
    # Validate PowerShell on Windows systems
    if os.name == 'nt' and ('<#' in script_content or 'function ' in script_content or '$ErrorActionPreference' in script_content):
        try:
            with tempfile.NamedTemporaryFile(suffix=".ps1", delete=False) as temp:
                temp_path = temp.name
                temp.write(script_content.encode())
            
            try:
                # Check PowerShell syntax
                result = subprocess.run(
                    ["powershell", "-Command", f"$ErrorActionPreference='Stop'; $null = [System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw '{temp_path}'), [ref]$null)"],
                    capture_output=True, text=True, check=False
                )
                
                if result.returncode != 0:
                    for line in result.stderr.splitlines():
                        if line.strip():
                            errors.append(f"PowerShell syntax error: {line.strip()}")
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass
        except Exception as e:
            warnings.append(f"PowerShell validation error: {e}")
    
    # Determine overall validity - if there are errors, it's not valid
    valid = len(errors) == 0
    
    return {
        "valid": valid,
        "warnings": warnings,
        "errors": errors
    }
