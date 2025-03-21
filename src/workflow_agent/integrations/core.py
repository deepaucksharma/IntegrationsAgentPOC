"""Core functionality for integrations."""
from typing import Dict, Any, Optional

class IntegrationCore:
    """Core functionality for integrations."""
    
    def __init__(self):
        self._handlers = {}
        
    def register_handler(self, name: str, handler: Any) -> None:
        """Register a handler."""
        self._handlers[name] = handler
        
    def get_handler(self, name: str) -> Optional[Any]:
        """Get a registered handler."""
        return self._handlers.get(name)
        
    def list_handlers(self) -> Dict[str, Any]:
        """List all registered handlers."""
        return self._handlers.copy() 