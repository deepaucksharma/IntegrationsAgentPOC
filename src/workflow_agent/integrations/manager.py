"""
Integration manager for handling integration lifecycle.
"""
import logging
from typing import Dict, Any, Optional, List

from .base import IntegrationBase
from .registry import IntegrationRegistry
from ..error.exceptions import IntegrationError
from ..config.configuration import WorkflowConfiguration
from ..templates.manager import TemplateManager

logger = logging.getLogger(__name__)

class IntegrationManager:
    """Manages integration operations and lifecycle."""
    
    def __init__(self, config: WorkflowConfiguration, registry: Optional[IntegrationRegistry] = None):
        """
        Initialize with configuration.
        
        Args:
            config: Workflow configuration
            registry: Optional integration registry (will create if not provided)
        """
        self.config = config
        self.registry = registry or IntegrationRegistry()
        self.template_manager = TemplateManager(config)
        
        # Discover plugins if plugin dirs specified
        if config.plugin_dirs:
            self.registry.discover_plugins(config.plugin_dirs)
            
        # Discover built-in integrations
        self._discover_built_in_integrations()
        
    def _discover_built_in_integrations(self) -> None:
        """Discover and register built-in integrations."""
        from . import infra_agent, custom
        
        modules = [infra_agent, custom]
        for module in modules:
            # Attempt to get the module's integrations
            if hasattr(module, 'get_integrations'):
                try:
                    for integration_class in module.get_integrations():
                        self.registry.register(integration_class)
                except Exception as e:
                    logger.error(f"Error loading integrations from {module.__name__}: {e}")
    
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
            logger.error(f"Integration not found: {integration_type}")
            available = list(self.registry.list_integrations().keys())
            logger.info(f"Available integrations: {available}")
            
        return integration
        
    def list_integrations(self) -> Dict[str, Dict[str, Any]]:
        """
        List all available integrations.
        
        Returns:
            Dictionary of integration information
        """
        return self.registry.list_integrations()
        
    def get_template_for_integration(
        self, 
        integration_type: str, 
        action: str, 
        target: str
    ) -> Optional[str]:
        """
        Get a template for an integration action.
        
        Args:
            integration_type: Type of integration
            action: Action (install, verify, uninstall, etc.)
            target: Target identifier
            
        Returns:
            Template key or None if not found
        """
        # Try specific template first
        template_key = f"{action}/{integration_type}/{target}"
        if self.template_manager.get_template(template_key):
            return template_key
            
        # Try integration-wide template
        template_key = f"{action}/{integration_type}/default"
        if self.template_manager.get_template(template_key):
            return template_key
            
        # Try action-wide template
        template_key = f"{action}/default"
        if self.template_manager.get_template(template_key):
            return template_key
            
        logger.warning(f"No template found for {integration_type}/{action}/{target}")
        return None
