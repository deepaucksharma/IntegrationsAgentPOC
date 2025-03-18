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
            target_norm = target.replace("_", "").lower()
            if target_norm not in cls._targets_map:
                cls._targets_map[target_norm] = []
            cls._targets_map[target_norm].append(name)
        logger.debug(f"Registered integration handler: {name}")
    
    @classmethod
    def get_integration(cls, name: str) -> Optional[Type[IntegrationBase]]:
        return cls._integrations.get(name.replace("_", "").lower())
    
    @classmethod
    def get_integrations_for_target(cls, target: str) -> List[str]:
        return cls._targets_map.get(target.replace("_", "").lower(), [])
    
    @classmethod
    def get_best_integration_for_target(cls, target: str) -> Optional[Tuple[str, Type[IntegrationBase]]]:
        integrations = cls.get_integrations_for_target(target)
        if not integrations:
            return None
        integration_name = integrations[0]
        return integration_name, cls._integrations[integration_name]
    
    @classmethod
    def has_target(cls, target: str) -> bool:
        return target.replace("_", "").lower() in cls._targets_map

IntegrationRegistry.register(InfraAgentIntegration)