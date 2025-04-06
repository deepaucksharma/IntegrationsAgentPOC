"""Rollback integration package."""
from .rollback_integration import RollbackIntegration

def get_integrations():
    """Return all integrations in this package."""
    return [RollbackIntegration]

__all__ = ['RollbackIntegration', 'get_integrations']
