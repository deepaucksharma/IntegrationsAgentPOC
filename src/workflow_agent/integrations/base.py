"""
Base interface for all integration plugins with streamlined responsibilities.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, ClassVar, Type
from pathlib import Path
import inspect

from ..core.state import WorkflowState
from ..error.exceptions import IntegrationError

logger = logging.getLogger(__name__)

class IntegrationBase(ABC):
    """
    Base interface for integration plugins.
    
    This class defines the core interface that all integrations must implement.
    It focuses only on integration-specific functionality and delegates other
    concerns like configuration loading, template management, etc. to the
    appropriate specialized modules.
    """
    
    # Class attributes that can be overridden by subclasses
    name: ClassVar[str] = ""
    version: ClassVar[str] = "1.0.0"
    description: ClassVar[str] = "Base integration interface"
    category: ClassVar[str] = "custom"
    supported_targets: ClassVar[List[str]] = []
    required_parameters: ClassVar[List[str]] = []
    
    def __init__(self):
        """Initialize the integration."""
        # Set name from class if not explicitly provided
        if not self.name:
            self.name = self.get_name()
            
        # Log initialization
        logger.debug(f"Initializing integration: {self.name} v{self.version}")
    
    @classmethod
    def get_name(cls) -> str:
        """
        Get the integration name from class name.
        
        Returns:
            Normalized integration name
        """
        return cls.__name__.lower().replace("integration", "")
    
    @classmethod
    def get_category(cls) -> str:
        """
        Get the integration category.
        
        Returns:
            Category identifier
        """
        return cls.category
    
    @classmethod
    def get_supported_targets(cls) -> List[str]:
        """
        Get list of supported targets.
        
        Returns:
            List of target identifiers
        """
        return cls.supported_targets
    
    @classmethod
    def get_required_parameters(cls) -> List[str]:
        """
        Get list of required parameters.
        
        Returns:
            List of required parameter names
        """
        return cls.required_parameters
        
    @abstractmethod
    async def install(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Install the integration.
        
        Args:
            parameters: Installation parameters
            
        Returns:
            Installation result with template information
        """
        raise NotImplementedError("Subclasses must implement install()")
    
    @abstractmethod
    async def verify(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify the integration installation.
        
        Args:
            parameters: Verification parameters
            
        Returns:
            Verification result with status information
        """
        raise NotImplementedError("Subclasses must implement verify()")
    
    @abstractmethod
    async def uninstall(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uninstall the integration.
        
        Args:
            parameters: Uninstallation parameters
            
        Returns:
            Uninstallation result
        """
        raise NotImplementedError("Subclasses must implement uninstall()")
    
    async def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parameters for this integration.
        
        Args:
            parameters: Parameters to validate
            
        Returns:
            Validation result with status and errors if any
        """
        errors = []
        
        # Check for required parameters
        for param in self.get_required_parameters():
            if param not in parameters:
                errors.append(f"Missing required parameter: {param}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
        
    def get_info(self) -> Dict[str, Any]:
        """
        Get integration information.
        
        Returns:
            Integration metadata
        """
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.get_category(),
            "supported_targets": self.get_supported_targets(),
            "required_parameters": self.get_required_parameters()
        }
    
    @classmethod
    def discover_implementations(cls) -> List[Type['IntegrationBase']]:
        """
        Discover all implementations of this interface.
        
        Returns:
            List of integration implementation classes
        """
        implementations = []
        
        # Get all subclasses of IntegrationBase
        def get_all_subclasses(cls):
            all_subclasses = []
            for subclass in cls.__subclasses__():
                all_subclasses.append(subclass)
                all_subclasses.extend(get_all_subclasses(subclass))
            return all_subclasses
            
        subclasses = get_all_subclasses(cls)
        
        # Filter out abstract classes
        for subclass in subclasses:
            if not inspect.isabstract(subclass):
                implementations.append(subclass)
                
        return implementations
