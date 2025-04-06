"""
Integration components for workflow agent.
"""
from .base import IntegrationBase
from .infra_agent import InfraAgentIntegration
from .custom import CustomIntegration
from .registry import IntegrationRegistry

# Register integrations
registry = IntegrationRegistry()
registry.register(InfraAgentIntegration)
registry.register(CustomIntegration)

__all__ = [
    'IntegrationBase',
    'InfraAgentIntegration',
    'CustomIntegration',
    'IntegrationRegistry'
]