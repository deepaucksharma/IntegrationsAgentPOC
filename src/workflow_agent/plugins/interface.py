"""
Base interface for agent plugins.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set

from ..multi_agent.base import MultiAgentBase
from ..agent.consolidated_base_agent import AgentCapability

logger = logging.getLogger(__name__)

class AgentPlugin(ABC):
    """Base interface for agent plugins."""
    
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get plugin metadata.
        
        Returns:
            Dictionary with plugin metadata
        """
        pass
        
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initialize the plugin with configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            True if initialization was successful
        """
        pass
        
    @abstractmethod
    async def get_agent_instance(self) -> MultiAgentBase:
        """
        Get an instance of the agent implemented by this plugin.
        
        Returns:
            Agent instance
        """
        pass
        
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up plugin resources."""
        pass
        
    @abstractmethod
    def get_capabilities(self) -> Set[AgentCapability]:
        """
        Get the capabilities provided by this plugin.
        
        Returns:
            Set of agent capabilities
        """
        pass
