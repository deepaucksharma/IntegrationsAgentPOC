import abc
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

@dataclass
class AgentConfig:
    """Base configuration for all agents."""
    name: str
    description: str
    max_concurrent_tasks: int = 5
    use_isolation: bool = True
    isolation_method: str = "docker"
    execution_timeout: int = 300

class AbstractWorkflowAgent(abc.ABC):
    """Abstract base class for all workflow agents in the system."""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.name = config.name
        self.description = config.description

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

    def get_config_schema(self) -> Dict[str, Any]:
        """
        Get the configuration schema for the agent.
        
        Returns:
            Dictionary describing the configuration schema
        """
        return {
            "name": "string",
            "description": "string",
            "max_concurrent_tasks": "number",
            "use_isolation": "boolean",
            "isolation_method": "string",
            "execution_timeout": "number"
        }

# Simple types for agent state and result.
AgentState = Dict[str, Any]
AgentResult = Dict[str, Any]