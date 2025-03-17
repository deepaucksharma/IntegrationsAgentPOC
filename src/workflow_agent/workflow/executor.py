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
        default_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the workflow executor.
        
        Args:
            graph: Optional workflow graph
            default_config: Optional default configuration
        """
        self.graph = graph or WorkflowGraph()
        self.default_config = default_config or {}
    
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
        # Merge with default configuration
        merged_config = self.default_config.copy()
        if config:
            for key, value in config.items():
                if key in merged_config and isinstance(merged_config[key], dict) and isinstance(value, dict):
                    merged_config[key].update(value)
                else:
                    merged_config[key] = value
        
        # Get workflow configuration
        workflow_config = ensure_workflow_config(merged_config)
        
        # Convert state dict to WorkflowState
        workflow_state = WorkflowState(**state)
        
        # Determine nodes to skip based on configuration
        skip_nodes = []
        if config and "configurable" in config:
            skip_verify = config["configurable"].get("skip_verification", False)
            if skip_verify and workflow_state.action in ["remove", "uninstall"]:
                skip_nodes.append("verify_result")
                logger.info("Skipping verification for removal/uninstall action (configured)")
        
        # Execute workflow
        try:
            result_state = await self.graph.execute(
                state=workflow_state,
                config=merged_config,
                async_execution=workflow_config.async_execution,
                skip_nodes=skip_nodes
            )
            
            # Convert back to dictionary
            return result_state.dict()
        except Exception as e:
            logger.exception(f"Error executing workflow: {e}")
            return {
                "error": f"Workflow execution failed: {str(e)}",
                "action": workflow_state.action,
                "target_name": workflow_state.target_name
            }