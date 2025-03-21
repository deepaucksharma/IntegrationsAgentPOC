"""
Message bus for inter-agent communication.
"""
import asyncio
import logging
from typing import Dict, Any, Callable, List, Optional
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)

class MessageBus:
    """Message bus for inter-agent communication."""
    
    def __init__(self):
        self._subscribers = {}
        self._lock = asyncio.Lock()
        self._message_history = {}
        self._message_queues = {}  # Per-topic message queues
        self._processing = {}  # Track processing state per topic
        self._max_queue_size = 1000  # Prevent memory issues
    
    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        """Publish a message to a topic."""
        # Add timestamp and sequence number
        message["timestamp"] = datetime.utcnow().isoformat()
        
        async with self._lock:
            if topic not in self._message_history:
                self._message_history[topic] = []
            if topic not in self._message_queues:
                self._message_queues[topic] = deque(maxlen=self._max_queue_size)
            
            # Add to history and queue
            self._message_history[topic].append(message)
            self._message_queues[topic].append(message)
            
            if topic not in self._subscribers:
                logger.debug(f"No subscribers for topic: {topic}")
                return
        
        # Process queue if not already processing
        if topic not in self._processing or not self._processing[topic]:
            asyncio.create_task(self._process_queue(topic))
    
    async def _process_queue(self, topic: str) -> None:
        """Process messages in the queue for a topic."""
        if topic in self._processing and self._processing[topic]:
            return
            
        self._processing[topic] = True
        try:
            while self._message_queues[topic]:
                message = self._message_queues[topic].popleft()
                subscribers = list(self._subscribers.get(topic, set()))
                
                # Process with all subscribers
                for callback in subscribers:
                    try:
                        await callback(message)
                    except Exception as e:
                        logger.error(f"Error in subscriber callback: {e}")
                        # Continue with other subscribers even if one fails
                        continue
        finally:
            self._processing[topic] = False
    
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