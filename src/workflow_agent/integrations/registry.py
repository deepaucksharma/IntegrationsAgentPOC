"""
Registry for integrations with improved discovery.
"""
import importlib
import inspect
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Type, List, Optional, Any

from .base import IntegrationBase
from ..error.exceptions import IntegrationError

logger = logging.getLogger(__name__)

class IntegrationRegistry:
    """Registry for all available integrations."""
    
    def __init__(self):
        """Initialize the registry."""
        self._integrations: Dict[str, Type[IntegrationBase]] = {}
        self._instances: Dict[str, IntegrationBase] = {}
        self._plugin_dirs: List[Path] = []
        
    def register(self, integration_class: Type[IntegrationBase]) -> None:
        """
        Register an integration class.
        
        Args:
            integration_class: Integration class to register
        """
        if not issubclass(integration_class, IntegrationBase):
            raise IntegrationError(
                f"Cannot register {integration_class.__name__}: Not a subclass of IntegrationBase"
            )
            
        name = integration_class.get_name()
        logger.debug(f"Registering integration: {name}")
        self._integrations[name] = integration_class
        
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
                logger.error(f"Error instantiating integration {name}: {e}")
                
        return None
        
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
        count = 0
        
        for plugin_dir in plugin_dirs:
            if not plugin_dir.exists() or not plugin_dir.is_dir():
                logger.warning(f"Plugin directory not found: {plugin_dir}")
                continue
                
            logger.info(f"Searching for plugins in: {plugin_dir}")
            
            # Add plugin directory to path temporarily
            sys.path.insert(0, str(plugin_dir))
            try:
                # Look for Python modules/packages
                for item in plugin_dir.iterdir():
                    if item.is_file() and item.suffix == '.py' and not item.name.startswith('_'):
                        module_name = item.stem
                        self._load_module(module_name)
                        count += 1
                    elif item.is_dir() and (item / '__init__.py').exists():
                        module_name = item.name
                        self._load_module(module_name)
                        count += 1
            finally:
                # Remove from path
                if str(plugin_dir) in sys.path:
                    sys.path.remove(str(plugin_dir))
                    
        logger.info(f"Discovered {count} integration plugins")
        return count
        
    def _load_module(self, module_name: str) -> None:
        """
        Load a module and register contained integrations.
        
        Args:
            module_name: Name of module to load
        """
        try:
            module = importlib.import_module(module_name)
            for _, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and issubclass(obj, IntegrationBase) 
                        and obj != IntegrationBase):
                    self.register(obj)
        except Exception as e:
            logger.error(f"Error loading module {module_name}: {e}")
            
    def _discover_integrations(self) -> None:
        """Discover built-in integrations."""
        # Look for integrations in infra_agent and custom directories
        package_path = Path(__file__).parent
        subdirs = ['infra_agent', 'custom']
        
        for subdir in subdirs:
            subdir_path = package_path / subdir
            if not subdir_path.exists() or not subdir_path.is_dir():
                continue
                
            # Import the module
            try:
                module_name = f"workflow_agent.integrations.{subdir}"
                module = importlib.import_module(module_name)
                
                # Look for IntegrationBase subclasses
                for _, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and issubclass(obj, IntegrationBase) 
                            and obj != IntegrationBase):
                        self.register(obj)
            except Exception as e:
                logger.error(f"Error loading built-in integration {subdir}: {e}")
