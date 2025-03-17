# src/workflow_agent/integrations/registry.py
import logging
import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
from .base import IntegrationBase
from ..core.state import WorkflowState
from ..config.configuration import ensure_workflow_config
from ..utils.system import get_system_context

logger = logging.getLogger(__name__)

class IntegrationRegistry:
    """Registry for integration handlers."""
    
    _integrations: Dict[str, Type[IntegrationBase]] = {}
    
    @classmethod
    def register(cls, integration_class: Type[IntegrationBase]) -> None:
        """
        Register an integration handler.
        
        Args:
            integration_class: Class that implements IntegrationBase
        """
        name = integration_class.get_name()
        cls._integrations[name] = integration_class
        logger.debug(f"Registered integration handler: {name}")
    
    @classmethod
    def get_integration(cls, name: str) -> Optional[Type[IntegrationBase]]:
        """
        Get integration handler by name.
        
        Args:
            name: Name of the integration
            
        Returns:
            Integration class or None if not found
        """
        return cls._integrations.get(name.lower())
    
    @classmethod
    def list_integrations(cls) -> List[str]:
        """
        Get list of available integrations.
        
        Returns:
            List of integration names
        """
        return list(cls._integrations.keys())
    
    @classmethod
    def discover_integrations(cls, package_path: str = None) -> None:
        """
        Discover and register integration handlers from a package.
        
        Args:
            package_path: Path to package containing integration modules
        """
        if package_path:
            logger.info(f"Discovering integrations in {package_path}")
            try:
                # Load from path
                for finder, name, is_pkg in pkgutil.iter_modules([package_path]):
                    try:
                        module = importlib.import_module(f"{package_path}.{name}")
                        for item_name in dir(module):
                            item = getattr(module, item_name)
                            if (inspect.isclass(item) and 
                                issubclass(item, IntegrationBase) and 
                                item is not IntegrationBase):
                                cls.register(item)
                    except Exception as e:
                        logger.error(f"Error loading integration module {name}: {e}")
            except Exception as e:
                logger.error(f"Error discovering integrations in {package_path}: {e}")

class IntegrationHandler:
    """Main handler for all integrations."""
    
    def __init__(self):
        """Initialize the integration handler."""
        # Import handlers here to avoid circular imports
        from .handlers.infra_agent import InfraAgentIntegration
        from .handlers.aws import AwsIntegration
        
        # Register built-in integrations
        IntegrationRegistry.register(InfraAgentIntegration)
        IntegrationRegistry.register(AwsIntegration)
        
        # Discover external integrations
        config = ensure_workflow_config()
        for plugin_dir in config.plugin_dirs:
            IntegrationRegistry.discover_integrations(plugin_dir)
    
    async def handle_integration(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle integration request based on integration type.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with updates to workflow state
        """
        integration_type = state.integration_type.lower()
        
        # Get integration handler
        integration_class = IntegrationRegistry.get_integration(integration_type)
        if not integration_class:
            logger.warning(f"No integration handler found for {integration_type}, using fallback")
            return {
                "script": f"""#!/usr/bin/env bash
set -e
echo "Handling generic integration for {state.target_name} using {state.integration_type}"
""",
                "source": "fallback_handler"
            }
        
        try:
            integration = integration_class()
            result = await integration.handle(state, config)
            
            # Add default system context if not provided
            if "system_context" not in result:
                result["system_context"] = get_system_context()
                
            return result
        except Exception as e:
            logger.error(f"Error handling {integration_type} integration: {e}")
            return {"error": f"Integration handler error: {str(e)}"}
    
    async def handle_infra_agent(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Specialized handler for infra agent integrations.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with updates to workflow state
        """
        # This is a convenience method that delegates to the InfraAgentIntegration
        state.integration_type = "infra_agent"
        integration_class = IntegrationRegistry.get_integration("infra_agent")
        if not integration_class:
            logger.error("InfraAgentIntegration not registered")
            return {"error": "InfraAgentIntegration not available"}
        
        integration = integration_class()
        return await integration.handle(state, config)