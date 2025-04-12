"""
Plugin manager for discovering and loading agent plugins.
"""
import os
import sys
import json
import logging
import importlib.util
from typing import Dict, Any, List, Optional, Set

from .interface import AgentPlugin
from ..error.handler import handle_safely_async
from ..agent.consolidated_base_agent import AgentCapability

logger = logging.getLogger(__name__)

class PluginManager:
    """Manager for discovering and loading agent plugins."""
    
    def __init__(self, plugin_paths: Optional[List[str]] = None):
        """
        Initialize the plugin manager.
        
        Args:
            plugin_paths: Optional list of plugin directories to search
        """
        self.plugin_paths = plugin_paths or self._get_default_plugin_paths()
        self.loaded_plugins = {}
        self.plugin_metadata = {}
        
    def _get_default_plugin_paths(self) -> List[str]:
        """
        Get default plugin paths.
        
        Returns:
            List of default plugin paths
        """
        # Default paths to search for plugins
        default_paths = [
            os.path.join(os.getcwd(), "plugins"),  # ./plugins
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "plugins")  # project_root/plugins
        ]
        
        # Add user plugins directory if it exists
        user_plugins_dir = os.path.expanduser("~/.workflow_agent/plugins")
        if os.path.exists(user_plugins_dir):
            default_paths.append(user_plugins_dir)
            
        return default_paths
    
    @handle_safely_async
    async def discover_plugins(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover available plugins and their metadata.
        
        Returns:
            Dictionary of plugin IDs to metadata
        """
        discovered = {}
        
        for path in self.plugin_paths:
            if not os.path.exists(path):
                logger.debug(f"Plugin path does not exist: {path}")
                continue
                
            logger.info(f"Searching for plugins in: {path}")
            for item in os.listdir(path):
                # Check for plugin directories with manifest.json
                plugin_dir = os.path.join(path, item)
                manifest_path = os.path.join(plugin_dir, "manifest.json")
                
                if os.path.isdir(plugin_dir) and os.path.exists(manifest_path):
                    try:
                        # Load manifest
                        with open(manifest_path, "r") as f:
                            manifest = json.load(f)
                            
                        # Validate manifest
                        if self._validate_manifest(manifest):
                            plugin_id = manifest.get("id", item)
                            discovered[plugin_id] = manifest
                            logger.info(f"Discovered plugin: {plugin_id} ({manifest.get('name')})")
                        else:
                            logger.warning(f"Invalid plugin manifest: {manifest_path}")
                    except Exception as e:
                        logger.error(f"Error loading plugin manifest {manifest_path}: {e}")
                        
        self.plugin_metadata = discovered
        return discovered
        
    def _validate_manifest(self, manifest: Dict[str, Any]) -> bool:
        """
        Validate a plugin manifest.
        
        Args:
            manifest: Plugin manifest dictionary
            
        Returns:
            True if manifest is valid
        """
        required_fields = ["id", "name", "version", "entry_point"]
        return all(field in manifest for field in required_fields)
        
    @handle_safely_async
    async def load_plugin(self, plugin_id: str) -> Optional[AgentPlugin]:
        """
        Load a plugin by ID.
        
        Args:
            plugin_id: Plugin ID to load
            
        Returns:
            Plugin instance or None if plugin could not be loaded
        """
        # Return cached plugin if already loaded
        if plugin_id in self.loaded_plugins:
            logger.debug(f"Returning cached plugin: {plugin_id}")
            return self.loaded_plugins[plugin_id]
            
        # Check if plugin metadata exists
        if plugin_id not in self.plugin_metadata:
            logger.error(f"Plugin metadata not found for: {plugin_id}")
            
            # Try to discover plugins if metadata is not found
            await self.discover_plugins()
            
            if plugin_id not in self.plugin_metadata:
                logger.error(f"Plugin {plugin_id} not found after discovery")
                return None
            
        manifest = self.plugin_metadata[plugin_id]
        logger.info(f"Loading plugin: {plugin_id} ({manifest.get('name')})")
        
        # Find plugin directory
        for path in self.plugin_paths:
            plugin_dir = os.path.join(path, plugin_id)
            if os.path.exists(plugin_dir):
                break
        else:
            logger.error(f"Plugin directory for {plugin_id} not found")
            return None
            
        # Import entry point
        entry_point = manifest["entry_point"]
        module_path = os.path.join(plugin_dir, f"{entry_point}.py")
        
        try:
            # Import plugin module
            logger.debug(f"Importing plugin module: {module_path}")
            spec = importlib.util.spec_from_file_location(entry_point, module_path)
            if not spec or not spec.loader:
                logger.error(f"Failed to create module spec for {module_path}")
                return None
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[entry_point] = module
            spec.loader.exec_module(module)
            
            # Get plugin class
            class_name = manifest.get("class_name", "Plugin")
            if not hasattr(module, class_name):
                logger.error(f"Plugin class {class_name} not found in {module_path}")
                return None
                
            plugin_class = getattr(module, class_name)
            
            # Check version compatibility
            if not self._check_version_compatibility(manifest["version"]):
                logger.warning(f"Plugin {plugin_id} version {manifest['version']} may not be compatible")
                
            # Instantiate plugin
            plugin = plugin_class()
            
            # Check if plugin implements the required interface
            if not isinstance(plugin, AgentPlugin):
                logger.error(f"Plugin {plugin_id} does not implement AgentPlugin interface")
                return None
                
            # Cache and return plugin
            self.loaded_plugins[plugin_id] = plugin
            logger.info(f"Successfully loaded plugin: {plugin_id}")
            
            return plugin
            
        except Exception as e:
            logger.error(f"Error loading plugin {plugin_id}: {e}")
            return None
            
    def _check_version_compatibility(self, plugin_version: str) -> bool:
        """
        Check if plugin version is compatible with framework version.
        
        Args:
            plugin_version: Plugin version string
            
        Returns:
            True if plugin version is compatible
        """
        # TODO: Implement proper version compatibility checking
        return True
    
    @handle_safely_async
    async def get_agent_instance(self, plugin_id: str) -> Optional[Any]:
        """
        Get an agent instance from a plugin.
        
        Args:
            plugin_id: Plugin ID
            
        Returns:
            Agent instance or None if plugin could not be loaded
        """
        plugin = await self.load_plugin(plugin_id)
        if not plugin:
            return None
            
        try:
            # Get agent instance from plugin
            return await plugin.get_agent_instance()
        except Exception as e:
            logger.error(f"Error getting agent instance from plugin {plugin_id}: {e}")
            return None
    
    @handle_safely_async
    async def get_plugin_capabilities(self, plugin_id: str) -> Set[AgentCapability]:
        """
        Get the capabilities provided by a plugin.
        
        Args:
            plugin_id: Plugin ID
            
        Returns:
            Set of agent capabilities
        """
        plugin = await self.load_plugin(plugin_id)
        if not plugin:
            return set()
            
        try:
            # Get capabilities from plugin
            return plugin.get_capabilities()
        except Exception as e:
            logger.error(f"Error getting capabilities from plugin {plugin_id}: {e}")
            return set()
