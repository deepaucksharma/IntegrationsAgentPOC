"""
Integration executor functionality has been moved to executor.py.
This module is maintained for backward compatibility.
New code should use executor.ScriptExecutor directly.
"""

from .executor import ScriptExecutor

class IntegrationExecutor:
    """Redirects to ScriptExecutor for backward compatibility."""
    
    def __init__(self):
        """Initialize with warning about deprecated usage."""
        import logging
        logging.getLogger(__name__).warning(
            "IntegrationExecutor is deprecated. Use ScriptExecutor instead."
        )
        self._executor = ScriptExecutor(None)  # Pass None as config for compatibility
        
    async def execute(self, integration: any, action: str, params: dict) -> dict:
        """Redirects to ScriptExecutor.execute_integration."""
        return await self._executor.execute_integration(integration, action, params)
            
    def set_context(self, key: str, value: any) -> None:
        """Redirects to ScriptExecutor.set_context."""
        self._executor.set_context(key, value)
        
    def get_context(self, key: str, default: any = None) -> any:
        """Redirects to ScriptExecutor.get_context."""
        return self._executor.get_context(key, default)
