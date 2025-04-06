"""Multi-agent integration package."""
from .multi_agent_integration import MultiAgentIntegration

def get_integrations():
    """Return all integrations in this package."""
    return [MultiAgentIntegration]

__all__ = ['MultiAgentIntegration', 'get_integrations']
