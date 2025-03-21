"""Recovery manager for handling workflow failures."""
from typing import Dict, Any, Optional
from ..core.state import WorkflowState

class RecoveryManager:
    """Manages recovery operations for failed workflows."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._strategies = {}
        
    async def recover(self, state: WorkflowState) -> WorkflowState:
        """Attempt to recover from a failed workflow."""
        try:
            # Get recovery strategy if available
            strategy = self._get_strategy(state.action)
            if strategy:
                return await strategy.recover(state)
                
            # No strategy found, return state as is
            return state.add_warning("No recovery strategy available")
            
        except Exception as e:
            return state.add_warning(f"Recovery failed: {str(e)}")
            
    def register_strategy(self, action: str, strategy: Any) -> None:
        """Register a recovery strategy for an action."""
        self._strategies[action] = strategy
        
    def _get_strategy(self, action: str) -> Optional[Any]:
        """Get recovery strategy for an action."""
        return self._strategies.get(action) 