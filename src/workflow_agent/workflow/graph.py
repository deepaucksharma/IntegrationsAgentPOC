import logging
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable, List, Set, NamedTuple
from ..core.state import WorkflowState

logger = logging.getLogger(__name__)

class NodeConfig(NamedTuple):
    """Configuration for a workflow node."""
    func: Callable[[WorkflowState, Optional[Dict[str, Any]]], Awaitable[Dict[str, Any]]]
    retry_count: int = 0
    retry_delay: float = 1.0
    timeout: Optional[float] = None
    optional: bool = False
    requires_previous: bool = True

class WorkflowGraph:
    """
    Manages the execution flow of workflow nodes in a directed graph.
    Supports both sequential and concurrent execution of nodes.
    """
    
    def __init__(self):
        """Initialize the workflow graph."""
        self.name = "WorkflowGraph"
        self._nodes = {}
        self._start_nodes = []
        self._transitions = {}
        self._parallel_groups = {}
    
    def add_node(
        self,
        name: str,
        node_func: Callable[[WorkflowState, Optional[Dict[str, Any]]], Awaitable[Dict[str, Any]]],
        retry_count: int = 0,
        retry_delay: float = 1.0,
        timeout: Optional[float] = None,
        optional: bool = False,
        requires_previous: bool = True
    ) -> None:
        """
        Add a node to the workflow graph.
        
        Args:
            name: Name of the node
            node_func: Function to execute for this node
            retry_count: Number of times to retry on failure
            retry_delay: Delay between retries in seconds
            timeout: Optional timeout in seconds
            optional: Whether this node is optional
            requires_previous: Whether this node requires previous nodes to complete
        """
        self._nodes[name] = NodeConfig(
            func=node_func,
            retry_count=retry_count,
            retry_delay=retry_delay,
            timeout=timeout,
            optional=optional,
            requires_previous=requires_previous
        )
        logger.debug(f"Added node {name} to workflow graph")
        
        # Set as start node if this is the first node
        if not self._start_nodes:
            self._start_nodes = [name]
    
    def set_start_nodes(self, names: List[str]) -> None:
        """
        Set the starting nodes for the workflow.
        
        Args:
            names: List of starting node names
        """
        for name in names:
            if name not in self._nodes:
                raise ValueError(f"Node '{name}' not found in graph")
        
        self._start_nodes = names
        logger.debug(f"Set start nodes to {names}")
    
    def add_transition(self, from_node: str, to_nodes: List[str]) -> None:
        """
        Add transitions from a node to multiple target nodes.
        
        Args:
            from_node: Source node name
            to_nodes: List of target node names
        """
        if from_node not in self._nodes:
            raise ValueError(f"Source node '{from_node}' not found in graph")
        
        for to_node in to_nodes:
            if to_node and to_node not in self._nodes:
                raise ValueError(f"Target node '{to_node}' not found in graph")
        
        self._transitions[from_node] = to_nodes
        logger.debug(f"Added transitions {from_node} -> {to_nodes or 'END'}")
    
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
        if not self._start_nodes:
            raise ValueError("No start nodes defined for workflow graph")
        
        skip_nodes = skip_nodes or []
        
        if async_execution:
            logger.info("Using asynchronous workflow execution")
            return await self._execute_async(state, config, skip_nodes)
        else:
            logger.info("Using sequential workflow execution")
            return await self._execute_sequential(state, config, skip_nodes)
    
    async def _execute_node(
        self,
        node_name: str,
        node_config: NodeConfig,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Execute a single node with retries and timeout.
        
        Args:
            node_name: Name of the node
            node_config: Node configuration
            state: Workflow state
            config: Optional configuration
            
        Returns:
            True if execution succeeded, False otherwise
        """
        retries_left = node_config.retry_count + 1
        
        while retries_left > 0:
            try:
                if node_config.timeout:
                    # Execute with timeout
                    result = await asyncio.wait_for(
                        node_config.func(state, config),
                        timeout=node_config.timeout
                    )
                else:
                    # Execute without timeout
                    result = await node_config.func(state, config)
                
                # Update state with result
                for key, value in result.items():
                    setattr(state, key, value)
                
                return True
                
            except asyncio.TimeoutError:
                logger.error(f"Node {node_name} timed out after {node_config.timeout} seconds")
                state.error = f"Timeout in {node_name}"
                
            except Exception as e:
                logger.error(f"Error executing node {node_name}: {e}")
                state.error = f"Error in {node_name}: {str(e)}"
            
            retries_left -= 1
            if retries_left > 0:
                logger.info(f"Retrying node {node_name} after {node_config.retry_delay} seconds ({retries_left} retries left)")
                await asyncio.sleep(node_config.retry_delay)
        
        # All retries failed
        if node_config.optional:
            logger.warning(f"Optional node {node_name} failed, continuing workflow")
            state.error = None
            return True
        
        return False
    
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
        current_nodes = self._start_nodes.copy()
        skip_nodes = skip_nodes or []
        
        while current_nodes:
            next_nodes = []
            for current_node in current_nodes:
                node_config = self._nodes.get(current_node)
                if not node_config:
                    state.error = f"Node {current_node} not found in workflow graph"
                    logger.error(f"Missing node in workflow graph: {current_node}")
                    return state
                
                logger.info(f"Executing node: {current_node}")
                if current_node in skip_nodes:
                    logger.info(f"Skipping node: {current_node}")
                    next_nodes.extend(self._transitions.get(current_node, []))
                    continue
                
                success = await self._execute_node(current_node, node_config, state, config)
                
                if not success and state.error:
                    logger.error(f"Node {current_node} failed: {state.error}")
                    # Find the rollback node if defined
                    rollback_node = next((n for n in self._nodes.keys() if n.startswith("rollback")), None)
                    if rollback_node:
                        logger.info(f"Transitioning to rollback node: {rollback_node}")
                        next_nodes = [rollback_node]
                        break
                    else:
                        logger.warning("No rollback node defined, ending workflow")
                        return state
                
                # Add next nodes to process
                next_nodes.extend(self._transitions.get(current_node, []))
            
            # Update current nodes for next iteration
            current_nodes = next_nodes
            if current_nodes:
                logger.info(f"Transitioning to nodes: {current_nodes}")
            else:
                logger.info("Workflow execution completed")
        
        return state