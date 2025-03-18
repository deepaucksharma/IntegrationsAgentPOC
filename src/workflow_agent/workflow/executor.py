import logging
import asyncio
from typing import Dict, Any, Optional, List
from ..core.state import WorkflowState
from ..config.configuration import ensure_workflow_config
from .graph import WorkflowGraph

logger = logging.getLogger(__name__)

class WorkflowExecutor:
    """Executes workflows by coordinating multiple nodes."""
    
    def __init__(
        self,
        graph: Optional[WorkflowGraph] = None,
        default_config: Optional[Dict[str, Any]] = None,
        max_concurrent_tasks: int = 5
    ):
        """
        Initialize the workflow executor.
        
        Args:
            graph: Optional workflow graph
            default_config: Optional default configuration
            max_concurrent_tasks: Maximum number of concurrent tasks to execute
        """
        self.graph = graph or WorkflowGraph()
        self.default_config = default_config or {}
        self.max_concurrent_tasks = max_concurrent_tasks
    
    async def cleanup(self) -> None:
        """Clean up workflow executor resources."""
        try:
            if hasattr(self.graph, 'cleanup'):
                await self.graph.cleanup()
            logger.info("WorkflowExecutor resources cleaned up")
        except Exception as e:
            logger.error(f"Error during WorkflowExecutor cleanup: {e}")
            # Don't re-raise as cleanup should be best-effort
    
    async def execute_workflow(
        self,
        state: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a workflow with the given state and configuration.
        
        Args:
            state: Initial workflow state
            config: Optional configuration
            
        Returns:
            Updated workflow state as a dictionary
        """
        try:
            # Convert state dict to WorkflowState if it's not already
            workflow_state = state if isinstance(state, WorkflowState) else WorkflowState(**state)
            
            # Get workflow configuration
            workflow_config = ensure_workflow_config(config)
            
            # Determine nodes to skip based on configuration
            skip_nodes = []
            if config and "configurable" in config:
                skip_verify = config["configurable"].get("skip_verification", False)
                if skip_verify and workflow_state.action in ["remove", "uninstall"]:
                    skip_nodes.append("verify_result")
                    logger.info("Skipping verification for removal/uninstall action (configured)")
            
            # Execute workflow
            result_state = await self.graph.execute(
                state=workflow_state,
                config=workflow_config.dict(),  # Convert Pydantic model to dict
                async_execution=workflow_config.async_execution,
                skip_nodes=skip_nodes
            )
            
            # Convert back to dictionary
            return result_state.dict()
        except Exception as e:
            logger.exception(f"Error executing workflow: {e}")
            return {
                "error": f"Workflow execution failed: {str(e)}",
                "action": workflow_state.action if 'workflow_state' in locals() else state.get("action", "unknown"),
                "target_name": workflow_state.target_name if 'workflow_state' in locals() else state.get("target_name", "unknown")
            }