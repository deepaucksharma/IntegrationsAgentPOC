"""
Integration manager for handling plugin loading and management.
"""
import logging
import importlib
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Type

from .base import IntegrationBase
from .registry import IntegrationRegistry

logger = logging.getLogger(__name__)

class IntegrationManager:
    """Manages integration plugins."""
    
    def __init__(self, plugin_dirs: List[str]):
        self.plugin_dirs = plugin_dirs
        self._integrations: Dict[str, Type[IntegrationBase]] = {}
        self._loaded_integrations: Dict[str, IntegrationBase] = {}
        
    async def initialize(self) -> None:
        """Initialize the integration manager."""
        logger.info("Initializing integration manager...")
        
        # First load built-in integrations
        await self._load_builtin_integrations()
        
        # Then load external plugins
        for plugin_dir in self.plugin_dirs:
            await self._load_plugins_from_dir(plugin_dir)
            
        logger.info(f"Loaded {len(self._integrations)} integration types")
        
    async def _load_builtin_integrations(self) -> None:
        """Load built-in integrations."""
        try:
            # Get the integrations directory path
            package_path = Path(__file__).parent
            
            # Load each integration module
            for item in package_path.iterdir():
                if item.is_dir() and not item.name.startswith('__'):
                    try:
                        module_name = f"{__package__}.{item.name}"
                        module = importlib.import_module(module_name)
                        
                        # Look for IntegrationBase subclasses
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (isinstance(attr, type) and 
                                issubclass(attr, IntegrationBase) and 
                                attr is not IntegrationBase):
                                integration_instance = attr()
                                self._integrations[integration_instance.get_name()] = attr
                                logger.info(f"Loaded built-in integration: {attr_name}")
                                
                    except Exception as e:
                        logger.warning(f"Failed to load built-in integration {item.name}: {e}")
                        
        except Exception as e:
            logger.error(f"Error loading built-in integrations: {e}")
                
    async def _load_plugins_from_dir(self, plugin_dir: str) -> None:
        """Load plugins from a directory."""
        try:
            plugin_path = Path(plugin_dir)
            if not plugin_path.exists():
                logger.warning(f"Plugin directory not found: {plugin_dir}")
                return
                
            # Add plugin directory to Python path
            plugin_parent = str(plugin_path.parent.absolute())
            if plugin_parent not in sys.path:
                sys.path.append(plugin_parent)
                
            for item in plugin_path.iterdir():
                if item.is_dir() and not item.name.startswith('__'):
                    await self._load_plugin(item)
                    
        except Exception as e:
            logger.error(f"Error loading plugins from {plugin_dir}: {e}")
            
    async def _load_plugin(self, plugin_dir: Path) -> None:
        """Load a single plugin."""
        try:
            # Import the plugin module
            module_name = f"plugins.{plugin_dir.name}"
            spec = importlib.util.spec_from_file_location(
                module_name,
                plugin_dir / "__init__.py"
            )
            if not spec or not spec.loader:
                logger.warning(f"Could not load plugin {plugin_dir.name}")
                return
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find integration classes
            for item_name in dir(module):
                item = getattr(module, item_name)
                if (isinstance(item, type) and 
                    issubclass(item, IntegrationBase) and 
                    item != IntegrationBase):
                    integration_instance = item()
                    self._integrations[integration_instance.get_name()] = item
                    logger.info(f"Loaded plugin integration: {item_name}")
                    
        except Exception as e:
            logger.error(f"Error loading plugin {plugin_dir.name}: {e}")
            
    def get_integration(self, name: str) -> Optional[IntegrationBase]:
        """Get an integration instance by name."""
        name = name.lower()
        if name not in self._loaded_integrations:
            if name not in self._integrations:
                return None
            self._loaded_integrations[name] = self._integrations[name]()
        return self._loaded_integrations[name]
        
    def list_integrations(self) -> List[Dict[str, str]]:
        """List all available integrations."""
        return [
            integration().get_info()
            for integration in self._integrations.values()
        ]
        
    async def cleanup(self) -> None:
        """Clean up integration instances."""
        self._loaded_integrations.clear() 