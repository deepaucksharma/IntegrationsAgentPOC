"""Integration registry for workflow agent."""
import logging
from typing import Any, Dict, List, Optional, Type, Tuple

from .base import IntegrationBase
from .handlers import InfraAgentIntegration

logger = logging.getLogger(__name__)

class IntegrationRegistry:
    """Registry for integration handlers."""
    
    _integrations: Dict[str, Type[IntegrationBase]] = {}
    _targets_map: Dict[str, List[str]] = {}
    
    @classmethod
    def register(cls, integration_class: Type[IntegrationBase]) -> None:
        name = integration_class.get_name()
        cls._integrations[name] = integration_class
        for target in integration_class.get_supported_targets():
            if target not in cls._targets_map:
                cls._targets_map[target] = []
            cls._targets_map[target].append(name)
        logger.debug(f"Registered integration handler: {name}")
    
    @classmethod
    def get_integration(cls, name: str) -> Optional[Type[IntegrationBase]]:
        """Get integration handler by name, normalizing underscores and case."""
        # Normalize by removing underscores and converting to lowercase
        normalized_name = name.lower().replace("_", "")
        
        # Try direct lookup first
        if name.lower() in cls._integrations:
            return cls._integrations[name.lower()]
        
        # Try normalized lookup
        for key, value in cls._integrations.items():
            if key.replace("_", "") == normalized_name:
                return value
        
        return None
    
    @classmethod
    def get_integrations_for_target(cls, target: str) -> List[str]:
        return cls._targets_map.get(target, [])
    
    @classmethod
    def get_best_integration_for_target(cls, target: str) -> Optional[Tuple[str, Type[IntegrationBase]]]:
        integrations = cls.get_integrations_for_target(target)
        if not integrations:
            return None
        integration_name = integrations[0]
        return integration_name, cls._integrations[integration_name]
    
    @classmethod
    def has_target(cls, target: str) -> bool:
        return target in cls._targets_map

IntegrationRegistry.register(InfraAgentIntegration)