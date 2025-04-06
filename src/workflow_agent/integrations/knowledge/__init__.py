"""Knowledge integration package."""
from .knowledge_integration import KnowledgeIntegration

def get_integrations():
    """Return all integrations in this package."""
    return [KnowledgeIntegration]

__all__ = ['KnowledgeIntegration', 'get_integrations']
