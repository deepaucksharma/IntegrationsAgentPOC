"""
Integration registry for workflow agent.
"""
import logging
from typing import Type, Optional, Dict, List, Tuple
from .base import IntegrationBase

logger = logging.getLogger(__name__)

class IntegrationRegistry:
    """Registry for integration handlers with auto-discovery capability."""
    _integrations: Dict[str, Type[IntegrationBase]] = {}
    _targets_map: Dict[str, List[str]] = {}
    _initialized = False

    @classmethod
    def register(cls, name: str, integration_class: Type[IntegrationBase]) -> None:
        cls._integrations[name.lower()] = integration_class
        for target in integration_class.get_supported_targets():
            if target not in cls._targets_map:
                cls._targets_map[target] = []
            cls._targets_map[target].append(name.lower())
        logger.debug(f"Registered integration: {name}")

    @classmethod
    def get_integration(cls, name: str) -> Optional[Type[IntegrationBase]]:
        if not cls._initialized:
            cls._discover_integrations()
        if name.lower() in cls._integrations:
            return cls._integrations[name.lower()]
        normalized = name.lower().replace("_", "").replace("-", "")
        for key, value in cls._integrations.items():
            if key.replace("_", "").replace("-", "") == normalized:
                return value
        return None

    @classmethod
    def get_integrations_for_target(cls, target: str) -> List[str]:
        if not cls._initialized:
            cls._discover_integrations()
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

    @classmethod
    def _discover_integrations(cls) -> None:
        if cls._initialized:
            return
        if "integrationbase" not in cls._integrations:
            cls.register("IntegrationBase", IntegrationBase)
        cls._initialized = True

IntegrationRegistry.register("IntegrationBase", IntegrationBase)