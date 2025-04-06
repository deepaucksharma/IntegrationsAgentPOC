"""Execution handling for integrations."""
from typing import Dict, Any, Optional

from ..error.exceptions import IntegrationExecutionError

class IntegrationExecutor:
    """Handles execution of integration operations."""
    
    def __init__(self):
        self._context = {}
        
    async def execute(self, integration: Any, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an integration action."""
        try:
            if not hasattr(integration, action):
                raise IntegrationExecutionError(f"Action {action} not supported by integration")
                
            method = getattr(integration, action)
            result = await method(params)
            
            if not isinstance(result, dict):
                raise IntegrationExecutionError("Integration action must return a dictionary")
                
            return result
            
        except Exception as e:
            raise IntegrationExecutionError(f"Execution failed: {str(e)}")
            
    def set_context(self, key: str, value: Any) -> None:
        """Set execution context value."""
        self._context[key] = value
        
    def get_context(self, key: str, default: Any = None) -> Any:
        """Get execution context value."""
        return self._context.get(key, default)
