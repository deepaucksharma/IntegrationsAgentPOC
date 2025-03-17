import logging
from typing import Dict, Any, Optional, Callable, Awaitable, List, Set
from ..core.state import WorkflowState

logger = logging.getLogger(__name__)

class WorkflowGraph:
    """
    Manages the execution flow of workflow nodes in a directed graph.
    Supports both sequential and concurrent execution of nodes.
    """
    
    def __init__(self):
        """Initialize the workflow graph."""
        self.name = "WorkflowGraph"
        self._nodes = {}
        self._start = None
        self._transitions = {}
        self._parallel_groups = {}
    
    def add_node(
        self,
        name: str,
        node_func: Callable[[WorkflowState, Optional[Dict[str, Any]]], Awaitable[Dict[str, Any]]]
    ) -> None:
        """
        Add a node to the workflow graph.
        
        Args:
            name: Name of the node
            node_func: Function to execute for this node
        """
        self._nodes[name] = node_func
        logger.debug(f"Added node {name} to workflow graph")
        
        # Set as start node if this is the first node
        if not self._start:
            self._start = name
    
    def set_start_node(self, name: str) -> None:
        """
        Set the starting node for the workflow.
        
        Args:
            name: Name of the starting node
        """
        if name not in self._nodes:
            raise ValueError(f"Node '{name}' not found in graph")
        
        self._start = name
        logger.debug(f"Set start node to {name}")
    
    def add_transition(self, from_node: str, to_node: Optional[str]) -> None:
        """
        Add a transition between nodes.
        
        Args:
            from_node: Source node name
            to_node: Target node name or None for terminal node
        """
        if from_node not in self._nodes:
            raise ValueError(f"Source node '{from_node}' not found in graph")
        
        if to_node is not None and to_node not in self._nodes:
            raise ValueError(f"Target node '{to_node}' not found in graph")
        
        self._transitions[from_node] = to_node
        logger.debug(f"Added transition {from_node} -> {to_node or 'END'}")
    
    def add_parallel_group(self, group_name: str, node_names: List[str]) -> None:
        """
        Define a group of nodes that can be executed in parallel.
        
        Args:
            group_name: Name for the parallel group
            node_names: List of node names in the group
        """
        for node in node_names:
            if node not in self._nodes:
                raise ValueError(f"Node '{node}' not found in graph")
        
        self._parallel_groups[group_name] = node_names
        logger.debug(f"Added parallel group '{group_name}': {', '.join(node_names)}")
    
    async def get_node(self, node_name: str) -> Optional[Callable]:
        """
        Get a node function by name.
        
        Args:
            node_name: Name of the node
            
        Returns:
            Node function or None if not found
        """
        return self._nodes.get(node_name)
    
    async def execute(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None,
        async_execution: bool = False,
        skip_nodes: Optional[List[str]] = None
    ) -> WorkflowState:
        """
        Execute the workflow graph.
        
        Args:
            state: Initial workflow state
            config: Optional configuration
            async_execution: Whether to use asynchronous execution
            skip_nodes: List of nodes to skip
            
        Returns:
            Updated workflow state
        """
        if not self._start:
            raise ValueError("No start node defined for workflow graph")
        
        skip_nodes = skip_nodes or []
        
        if async_execution:
            logger.info("Using asynchronous workflow execution")
            return await self._execute_async(state, config, skip_nodes)
        else:
            logger.info("Using sequential workflow execution")
            return await self._execute_sequential(state, config, skip_nodes)
    
    async def _execute_sequential(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None,
        skip_nodes: List[str] = None
    ) -> WorkflowState:
        """
        Execute workflow nodes sequentially.
        
        Args:
            state: Initial workflow state
            config: Optional configuration
            skip_nodes: List of nodes to skip
            
        Returns:
            Updated workflow state
        """
        current_node = self._start
        
        while current_node:
            node_func = self._nodes.get(current_node)
            if not node_func:
                state.error = f"Node {current_node} not found in workflow graph"
                logger.error(f"Missing node in workflow graph: {current_node}")
                break
            
            logger.info(f"Executing node: {current_node}")
            if current_node in skip_nodes:
                logger.info(f"Skipping node: {current_node}")
                current_node = self._transitions.get(current_node)
                continue
            
            try:
                result = await node_func(state, config)
                for key, value in result.items():
                    setattr(state, key, value)
            except Exception as e:
                logger.exception(f"Error executing node {current_node}: {e}")
                state.error = f"Error in {current_node}: {str(e)}"
            
            if state.error:
                logger.error(f"Node {current_node} returned error: {state.error}")
                # Find the rollback node if defined
                rollback_node = next((n for n, f in self._nodes.items() if n.startswith("rollback")), None)
                if rollback_node:
                    logger.info(f"Transitioning to rollback node: {rollback_node}")
                    current_node = rollback_node
                else:
                    logger.warning("No rollback node defined, ending workflow")
                    break
                continue
            
            current_node = self._transitions.get(current_node)
            if current_node:
                logger.info(f"Transitioning to node: {current_node}")
            else:
                logger.info("Workflow execution completed")
        
        return state