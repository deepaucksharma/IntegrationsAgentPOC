"""
Message bus for inter-agent communication.
"""
import asyncio
import logging
from typing import Dict, Any, Callable, List, Optional

logger = logging.getLogger(__name__)

class MessageBus:
    """Message bus for inter-agent communication."""
    
    def __init__(self):
        self._subscribers = {}
        self._lock = asyncio.Lock()
        self._message_history = {}
    
    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        """Publish a message to a topic."""
        subscribers = []
        async with self._lock:
            if topic not in self._message_history:
                self._message_history[topic] = []
            self._message_history[topic].append(message)
            
            if topic not in self._subscribers:
                logger.debug(f"No subscribers for topic: {topic}")
                return
            subscribers = list(self._subscribers[topic])
        
        for callback in subscribers:
            try:
                await callback(message)
            except Exception as e:
                logger.error(f"Error in subscriber callback: {e}")
    
    async def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to a topic with a callback."""
        async with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = set()
            self._subscribers[topic].add(callback)
            logger.debug(f"Subscribed to topic: {topic}")
    
    async def unsubscribe(self, topic: str, callback: Callable) -> None:
        """Unsubscribe from a topic."""
        async with self._lock:
            if topic in self._subscribers and callback in self._subscribers[topic]:
                self._subscribers[topic].remove(callback)
                logger.debug(f"Unsubscribed from topic: {topic}")
    
    def get_message_history(self, topic: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get message history for debugging."""
        if topic:
            return {topic: self._message_history.get(topic, [])}
        return self._message_history