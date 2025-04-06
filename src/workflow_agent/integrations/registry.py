"""
Enhanced registry for integration discovery and management.
"""
import importlib
import inspect
import logging
import os
import sys
import re
from pathlib import Path
from typing import Dict, Type, List, Optional, Any, Set

from .base import IntegrationBase
from ..error.exceptions import IntegrationError, RegistrationError

logger = logging.getLogger(__name__)

class IntegrationRegistry:
    """
    Registry for managing integration plugins.
    
    This class provides functionality to:
    1. Register integration classes
    2. Discover integration plugins from directories
    3. Create and manage integration instances
    4. List available integrations
    """
    
    def __init__(self):
        """Initialize the registry."""
        self._integrations: Dict[str, Type[IntegrationBase]] = {}
        self._instances: Dict[str, IntegrationBase] = {}
        self._plugin_dirs: List[Path] = []
        self._discovered_paths: Set[str] = set()
        
    def register(self, integration_class: Type[IntegrationBase]) -> None:
        """
        Register an integration class.
        
        Args:
            integration_class: Integration class to register
            
        Raises:
            RegistrationError: If the class is not a valid integration
        """
        try:
            # Validate class is a proper integration
            if not inspect.isclass(integration_class):
                raise RegistrationError(f"Cannot register {integration_class}: Not a class")
                
            if not issubclass(integration_class, IntegrationBase):
                raise RegistrationError(
                    f"Cannot register {integration_class.__name__}: Not a subclass of IntegrationBase"
                )
                
            if inspect.isabstract(integration_class):
                logger.debug(f"Skipping abstract class: {integration_class.__name__}")
                return
                
            # Get integration name
            name = integration_class.get_name()
            if not name:
                raise RegistrationError(f"Integration {integration_class.__name__} has no name")
                
            # Register the integration
            logger.debug(f"Registering integration: {name}")
            self._integrations[name.lower()] = integration_class
            
            # Clear cached instance if exists
            if name.lower() in self._instances:
                del self._instances[name.lower()]
                
        except Exception as e:
            if isinstance(e, RegistrationError):
                raise
            raise RegistrationError(f"Error registering {getattr(integration_class, '__name__', str(integration_class))}: {e}")
        
    def get(self, name: str) -> Optional[Type[IntegrationBase]]:
        """
        Get integration class by name.
        
        Args:
            name: Integration name
            
        Returns:
            Integration class or None if not found
        """
        return self._integrations.get(name.lower())
        
    def get_instance(self, name: str) -> Optional[IntegrationBase]:
        """
        Get or create an integration instance.
        
        Args:
            name: Integration name
            
        Returns:
            Integration instance or None if not found
        """
        name = name.lower()
        
        # Return cached instance if available
        if name in self._instances:
            return self._instances[name]
            
        # Try to get the class and create instance
        cls = self.get(name)
        if cls:
            try:
                instance = cls()
                self._instances[name] = instance
                return instance
            except Exception as e:
                logger.error(f"Error instantiating integration {name}: {e}", exc_info=True)
                
        return None
        
    def get_by_target(self, target_name: str) -> List[IntegrationBase]:
        """
        Get integrations that support a specific target.
        
        Args:
            target_name: Target identifier
            
        Returns:
            List of integration instances supporting the target
        """
        result = []
        
        for name, cls in self._integrations.items():
            supported_targets = cls.get_supported_targets()
            if target_name in supported_targets:
                instance = self.get_instance(name)
                if instance:
                    result.append(instance)
                    
        return result
        
    def list_integrations(self) -> Dict[str, Dict[str, Any]]:
        """
        List all registered integrations.
        
        Returns:
            Dictionary of integration information
        """
        result = {}
        for name, cls in self._integrations.items():
            try:
                # Get instance for more detailed info
                instance = self.get_instance(name)
                if instance:
                    result[name] = instance.get_info()
                else:
                    # Fallback to basic info from class
                    result[name] = {
                        "name": name,
                        "category": cls.get_category(),
                        "supported_targets": cls.get_supported_targets(),
                        "error": "Failed to instantiate"
                    }
            except Exception as e:
                logger.error(f"Error getting info for {name}: {e}")
                result[name] = {"name": name, "error": str(e)}
                
        return result
        
    def discover_plugins(self, plugin_dirs: List[Path]) -> int:
        """
        Discover and load integration plugins.
        
        Args:
            plugin_dirs: List of directories to search for plugins
            
        Returns:
            Number of integrations discovered
        """
        self._plugin_dirs = plugin_dirs
        registered_count = 0
        
        for plugin_dir in plugin_dirs:
            # Skip if already processed
            if str(plugin_dir) in self._discovered_paths:
                continue
                
            if not plugin_dir.exists() or not plugin_dir.is_dir():
                logger.warning(f"Plugin directory not found: {plugin_dir}")
                continue
                
            logger.info(f"Searching for plugins in: {plugin_dir}")
            self._discovered_paths.add(str(plugin_dir))
            
            # Add plugin directory to path temporarily
            old_path = sys.path.copy()
            sys.path.insert(0, str(plugin_dir))
            try:
                # Look for Python modules/packages
                for item in plugin_dir.iterdir():
                    if item.is_file() and item.suffix == '.py' and not item.name.startswith('_'):
                        module_name = item.stem
                        count = self._load_module(module_name)
                        registered_count += count
                    elif item.is_dir() and (item / '__init__.py').exists():
                        module_name = item.name
                        count = self._load_module(module_name)
                        registered_count += count
            finally:
                # Restore original path
                sys.path = old_path
                    
        logger.info(f"Discovered {registered_count} integration plugins")
        return registered_count
        
    def _load_module(self, module_name: str) -> int:
        """
        Load a module and register contained integrations.
        
        Args:
            module_name: Name of module to load
            
        Returns:
            Number of integrations registered
        """
        count = 0
        try:
            # Skip modules that don't look like integrations
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*(_agent|_integration)?$', module_name):
                logger.debug(f"Skipping unlikely integration module: {module_name}")
                return 0
                
            # Import the module
            module = importlib.import_module(module_name)
            
            # Check for a get_integrations function first
            if hasattr(module, 'get_integrations') and callable(module.get_integrations):
                try:
                    integration_classes = module.get_integrations()
                    for cls in integration_classes:
                        try:
                            self.register(cls)
                            count += 1
                        except Exception as e:
                            logger.warning(f"Failed to register integration from {module_name}: {e}")
                except Exception as e:
                    logger.warning(f"Error calling get_integrations on {module_name}: {e}")
            
            # Look for IntegrationBase subclasses
            for _, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                        issubclass(obj, IntegrationBase) and 
                        obj != IntegrationBase and 
                        not inspect.isabstract(obj)):
                    try:
                        self.register(obj)
                        count += 1
                    except Exception as e:
                        logger.warning(f"Failed to register {obj.__name__} from {module_name}: {e}")
                        
            # Recursively check submodules
            if hasattr(module, '__path__'):
                package_path = Path(module.__path__[0])
                for item in package_path.iterdir():
                    if item.is_file() and item.suffix == '.py' and not item.name.startswith('_'):
                        submodule_name = f"{module_name}.{item.stem}"
                        count += self._load_module(submodule_name)
                        
        except Exception as e:
            logger.error(f"Error loading module {module_name}: {e}")
            
        return count
    
    def clear(self) -> None:
        """Clear all registered integrations and instances."""
        pre_count = len(self._integrations)
        self._integrations.clear()
        self._instances.clear()
        self._discovered_paths.clear()
        logger.debug(f"Cleared {pre_count} integrations from registry")
