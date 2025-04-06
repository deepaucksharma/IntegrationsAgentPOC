"""
Integration components for workflow agent.
"""
from .base import IntegrationBase
from .registry import IntegrationRegistry
from .manager import IntegrationManager

# Import integration packages
from . import infra_agent
from . import custom
from . import knowledge
from . import multi_agent
from . import rollback
from . import strategy

# Get all available integrations for use in the registry
def get_all_integrations():
    """Get all available integrations."""
    all_integrations = []
    
    # Add integrations from each package
    for package in [infra_agent, custom, knowledge, multi_agent, rollback, strategy]:
        if hasattr(package, 'get_integrations'):
            all_integrations.extend(package.get_integrations())
    
    return all_integrations

__all__ = [
    'IntegrationBase',
    'IntegrationRegistry',
    'IntegrationManager',
    'get_all_integrations',
]
