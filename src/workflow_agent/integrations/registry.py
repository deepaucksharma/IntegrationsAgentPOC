"""
Integration registry for workflow agent.
"""
import logging
import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Type, Optional, Dict, List, Tuple, Set

from .base import IntegrationBase

logger = logging.getLogger(__name__)

class IntegrationRegistry:
    """Registry for managing integration plugins."""
    
    _instance = None
    _integrations: Dict[str, Type[IntegrationBase]] = {}

    def __new__(cls):
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, integration_class: Type[IntegrationBase]) -> None:
        """Register an integration class."""
        name = integration_class.__name__.lower()
        if name in cls._integrations:
            logger.warning(f"Integration {name} already registered. Overwriting.")
        cls._integrations[name] = integration_class
        logger.info(f"Registered integration: {name}")

    @classmethod
    def get_integration(cls, name: str) -> Optional[Type[IntegrationBase]]:
        """Get an integration class by name."""
        return cls._integrations.get(name.lower())

    @classmethod
    def list_integrations(cls) -> Dict[str, Type[IntegrationBase]]:
        """List all registered integrations."""
        return cls._integrations.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear all registered integrations."""
        cls._integrations.clear()
        logger.info("Cleared all registered integrations")

    @classmethod
    def get_integrations_for_target(cls, target: str) -> List[str]:
        """Get all integration names that support a specific target."""
        if not cls._initialized:
            cls._discover_integrations()
        
        # Try exact match first
        target_lower = target.lower()
        if target_lower in cls._targets_map:
            return cls._targets_map[target_lower]
        
        # Try flexible matching
        flexible_target = target_lower.replace("_", "").replace("-", "")
        for key, integrations in cls._targets_map.items():
            if key.replace("_", "").replace("-", "") == flexible_target:
                return integrations
        
        return []

    @classmethod
    def get_best_integration_for_target(cls, target: str) -> Optional[Tuple[str, Type[IntegrationBase]]]:
        """Get the best integration for a specific target."""
        integrations = cls.get_integrations_for_target(target)
        if not integrations:
            return None
        
        # For now, just return the first one
        # TODO: Implement ranking or scoring to select best integration
        integration_name = integrations[0]
        return integration_name, cls._integrations[integration_name]

    @classmethod
    def get_all_integrations(cls) -> Dict[str, Type[IntegrationBase]]:
        """Get all registered integrations."""
        if not cls._initialized:
            cls._discover_integrations()
        
        return cls._integrations.copy()

    @classmethod
    def get_integrations_by_category(cls, category: str) -> List[str]:
        """Get all integration names in a specific category."""
        if not cls._initialized:
            cls._discover_integrations()
        
        category_lower = category.lower()
        return list(cls._categories.get(category_lower, set()))

    @classmethod
    def has_target(cls, target: str) -> bool:
        """Check if a target is supported by any integration."""
        return len(cls.get_integrations_for_target(target)) > 0

    @classmethod
    def _discover_integrations(cls) -> None:
        """Automatically discover and register all integrations in the package."""
        if cls._initialized:
            return
            
        # Register base integration
        if "integrationbase" not in cls._integrations:
            cls.register("IntegrationBase", IntegrationBase)
        
        try:
            # Get package path
            current_module = __import__(__name__)
            package_path = Path(current_module.__file__).parent
            
            # Dynamically import and register all modules in the package
            for _, module_name, is_pkg in pkgutil.iter_modules([str(package_path)]):
                if is_pkg and module_name != "__pycache__":
                    try:
                        module = importlib.import_module(f"{__package__}.{module_name}")
                        
                        # Look for IntegrationBase subclasses in the module
                        for name, obj in inspect.getmembers(module):
                            if (inspect.isclass(obj) and 
                                issubclass(obj, IntegrationBase) and 
                                obj is not IntegrationBase):
                                cls.register(obj)
                                
                    except Exception as e:
                        logger.warning(f"Failed to load integration module {module_name}: {e}")
        
        except Exception as e:
            logger.error(f"Error during integration discovery: {e}")
            
        # Mark as initialized
        cls._initialized = True
        logger.info(f"Discovered {len(cls._integrations)} integrations")

# Register base class
IntegrationRegistry.register("IntegrationBase", IntegrationBase)

# Auto-discover integrations on import
IntegrationRegistry._discover_integrations()