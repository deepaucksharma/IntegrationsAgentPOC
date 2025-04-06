"""
Base class for all integration plugins.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

from ..core.state import WorkflowState

logger = logging.getLogger(__name__)

class IntegrationBase(ABC):
    """Base class for all integration plugins."""
    
    def __init__(self):
        """Initialize the integration."""
        self.name: str = self.get_name()
        self.version: str = "1.0.0"
        self.description: str = "Base integration class"
    
    @classmethod
    def get_name(cls) -> str:
        """
        Get the integration name.
        
        Returns:
            Name of the integration
        """
        return cls.__name__.lower().replace("integration", "")
    
    @classmethod
    def get_category(cls) -> str:
        """
        Get the integration category.
        
        Returns:
            Category of the integration
        """
        return "custom"
    
    @classmethod
    def get_supported_targets(cls) -> List[str]:
        """
        Get list of supported targets.
        
        Returns:
            List of target identifiers
        """
        return []
        
    @abstractmethod
    async def install(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Install the integration.
        
        Args:
            parameters: Installation parameters
            
        Returns:
            Dictionary with installation result
        """
        raise NotImplementedError("Subclasses must implement install()")
    
    @abstractmethod
    async def verify(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify the integration installation.
        
        Args:
            parameters: Verification parameters
            
        Returns:
            Dictionary with verification result
        """
        raise NotImplementedError("Subclasses must implement verify()")
    
    @abstractmethod
    async def uninstall(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uninstall the integration.
        
        Args:
            parameters: Uninstallation parameters
            
        Returns:
            Dictionary with uninstallation result
        """
        raise NotImplementedError("Subclasses must implement uninstall()")
    
    async def validate(self, parameters: Dict[str, Any]) -> Dict[str, bool]:
        """
        Validate parameters for this integration.
        
        Args:
            parameters: Parameters to validate
            
        Returns:
            Dictionary with validation result
        """
        return {"valid": True}
        
    def get_info(self) -> Dict[str, str]:
        """
        Get integration information.
        
        Returns:
            Dictionary with integration metadata
        """
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.get_category()
        }
