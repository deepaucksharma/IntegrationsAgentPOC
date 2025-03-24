"""
Strategy agent module.
"""
from typing import Dict, Any, Optional

class InstallationStrategyAgent:
    """Agent for managing installation strategies."""
    
    def __init__(self):
        """Initialize the strategy agent."""
        self.strategies = {}
        
    def add_strategy(self, name: str, strategy: Dict[str, Any]) -> None:
        """Add a new strategy."""
        self.strategies[name] = strategy
        
    def get_strategy(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a strategy by name."""
        return self.strategies.get(name)
        
    def list_strategies(self) -> list[str]:
        """List all available strategies."""
        return list(self.strategies.keys())
        
    def remove_strategy(self, name: str) -> None:
        """Remove a strategy."""
        if name in self.strategies:
            del self.strategies[name]
            
    def clear_strategies(self) -> None:
        """Clear all strategies."""
        self.strategies.clear() 