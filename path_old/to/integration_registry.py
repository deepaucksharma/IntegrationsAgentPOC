import logging
import importlib
import inspect
import pkgutil
from typing import Type, Optional, Dict, List, Tuple, Set, Any
from pathlib import Path

from .base import IntegrationBase

logger = logging.getLogger(__name__)

class IntegrationRegistry:
    """Registry for integration handlers with auto-discovery capability."""
    _integrations: Dict[str, Type[IntegrationBase]] = {}
    _targets_map: Dict[str, List[str]] = {}
    _categories: Dict[str, Set[str]] = {}
    _initialized = False

    @classmethod
    def register(cls, name: str, integration_class: Type[IntegrationBase]) -> None:
        """
        Register an integration class with the registry.
        
        Args:
            name: Name of the integration
            integration_class: Integration class that extends IntegrationBase
        """
        normalized_name = name.lower().replace("integration", "")
        cls._integrations[normalized_name] = integration_class
        
        # Add to category map
        category = integration_class.get_category()
        if category not in cls._categories:
            cls._categories[category] = set()
        cls._categories[category].add(normalized_name)
        
        # Update targets map
        for target in integration_class.get_supported_targets():
            if target not in cls._targets_map:
                cls._targets_map[target] = []
            cls._targets_map[target].append(normalized_name)
        
        logger.debug(f"Registered integration: {normalized_name} in category {category}")

    @classmethod
    def get_integration(cls, name: str) -> Optional[Type[IntegrationBase]]:
        """
        Get an integration class by name.
        
        Args:
            name: Integration name
            
        Returns:
            IntegrationBase subclass or None if not found
        """
        if not cls._initialized:
            cls._discover_integrations()
        
        # Try direct lookup
        normalized = name.lower().replace("integration", "")
        if normalized in cls._integrations:
            return cls._integrations[normalized]
        
        # Try flexible matching - handle underscores, hyphens
        flexible_name = normalized.replace("_", "").replace("-", "")
        for key, value in cls._integrations.items():
            if key.replace("_", "").replace("-", "") == flexible_name:
                return value
        
        return None

    @classmethod
    def get_integrations_for_target(cls, target: str) -> List[str]:
        """
        Get all integration names that support a specific target.
        
        Args:
            target: Target name
            
        Returns:
            List of integration names
        """
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
        """
        Get the best integration for a specific target.
        
        Args:
            target: Target name
            
        Returns:
            Tuple with (integration_name, integration_class) or None if not found
        """
        integrations = cls.get_integrations_for_target(target)
        if not integrations:
            return None
        
        # For now, just return the first one
        # TODO: Implement ranking or scoring to select best integration
        integration_name = integrations[0]
        return integration_name, cls._integrations[integration_name]

    @classmethod
    def get_all_integrations(cls) -> Dict[str, Type[IntegrationBase]]:
        """
        Get all registered integrations.
        
        Returns:
            Dictionary of integration name to integration class
        """
        if not cls._initialized:
            cls._discover_integrations()
        
        return cls._integrations.copy()

    @classmethod
    def get_integrations_by_category(cls, category: str) -> List[str]:
        """
        Get all integration names in a specific category.
        
        Args:
            category: Category name
            
        Returns:
            List of integration names in the category
        """
        if not cls._initialized:
            cls._discover_integrations()
        
        category_lower = category.lower()
        return list(cls._categories.get(category_lower, set()))

    @classmethod
    def has_target(cls, target: str) -> bool:
        """
        Check if a target is supported by any integration.
        
        Args:
            target: Target name
            
        Returns:
            True if target is supported
        """
        return len(cls.get_integrations_for_target(target)) > 0

    @classmethod
    def _discover_integrations(cls) -> None:
        """
        Automatically discover and register all integrations in the package.
        """
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
                                cls.register(name, obj)
                                
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