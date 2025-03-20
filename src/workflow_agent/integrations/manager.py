"""
Integration manager for handling plugin loading and management.
"""
import logging
import importlib
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Type

from .base import BaseIntegration

logger = logging.getLogger(__name__)

class IntegrationManager:
    """Manages integration plugins."""
    
    def __init__(self, plugin_dirs: List[str]):
        self.plugin_dirs = plugin_dirs
        self._integrations: Dict[str, Type[BaseIntegration]] = {}
        self._loaded_integrations: Dict[str, BaseIntegration] = {}
        
    async def initialize(self) -> None:
        """Initialize the integration manager."""
        logger.info("Initializing integration manager...")
        for plugin_dir in self.plugin_dirs:
            await self._load_plugins_from_dir(plugin_dir)
        logger.info(f"Loaded {len(self._integrations)} integration types")
        
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
                    issubclass(item, BaseIntegration) and 
                    item != BaseIntegration):
                    integration_instance = item()
                    self._integrations[integration_instance.name] = item
                    logger.info(f"Loaded integration: {item_name} (name: {integration_instance.name})")
                    
        except Exception as e:
            logger.error(f"Error loading plugin {plugin_dir.name}: {e}")
            
    def get_integration(self, name: str) -> Optional[BaseIntegration]:
        """Get an integration instance by name."""
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