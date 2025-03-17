# src/workflow_agent/integrations/base.py
import logging
from typing import Any, Dict, List, Optional
from ..core.state import WorkflowState

logger = logging.getLogger(__name__)

class IntegrationBase:
    """Base class for all integration handlers."""
    
    @classmethod
    def get_name(cls) -> str:
        """Get the name of this integration."""
        return cls.__name__.lower().replace("integration", "")
    
    @classmethod
    def get_supported_targets(cls) -> List[str]:
        """Return list of targets this integration supports."""
        return []
    
    async def handle(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle the integration request.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with updates to workflow state
        """
        logger.info(f"Base implementation for {self.get_name()} integration")
        return {}