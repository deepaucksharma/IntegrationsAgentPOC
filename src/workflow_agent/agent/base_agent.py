"""
Base agent implementation for all specialized workflow agents.
"""
import logging
import asyncio
import time
from typing import Dict, Any, Optional, List, Set, Union, TypeVar, Generic
from abc import ABC, abstractmethod
from enum import Enum, auto
from dataclasses import dataclass, field
import uuid

from ..core.state import WorkflowState, WorkflowStatus
from ..error.handler import ErrorHandler, handle_safely_async
from ..error.exceptions import AgentError

logger = logging.getLogger(__name__)

class AgentCapability(str, Enum):
    """Capabilities that an agent can provide."""
    SCRIPT_GENERATION = "script_generation"
    VERIFICATION = "verification"
    ERROR_ANALYSIS = "error_analysis"
    DECISION_MAKING = "decision_making"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    INTEGRATION_SPECIFIC = "integration_specific"
    PLANNING = "planning"
    EXECUTION = "execution"
    RECOVERY = "recovery"
    DOCUMENTATION = "documentation"

@dataclass
class AgentConfig:
    """Configuration options for an agent."""
    timeout_seconds: float = 60.0
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    extra_options: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentContext:
    """Context for agent execution."""
    workflow_state: WorkflowState
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: float = field(default_factory=time.time)
    parameters: Dict[str, Any] = field(default_factory=dict)
    shared_context: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    interaction_count: int = 0
    
    def add_to_history(self, action: str, details: Any) -> None:
        """Add an entry to the agent interaction history."""
        self.history.append({
            "timestamp": time.time(),
            "action": action,
            "details": details
        })
        self.interaction_count += 1

@dataclass
class AgentResult:
    """Result of an agent operation."""
    success: bool
    workflow_state: WorkflowState
    output: Optional[Any] = None
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success_result(cls, workflow_state: WorkflowState, output: Any = None, 
                      metadata: Optional[Dict[str, Any]] = None) -> 'AgentResult':
        """Create a success result."""
        return cls(
            success=True,
            workflow_state=workflow_state,
            output=output,
            error_message=None,
            metadata=metadata or {}
        )
    
    @classmethod
    def error_result(cls, workflow_state: WorkflowState, error_message: str,
                    metadata: Optional[Dict[str, Any]] = None) -> 'AgentResult':
        """Create an error result."""
        error_state = workflow_state.set_error(error_message)
        return cls(
            success=False,
            workflow_state=error_state,
            output=None,
            error_message=error_message,
            metadata=metadata or {}
        )

class BaseAgent(ABC):
    """
    Base agent class for all specialized workflow agents.
    Provides common functionality and standardized interfaces.
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the agent with optional configuration.
        
        Args:
            config: Agent configuration options
        """
        self.config = config or AgentConfig()
        self.capabilities: Set[AgentCapability] = set()
        self._register_capabilities()
        
    @abstractmethod
    def _register_capabilities(self) -> None:
        """
        Register agent capabilities.
        This method should be implemented by subclasses.
        """
        pass
    
    def has_capability(self, capability: AgentCapability) -> bool:
        """
        Check if the agent has a specific capability.
        
        Args:
            capability: Capability to check
            
        Returns:
            True if agent has the capability
        """
        return capability in self.capabilities
    
    @handle_safely_async
    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Execute the agent's main functionality with the given context.
        
        Args:
            context: Agent execution context
            
        Returns:
            Agent result
        """
        start_time = time.time()
        
        try:
            # Record the start of execution
            context.add_to_history("execute", {
                "agent_type": self.__class__.__name__
            })
            
            # Execute agent-specific logic
            result = await self._execute_agent_logic(context)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Update result with duration
            result = AgentResult(
                success=result.success,
                workflow_state=result.workflow_state,
                output=result.output,
                error_message=result.error_message,
                duration_seconds=duration,
                metadata=result.metadata
            )
            
            # Log outcome
            if result.success:
                logger.info(f"{self.__class__.__name__} executed successfully in {duration:.2f}s")
            else:
                logger.error(f"{self.__class__.__name__} failed in {duration:.2f}s: {result.error_message}")
                
            return result
            
        except Exception as e:
            # Handle unexpected errors
            duration = time.time() - start_time
            error_msg = f"Agent execution error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Return error result
            return AgentResult.error_result(
                workflow_state=context.workflow_state,
                error_message=error_msg,
                metadata={
                    "exception_type": type(e).__name__,
                    "duration_seconds": duration
                }
            )
    
    @abstractmethod
    async def _execute_agent_logic(self, context: AgentContext) -> AgentResult:
        """
        Execute agent-specific logic.
        This method should be implemented by subclasses.
        
        Args:
            context: Agent execution context
            
        Returns:
            Agent result
        """
        pass
    
    @handle_safely_async
    async def initialize(self) -> None:
        """
        Initialize the agent.
        Called when the agent is first used.
        """
        logger.debug(f"Initialized {self.__class__.__name__}")
    
    @handle_safely_async
    async def cleanup(self) -> None:
        """
        Clean up resources used by the agent.
        Called when the agent is no longer needed.
        """
        logger.debug(f"Cleaned up {self.__class__.__name__}")
    
    async def validate_context(self, context: AgentContext) -> bool:
        """
        Validate the context before execution.
        
        Args:
            context: Agent execution context
            
        Returns:
            True if context is valid
            
        Raises:
            AgentError: If context is invalid
        """
        # Ensure workflow state is present
        if not context.workflow_state:
            raise AgentError("Workflow state is required in agent context")
            
        # Perform additional validation
        return await self._validate_agent_context(context)
    
    async def _validate_agent_context(self, context: AgentContext) -> bool:
        """
        Validate agent-specific context requirements.
        Can be overridden by subclasses.
        
        Args:
            context: Agent execution context
            
        Returns:
            True if context is valid
        """
        return True
    
    @handle_safely_async
    async def execute_with_retry(self, context: AgentContext) -> AgentResult:
        """
        Execute the agent with automatic retries.
        
        Args:
            context: Agent execution context
            
        Returns:
            Agent result
        """
        retry_count = 0
        last_error = None
        
        while retry_count <= self.config.max_retries:
            if retry_count > 0:
                # This is a retry attempt
                logger.info(f"Retry attempt {retry_count} for {self.__class__.__name__}")
                
                # Wait before retrying
                await asyncio.sleep(self.config.retry_delay_seconds * (2 ** (retry_count - 1)))
                
                # Record retry in history
                context.add_to_history("retry", {
                    "attempt": retry_count,
                    "previous_error": str(last_error)
                })
            
            # Attempt execution
            result = await self.execute(context)
            
            if result.success:
                # Success, return result
                if retry_count > 0:
                    # Add retry information to result
                    result.metadata["retry_count"] = retry_count
                    result.metadata["retry_success"] = True
                return result
            
            # Execution failed, check if error is retriable
            error = result.error_message
            last_error = error
            retry_count += 1
            
            if not self._is_retriable_error(error) or retry_count > self.config.max_retries:
                # Error is not retriable or max retries reached
                if retry_count > 1:
                    # Add retry information to result
                    result.metadata["retry_count"] = retry_count - 1
                    result.metadata["retry_success"] = False
                return result
        
        # This code should not be reached, but just in case
        return AgentResult.error_result(
            workflow_state=context.workflow_state,
            error_message=f"Max retries exceeded: {last_error}",
            metadata={"retry_count": retry_count}
        )
    
    def _is_retriable_error(self, error_message: str) -> bool:
        """
        Check if an error is retriable.
        
        Args:
            error_message: Error message
            
        Returns:
            True if error is retriable
        """
        # Check for common retriable error patterns
        retriable_patterns = [
            "timeout",
            "connection refused",
            "network error",
            "temporary failure",
            "retry",
            "try again",
            "429", # Too Many Requests
            "503", # Service Unavailable
        ]
        
        return any(pattern in error_message.lower() for pattern in retriable_patterns)
