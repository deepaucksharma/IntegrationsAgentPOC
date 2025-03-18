"""Base integration class for workflow agent."""
import logging
from typing import Any, Dict, List, Optional

from ..core.state import WorkflowState

logger = logging.getLogger(__name__)

class IntegrationBase:
    """Base class for all integration handlers."""
    
    @classmethod
    def get_name(cls) -> str:
        # Normalize name by removing underscores and lowercasing
        return cls.__name__.replace("_", "").lower().replace("integration", "")
    
    @classmethod
    def get_supported_targets(cls) -> List[str]:
        return []
    
    @classmethod
    def get_category(cls) -> str:
        return "custom"
    
    @classmethod
    def get_version(cls) -> str:
        return "1.0.0"
    
    @classmethod
    def get_parameters(cls) -> Dict[str, Dict[str, Any]]:
        return {}
    
    async def handle(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info(f"Base implementation for {self.get_name()} integration")
        return {"error": f"Integration {self.get_name()} doesn't implement handle method"}
    
    async def validate(self, state: WorkflowState) -> Dict[str, Any]:
        missing_params = []
        parameters = self.get_parameters()
        for name, spec in parameters.items():
            if spec.get("required", False) and (name not in state.parameters or state.parameters[name] is None):
                missing_params.append(name)
        if missing_params:
            return {"valid": False, "error": f"Missing required parameters: {', '.join(missing_params)}"}
        return {"valid": True}