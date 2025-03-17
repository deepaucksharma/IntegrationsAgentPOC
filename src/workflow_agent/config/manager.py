import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import yaml
from dataclasses import dataclass
from .schemas import ParameterSpec
from functools import lru_cache
from .configuration import WorkflowConfiguration, ensure_workflow_config
from ..error.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

@dataclass
class WorkflowConfig:
    """Workflow configuration data class."""
    name: str
    description: str
    version: str
    parameters: Dict[str, ParameterSpec]
    targets: Dict[str, Dict[str, Any]]
    templates_dir: str
    scripts_dir: str
    timeout: int
    max_retries: int
    retry_delay: int
    log_level: str
    log_file: str
    history_enabled: bool
    history_retention_days: int

class ConfigurationManager:
    """Centralized configuration management with caching support."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the configuration manager."""
        self.config_dir = config_dir or Path("config")
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._config: Optional[WorkflowConfiguration] = None
    
    @lru_cache(maxsize=1)
    def get_workflow_config(self, config: Optional[Dict[str, Any]] = None) -> WorkflowConfiguration:
        """
        Get workflow configuration with caching.
        
        Args:
            config: Optional configuration dictionary to override defaults
            
        Returns:
            Validated WorkflowConfiguration object
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        try:
            # Load base config from file if exists
            base_config = {}
            config_path = self.config_dir / "workflow_config.yaml"
            if config_path.exists():
                with open(config_path) as f:
                    base_config = yaml.safe_load(f)
            
            # Override with environment variables
            env_config = self._load_env_config()
            
            # Merge configurations with proper precedence
            merged_config = self._merge_configs(base_config, env_config, config or {})
            
            # Validate and create WorkflowConfiguration
            return ensure_workflow_config(merged_config)
        except Exception as e:
            logger.error(f"Failed to load workflow config: {e}")
            raise ConfigurationError(f"Invalid workflow configuration: {str(e)}")
    
    def _load_env_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        prefix = 'WORKFLOW_'
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Convert WORKFLOW_TIMEOUT to timeout
                config_key = key[len(prefix):].lower()
                config[config_key] = value
                
        return config
    
    def _merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple configuration dictionaries with proper precedence."""
        result = {}
        
        for config in configs:
            for key, value in config.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = self._merge_configs(result[key], value)
                else:
                    result[key] = value
        
        return result
    
    def clear_cache(self) -> None:
        """Clear all cached configurations."""
        self.get_workflow_config.cache_clear()
        logger.info("Cleared configuration cache")
    
    def reload_config(self) -> None:
        """Reload all configurations."""
        self.clear_cache()
        logger.info("Reloaded all configurations")
    
    def save_config(self, config: WorkflowConfiguration) -> None:
        """
        Save configuration to file.
        
        Args:
            config: Configuration to save
        """
        try:
            config_path = self.config_dir / "workflow_config.yaml"
            with open(config_path, 'w') as f:
                yaml.dump(config.dict(), f, default_flow_style=False)
            logger.info(f"Saved configuration to {config_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise ConfigurationError(f"Failed to save configuration: {str(e)}")

class ConfigManager:
    """Centralized configuration management."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = config_path or os.getenv('WORKFLOW_CONFIG_PATH')
        self.config: Optional[WorkflowConfig] = None
        self._load_config()
        
    def _load_config(self) -> None:
        """Load configuration from file and environment variables."""
        try:
            # Load base config from file if exists
            base_config = {}
            if self.config_path and os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    base_config = yaml.safe_load(f)
                    
            # Override with environment variables
            env_config = self._load_env_config()
            config = {**base_config, **env_config}
            
            # Validate and create WorkflowConfig
            self.config = WorkflowConfig(
                name=config.get('name', 'workflow-agent'),
                description=config.get('description', ''),
                version=config.get('version', '1.0.0'),
                parameters=self._load_parameters(config.get('parameters', {})),
                targets=config.get('targets', {}),
                templates_dir=config.get('templates_dir', 'templates'),
                scripts_dir=config.get('scripts_dir', 'scripts'),
                timeout=config.get('timeout', 300),
                max_retries=config.get('max_retries', 3),
                retry_delay=config.get('retry_delay', 5),
                log_level=config.get('log_level', 'INFO'),
                log_file=config.get('log_file', 'workflow.log'),
                history_enabled=config.get('history_enabled', True),
                history_retention_days=config.get('history_retention_days', 30)
            )
            
            # Create required directories
            self._ensure_directories()
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
            
    def _load_env_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        prefix = 'WORKFLOW_'
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Convert WORKFLOW_TIMEOUT to timeout
                config_key = key[len(prefix):].lower()
                config[config_key] = value
                
        return config
        
    def _load_parameters(self, params: Dict[str, Any]) -> Dict[str, ParameterSpec]:
        """Load parameter specifications."""
        parameters = {}
        
        for name, spec in params.items():
            parameters[name] = ParameterSpec(
                name=name,
                type=spec.get('type', 'string'),
                description=spec.get('description', ''),
                required=spec.get('required', False),
                default=spec.get('default'),
                validation=spec.get('validation', {})
            )
            
        return parameters
        
    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        if self.config:
            for directory in [self.config.templates_dir, self.config.scripts_dir]:
                Path(directory).mkdir(parents=True, exist_ok=True)
                
    def get_config(self) -> WorkflowConfig:
        """Get the current configuration."""
        if not self.config:
            self._load_config()
        return self.config
        
    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        Update configuration with new values.
        
        Args:
            updates: Dictionary of configuration updates
        """
        if not self.config:
            self._load_config()
            
        # Update config attributes
        for key, value in updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                
        # Save to file if config_path is set
        if self.config_path:
            self._save_config()
            
    def _save_config(self) -> None:
        """Save current configuration to file."""
        if not self.config or not self.config_path:
            return
            
        try:
            config_dict = {
                'name': self.config.name,
                'description': self.config.description,
                'version': self.config.version,
                'parameters': {
                    name: {
                        'type': spec.type,
                        'description': spec.description,
                        'required': spec.required,
                        'default': spec.default,
                        'validation': spec.validation
                    }
                    for name, spec in self.config.parameters.items()
                },
                'targets': self.config.targets,
                'templates_dir': self.config.templates_dir,
                'scripts_dir': self.config.scripts_dir,
                'timeout': self.config.timeout,
                'max_retries': self.config.max_retries,
                'retry_delay': self.config.retry_delay,
                'log_level': self.config.log_level,
                'log_file': self.config.log_file,
                'history_enabled': self.config.history_enabled,
                'history_retention_days': self.config.history_retention_days
            }
            
            with open(self.config_path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False)
                
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            raise 