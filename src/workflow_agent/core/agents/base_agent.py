"""
Base agent class for all agents in the system.
"""
import logging
from typing import Dict, Any, Callable, Awaitable, Optional
from ..message_bus import MessageBus

logger = logging.getLogger(__name__)

class BaseAgent:
    """Abstract base class for all agents in the system."""
    
    def __init__(self, message_bus: MessageBus, name: str):
        """
        Initialize the base agent.
        
        Args:
            message_bus: Message bus for communication
            name: Agent name for logging and identification
        """
        self.message_bus = message_bus
        self.name = name
        self._subscriptions = {}
        
    async def initialize(self) -> None:
        """Initialize agent and subscribe to events."""
        logger.info(f"Initializing {self.name}...")
        await self._subscribe_to_events()
        logger.info(f"{self.name} initialization complete")
    
    async def _subscribe_to_events(self) -> None:
        """Subscribe to events based on subscription dictionary."""
        for topic, handler in self._subscriptions.items():
            await self.message_bus.subscribe(topic, handler)
            logger.debug(f"{self.name} subscribed to '{topic}'")
            
    async def cleanup(self) -> None:
        """Clean up resources."""
        logger.info(f"Cleaning up {self.name}...")
        # Default implementation does nothing
        # Subclasses should override if they need to release resources
        
    async def unsubscribe_all(self) -> None:
        """Unsubscribe from all topics."""
        logger.info(f"Unsubscribing {self.name} from all topics...")
        for topic in self._subscriptions:
            await self.message_bus.unsubscribe(topic, self._subscriptions[topic])
            logger.debug(f"{self.name} unsubscribed from '{topic}'")
        
    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        """Publish a message to the bus with standardized logging."""
        logger.debug(f"{self.name} publishing to '{topic}'")
        await self.message_bus.publish(topic, message)
        
    def register_handler(self, topic: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Register a handler for a topic."""
        self._subscriptions[topic] = handler
        logger.debug(f"{self.name} registered handler for '{topic}'")
