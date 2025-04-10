"""
Enhanced integration manager for handling integration lifecycle.
"""
import logging
import importlib
import inspect
from typing import Dict, Any, Optional, List, Type, Set
from pathlib import Path

from .base import IntegrationBase
from .registry import IntegrationRegistry
from ..error.exceptions import IntegrationError, ConfigurationError
from ..config.configuration import WorkflowConfiguration

logger = logging.getLogger(__name__)

class IntegrationManager:
    """
    Manages integration operations and lifecycle.
    
    This class is responsible for:
    1. Discovering and registering integrations
    2. Managing integration instances
    3. Coordinating integration operations
    4. Validating integration parameters
    
    It delegates template management and execution to specialized modules.
    """
    
    def __init__(self, config: WorkflowConfiguration, registry: Optional[IntegrationRegistry] = None):
        """
        Initialize with configuration.
        
        Args:
            config: Workflow configuration
            registry: Optional integration registry (will create if not provided)
        """
        self.config = config
        self.registry = registry or IntegrationRegistry()
        
        # Track loaded modules to avoid duplicates
        self._loaded_modules: Set[str] = set()
        
        # Initialize registry
        self._initialize_registry()
        
        logger.info(f"IntegrationManager initialized with {len(self.registry.list_integrations())} integrations")
        
    def _initialize_registry(self) -> None:
        """Initialize the integration registry with all available integrations."""
        # First discover built-in integrations
        self._discover_built_in_integrations()
        
        # Then discover plugins if plugin dirs specified
        if hasattr(self.config, 'plugin_dirs') and self.config.plugin_dirs:
            plugin_count = self.registry.discover_plugins(self.config.plugin_dirs)
            logger.info(f"Discovered {plugin_count} integration plugins")
        
    def _discover_built_in_integrations(self) -> None:
        """
        Discover and register built-in integrations using a consolidated approach.
        This method prevents duplicate registrations by using the registry's duplicate detection.
        """
        try:
            # Approach 1: Direct import of known integration packages
            integration_packages = []
            
            # Import the core integration packages
            try:
                from . import custom, infra_agent
                integration_packages.extend([custom, infra_agent])
            except ImportError as e:
                logger.warning(f"Could not import core integration packages: {e}")
            
            # Process each package
            for package in integration_packages:
                module_name = package.__name__
                if module_name in self._loaded_modules:
                    continue
                    
                self._loaded_modules.add(module_name)
                logger.debug(f"Processing integration package: {module_name}")
                
                # Look for integration classes in the package
                for name, obj in inspect.getmembers(package):
                    if (inspect.isclass(obj) and 
                            issubclass(obj, IntegrationBase) and 
                            obj != IntegrationBase and
                            not inspect.isabstract(obj)):
                        self.registry.register(obj)
            
            # Approach 2: Use the IntegrationBase discovery mechanism
            # This is a backup mechanism and may find the same integrations,
            # but the registry handles duplicates appropriately
            discovered = IntegrationBase.discover_implementations()
            for impl_class in discovered:
                self.registry.register(impl_class)
                
            logger.info(f"Discovered {len(self.registry.list_integrations())} built-in integrations")
            
        except Exception as e:
            logger.error(f"Error discovering built-in integrations: {e}", exc_info=True)
    
    async def execute_integration_action(
        self, 
        integration_type: str, 
        action: str, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute an integration action with the given parameters.
        
        Args:
            integration_type: Type of integration to use
            action: Action to perform (install, verify, uninstall)
            parameters: Parameters for the action
            
        Returns:
            Action result
            
        Raises:
            IntegrationError: If integration not found or action fails
        """
        # Get the integration
        integration = self.get_integration(integration_type)
        if not integration:
            available = ", ".join(list(self.registry.list_integrations().keys()))
            raise IntegrationError(
                f"Integration '{integration_type}' not found. Available: {available}",
                details={"available_integrations": available}
            )
        
        # Validate parameters
        validation = await integration.validate_parameters(parameters)
        if not validation.get("valid", False):
            errors = validation.get("errors", ["Unknown validation error"])
            error_msg = "; ".join(errors)
            raise IntegrationError(
                f"Invalid parameters for {integration_type}: {error_msg}",
                details={"errors": errors}
            )
        
        # Execute the requested action
        try:
            if action == "install":
                return await integration.install(parameters)
            elif action == "verify":
                return await integration.verify(parameters)
            elif action == "uninstall":
                return await integration.uninstall(parameters)
            else:
                raise IntegrationError(
                    f"Unsupported action: {action}",
                    details={"supported_actions": ["install", "verify", "uninstall"]}
                )
        except Exception as e:
            if isinstance(e, IntegrationError):
                raise
            raise IntegrationError(
                f"Error executing {action} on {integration_type}: {str(e)}",
                details={"error": str(e), "integration": integration_type, "action": action}
            ) from e
    
    def get_integration(self, integration_type: str) -> Optional[IntegrationBase]:
        """
        Get an integration instance by type.
        
        Args:
            integration_type: Type of integration
            
        Returns:
            Integration instance or None if not found
        """
        integration = self.registry.get_instance(integration_type)
        if not integration:
            logger.warning(f"Integration not found: {integration_type}")
            
        return integration
        
    def list_integrations(self) -> Dict[str, Dict[str, Any]]:
        """
        List all available integrations with their metadata.
        
        Returns:
            Dictionary of integration information
        """
        return self.registry.list_integrations()
        
    def get_integration_info(self, integration_type: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific integration.
        
        Args:
            integration_type: Type of integration
            
        Returns:
            Integration information or None if not found
        """
        integration = self.get_integration(integration_type)
        if integration:
            return integration.get_info()
        return None
        
    def reload_integrations(self) -> int:
        """
        Reload all integrations (clear and rediscover).
        
        Returns:
            Number of integrations loaded
        """
        # Clear existing integrations
        self.registry.clear()
        self._loaded_modules.clear()
        
        # Rediscover integrations
        self._initialize_registry()
        
        # Return count
        return len(self.registry.list_integrations())
