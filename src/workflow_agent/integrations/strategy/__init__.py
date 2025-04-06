"""Strategy integration package."""
from .strategy_integration import StrategyIntegration

def get_integrations():
    """Return all integrations in this package."""
    return [StrategyIntegration]

__all__ = ['StrategyIntegration', 'get_integrations']
