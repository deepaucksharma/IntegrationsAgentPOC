"""Integration configuration module."""
from typing import Dict, Any, Optional

class IntegrationConfig:
    """Configuration for integrations."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.config.get(key, default)
        
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self.config[key] = value
