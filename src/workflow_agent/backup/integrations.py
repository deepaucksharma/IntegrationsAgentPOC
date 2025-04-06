"""
Base integrations module.
"""
from typing import Dict, Any, Optional

from .base import IntegrationBase

class BaseIntegration(IntegrationBase):
    """Base integration implementation."""
    
    @classmethod
    def get_category(cls) -> str:
        return "base"
        
    @classmethod
    def get_supported_targets(cls) -> list[str]:
        return ["base"]
        
    async def install(self, parameters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Base install implementation."""
        return {"status": "success", "message": "Base installation completed"}
        
    async def verify(self, parameters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Base verify implementation."""
        return {"status": "success", "message": "Base verification completed"}
        
    async def uninstall(self, parameters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Base uninstall implementation."""
        return {"status": "success", "message": "Base uninstallation completed"} 