"""Interface definitions for plugins and agent components."""
import abc
from typing import Any, Dict, List, Optional

class PluginInterface(abc.ABC):
    """Interface for plugins to extend agent functionality."""
    
    @abc.abstractmethod
    def get_name(self) -> str:
        """Return the plugin name."""
        pass
    
    @abc.abstractmethod
    def get_version(self) -> str:
        """Return the plugin version."""
        pass
    
    @abc.abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data according to plugin functionality.
        
        Args:
            input_data: Data to be processed
            
        Returns:
            Processing results
        """
        pass

class BaseAgent(abc.ABC):
    """Abstract Base Agent class for workflow orchestration."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abc.abstractmethod
    async def invoke(self, input_state: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute the agent's main functionality.
        
        Args:
            input_state: The initial state data
            config: Optional configuration parameters
            
        Returns:
            Updated state after processing
        """
        pass

    @abc.abstractmethod
    async def initialize(self, config: Dict[str, Any] = None) -> None:
        """
        Initialize agent resources and connections.
        
        Args:
            config: Optional configuration parameters
        """
        pass

    @abc.abstractmethod
    async def cleanup(self) -> None:
        """Release any resources held by the agent."""
        pass
    
    @abc.abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        Return a list of the agent's capabilities.
        
        Returns:
            List of capability strings
        """
        pass

# Simple types for agent state and result.
AgentState = Dict[str, Any]
AgentResult = Dict[str, Any]