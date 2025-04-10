"""
Base classes and interfaces for the multi-agent system.
Provides common functionality and standardized communication patterns.
"""
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Set, Union
from datetime import datetime
import uuid

from ..core.state import WorkflowState
from ..agent.consolidated_base_agent import BaseAgent, AgentResult, AgentContext
from ..error.exceptions import AgentError, MultiAgentError

logger = logging.getLogger(__name__)

class MessageType:
    """Standard message types for inter-agent communication."""
    KNOWLEDGE_REQUEST = "knowledge_request"
    KNOWLEDGE_RESPONSE = "knowledge_response"
    EXECUTION_REQUEST = "execution_request"
    EXECUTION_RESPONSE = "execution_response"
    VERIFICATION_REQUEST = "verification_request"
    VERIFICATION_RESPONSE = "verification_response"
    STATUS_UPDATE = "status_update"
    ERROR_REPORT = "error_report"
    IMPROVEMENT_SUGGESTION = "improvement_suggestion"
    COORDINATION_COMMAND = "coordination_command"

class MessagePriority:
    """Priority levels for messages."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class MultiAgentMessage:
    """
    Standardized message format for inter-agent communication.
    All agent communication should use this format for consistency.
    """
    
    def __init__(
        self, 
        sender: str, 
        message_type: str, 
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        priority: str = MessagePriority.MEDIUM,
        message_id: Optional[str] = None,
        in_response_to: Optional[str] = None
    ):
        """
        Initialize a new message.
        
        Args:
            sender: ID of the sending agent
            message_type: Type of message (see MessageType constants)
            content: Message content (can be any serializable object)
            metadata: Additional message metadata
            priority: Message priority (high, medium, low)
            message_id: Unique message ID (generated if not provided)
            in_response_to: ID of message this is responding to (if applicable)
        """
        self.sender = sender
        self.message_type = message_type
        self.content = content
        self.metadata = metadata or {}
        self.priority = priority
        self.message_id = message_id or str(uuid.uuid4())
        self.in_response_to = in_response_to
        self.timestamp = datetime.now()
        self.processed = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary representation for serialization."""
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "message_type": self.message_type,
            "content": self.content,
            "metadata": self.metadata,
            "priority": self.priority,
            "in_response_to": self.in_response_to,
            "timestamp": self.timestamp.isoformat(),
            "processed": self.processed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MultiAgentMessage':
        """Create a message from a dictionary representation."""
        if not isinstance(data, dict):
            raise ValueError(f"Expected dictionary, got {type(data)}")
            
        # Extract required fields with validation
        try:
            sender = data["sender"]
            message_type = data["message_type"]
            content = data["content"]
        except KeyError as e:
            raise ValueError(f"Missing required field: {e}")
        
        # Create message with optional fields
        message = cls(
            sender=sender,
            message_type=message_type,
            content=content,
            metadata=data.get("metadata"),
            priority=data.get("priority", MessagePriority.MEDIUM),
            message_id=data.get("message_id"),
            in_response_to=data.get("in_response_to")
        )
        
        # Set additional fields if present
        if "timestamp" in data:
            try:
                if isinstance(data["timestamp"], str):
                    message.timestamp = datetime.fromisoformat(data["timestamp"])
                elif isinstance(data["timestamp"], datetime):
                    message.timestamp = data["timestamp"]
            except (ValueError, TypeError):
                pass  # Keep the default timestamp if parsing fails
                
        if "processed" in data:
            message.processed = bool(data["processed"])
            
        return message
    
    def create_response(self, content: Any, metadata: Optional[Dict[str, Any]] = None) -> 'MultiAgentMessage':
        """
        Create a response to this message.
        
        Args:
            content: Response content
            metadata: Additional response metadata
            
        Returns:
            Response message
        """
        # Determine response type based on request type
        response_types = {
            MessageType.KNOWLEDGE_REQUEST: MessageType.KNOWLEDGE_RESPONSE,
            MessageType.EXECUTION_REQUEST: MessageType.EXECUTION_RESPONSE,
            MessageType.VERIFICATION_REQUEST: MessageType.VERIFICATION_RESPONSE,
        }
        
        response_type = response_types.get(self.message_type, MessageType.STATUS_UPDATE)
        
        return MultiAgentMessage(
            sender=self.metadata.get("recipient", "unknown"),  # Use the recipient as the new sender
            message_type=response_type,
            content=content,
            metadata=metadata or {},
            in_response_to=self.message_id,
            priority=self.priority  # Match the priority of the request
        )

class MultiAgentBase(BaseAgent):
    """
    Base class for all multi-agent system agents.
    Extends the consolidated BaseAgent with multi-agent specific functionality.
    """
    
    def __init__(
        self, 
        coordinator: Any, 
        agent_id: str, 
        *args, 
        **kwargs
    ):
        """
        Initialize a multi-agent system agent.
        
        Args:
            coordinator: Agent coordinator instance
            agent_id: Unique identifier for this agent
            *args, **kwargs: Additional arguments for BaseAgent
        """
        super().__init__(*args, **kwargs)
        self.coordinator = coordinator
        self.agent_id = agent_id
        self._message_queue = asyncio.Queue()
        self._message_history: List[MultiAgentMessage] = []
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._processing_task = None
        self._is_processing = False
        self._message_handlers: Dict[str, callable] = {}
        
        # Register default message handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self) -> None:
        """Register default message handlers for common message types."""
        self._message_handlers[MessageType.ERROR_REPORT] = self._handle_error_report
        self._message_handlers[MessageType.STATUS_UPDATE] = self._handle_status_update
        
    async def initialize(self) -> None:
        """Initialize the agent and start message processing."""
        await super().initialize()
        
        # Start message processing task
        self._is_processing = True
        self._processing_task = asyncio.create_task(self._process_messages())
        logger.info(f"Agent {self.agent_id} initialized and processing messages")
    
    async def cleanup(self) -> None:
        """Clean up resources and stop message processing."""
        # Stop message processing
        self._is_processing = False
        
        if self._processing_task:
            try:
                # Cancel the task
                self._processing_task.cancel()
                await asyncio.gather(self._processing_task, return_exceptions=True)
            except Exception as e:
                logger.error(f"Error stopping message processing for {self.agent_id}: {e}")
            finally:
                self._processing_task = None
        
        # Cancel all pending responses
        for message_id, future in list(self._pending_responses.items()):
            if not future.done():
                future.cancel()
        
        # Clear internal state
        self._pending_responses.clear()
        
        # Call parent cleanup
        await super().cleanup()
        logger.info(f"Agent {self.agent_id} cleaned up")
    
    async def send_message(
        self, 
        recipient: str, 
        message_type: str, 
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        priority: str = MessagePriority.MEDIUM,
        wait_for_response: bool = False,
        response_timeout: Optional[float] = None
    ) -> Union[bool, MultiAgentMessage]:
        """
        Send a message to another agent via the coordinator.
        
        Args:
            recipient: ID of the recipient agent
            message_type: Type of message
            content: Message content
            metadata: Additional metadata
            priority: Message priority
            wait_for_response: Whether to wait for a response
            response_timeout: Timeout for waiting for response (seconds)
            
        Returns:
            If wait_for_response is True, returns the response message
            Otherwise, returns True if message was sent successfully
        """
        # Prepare metadata with recipient
        metadata = metadata or {}
        metadata["recipient"] = recipient
        
        # Create message
        message = MultiAgentMessage(
            sender=self.agent_id,
            message_type=message_type,
            content=content,
            metadata=metadata,
            priority=priority
        )
        
        if wait_for_response:
            # Create a future to receive the response
            response_future = asyncio.Future()
            self._pending_responses[message.message_id] = response_future
            
            # Send message
            success = await self.coordinator.route_message(message, recipient)
            if not success:
                # Clean up the future
                self._pending_responses.pop(message.message_id, None)
                raise MultiAgentError(f"Failed to send message to {recipient}")
            
            try:
                # Wait for response
                return await asyncio.wait_for(
                    response_future, 
                    timeout=response_timeout
                )
            except asyncio.TimeoutError:
                # Clean up the future
                self._pending_responses.pop(message.message_id, None)
                raise MultiAgentError(f"Timeout waiting for response from {recipient}")
        else:
            # Just send the message without waiting
            return await self.coordinator.route_message(message, recipient)
    
    async def receive_message(self, message: MultiAgentMessage) -> bool:
        """
        Process an incoming message from another agent.
        
        Args:
            message: The message to process
            
        Returns:
            True if message was accepted for processing
        """
        if not isinstance(message, MultiAgentMessage):
            logger.error(f"Received invalid message: {message}")
            return False
        
        # Check if this is a response to a pending message
        if message.in_response_to and message.in_response_to in self._pending_responses:
            # Get the future and set the result
            future = self._pending_responses.pop(message.in_response_to)
            if not future.done():
                future.set_result(message)
            return True
        
        # Otherwise queue for normal processing
        await self._message_queue.put(message)
        return True
    
    async def _process_messages(self) -> None:
        """Process messages from the queue continuously."""
        while self._is_processing:
            try:
                # Get a message from the queue
                message = await self._message_queue.get()
                
                # Add to history
                self._message_history.append(message)
                
                # Process the message
                await self._process_message(message)
                
                # Mark as done
                self._message_queue.task_done()
                
            except asyncio.CancelledError:
                logger.debug(f"Message processing for {self.agent_id} cancelled")
                break
            except Exception as e:
                logger.error(f"Error processing message in {self.agent_id}: {e}", exc_info=True)
    
    async def _process_message(self, message: MultiAgentMessage) -> None:
        """
        Process a specific message by routing to appropriate handler.
        
        Args:
            message: Message to process
        """
        try:
            # Check if we have a specific handler for this message type
            if message.message_type in self._message_handlers:
                handler = self._message_handlers[message.message_type]
                await handler(message)
            else:
                # Use the generic handler
                await self._handle_message(message)
                
            # Mark message as processed
            message.processed = True
            
        except Exception as e:
            logger.error(f"Error handling message {message.message_id} in {self.agent_id}: {e}", exc_info=True)
            
            # Send error report to coordinator
            try:
                error_message = MultiAgentMessage(
                    sender=self.agent_id,
                    message_type=MessageType.ERROR_REPORT,
                    content={
                        "error": str(e),
                        "original_message": message.to_dict()
                    },
                    priority=MessagePriority.HIGH,
                    in_response_to=message.message_id
                )
                await self.coordinator.route_message(error_message, "coordinator")
            except Exception as e2:
                logger.error(f"Failed to send error report: {e2}")
    
    @abstractmethod
    async def _handle_message(self, message: MultiAgentMessage) -> None:
        """
        Handle a message that has no specific handler.
        Must be implemented by subclasses.
        
        Args:
            message: Message to handle
        """
        pass
    
    async def _handle_error_report(self, message: MultiAgentMessage) -> None:
        """
        Handle an error report message.
        Default implementation logs the error.
        
        Args:
            message: Error report message
        """
        content = message.content
        if isinstance(content, dict) and "error" in content:
            logger.error(f"Received error report from {message.sender}: {content['error']}")
        else:
            logger.error(f"Received malformed error report from {message.sender}")
    
    async def _handle_status_update(self, message: MultiAgentMessage) -> None:
        """
        Handle a status update message.
        Default implementation logs the status.
        
        Args:
            message: Status update message
        """
        content = message.content
        if isinstance(content, dict) and "status" in content:
            logger.info(f"Status update from {message.sender}: {content['status']}")
        else:
            logger.info(f"Status update from {message.sender}: {content}")
    
    def register_message_handler(self, message_type: str, handler: callable) -> None:
        """
        Register a handler for a specific message type.
        
        Args:
            message_type: Type of message to handle
            handler: Async function to handle the message
        """
        if not asyncio.iscoroutinefunction(handler):
            raise ValueError(f"Message handler must be a coroutine function")
            
        self._message_handlers[message_type] = handler
        logger.debug(f"Registered handler for {message_type} in {self.agent_id}")
    
    def get_message_history(
        self, 
        message_type: Optional[str] = None, 
        sender: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[MultiAgentMessage]:
        """
        Get message history with optional filtering.
        
        Args:
            message_type: Filter by message type
            sender: Filter by sender
            limit: Maximum number of messages to return
            
        Returns:
            Filtered message history
        """
        # Apply filters
        filtered = self._message_history
        
        if message_type:
            filtered = [m for m in filtered if m.message_type == message_type]
            
        if sender:
            filtered = [m for m in filtered if m.sender == sender]
            
        # Sort by timestamp
        filtered = sorted(filtered, key=lambda m: m.timestamp)
        
        # Apply limit
        if limit is not None and limit > 0:
            filtered = filtered[-limit:]
            
        return filtered
