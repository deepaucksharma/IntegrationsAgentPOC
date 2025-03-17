import abc
from typing import Any, Dict, List, Optional

class PluginInterface(abc.ABC):
    """Interface for plugins to extend agent functionality."""
    
    @abc.abstractmethod
    def get_name(self) -> str:
        """Return the plugin name."""
        pass
    
    @abc.abstractmethod
    def get_version(self) -> str:
        """Return the plugin version."""
        pass
    
    @abc.abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data according to plugin functionality.
        
        Args:
            input_data: Data to be processed
            
        Returns:
            Processing results
        """
        pass