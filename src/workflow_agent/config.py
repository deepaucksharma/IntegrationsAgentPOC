"""Configuration handling for workflow agent."""
from typing import Dict, Any, Optional
import os
import yaml
from pydantic import BaseModel, Field

class WorkflowConfiguration(BaseModel):
    """Configuration model for workflow agent."""
    
    # Logging configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="workflow_agent.log", description="Log file path")
    
    # Integration configuration
    template_dir: str = Field(
        default="./templates",
        description="Directory containing integration templates"
    )
    storage_dir: str = Field(
        default="./storage",
        description="Directory for persistent storage"
    )
    plugin_dirs: list[str] = Field(
        default=["./plugins"],
        description="Directories containing integration plugins"
    )
    
    # LLM configuration
    llm_provider: str = Field(
        default="gemini",
        description="LLM provider (openai or gemini)"
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key"
    )
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key"
    )
    
    # Execution configuration
    use_recovery: bool = Field(
        default=True,
        description="Enable recovery for failed workflows"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts"
    )
    timeout_seconds: int = Field(
        default=300,
        description="Timeout for workflow execution in seconds"
    )

def ensure_workflow_config(config: Optional[Dict[str, Any]] = None) -> WorkflowConfiguration:
    """Ensure valid workflow configuration."""
    if isinstance(config, WorkflowConfiguration):
        return config
        
    # Load default config
    default_config = find_default_config()
    
    # Merge with provided config
    if config:
        default_config.update(config)
        
    return WorkflowConfiguration(**default_config)

def find_default_config() -> Dict[str, Any]:
    """Find and load default configuration."""
    config_paths = [
        "workflow_config.yaml",
        "config/workflow_config.yaml",
        os.path.expanduser("~/.workflow_agent/config.yaml")
    ]
    
    for path in config_paths:
        if os.path.exists(path):
            return load_config_file(path)
            
    return {}

def load_config_file(path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    try:
        with open(path, 'r') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        raise ValueError(f"Failed to load config file {path}: {str(e)}")

def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two configuration dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result 