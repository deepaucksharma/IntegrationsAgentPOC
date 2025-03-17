import asyncio
import logging
from typing import Dict, Any, Optional, Callable, Awaitable, List
from ..agent_core.interfaces import BaseAgent, AgentState, AgentResult
from .state import WorkflowState
from .nodes import (
    validate_parameters,
    generate_script,
    validate_script,
    run_script,
    verify_result,
    rollback_changes
)
from .configuration import ensure_workflow_config

logger = logging.getLogger(__name__)

class WorkflowGraph:
    """
    Manages the execution flow of workflow nodes in a directed graph.
    Supports both sequential and concurrent execution of nodes.
    """
    
    def __init__(self):
        """Initialize the workflow graph."""
        self.name = "WorkflowGraph"
        self._nodes = {
            "validate_parameters": validate_parameters,
            "generate_script": generate_script,
            "validate_script": validate_script,
            "run_script": run_script,
            "verify_result": verify_result,
            "rollback_changes": rollback_changes
        }
        self._start = "validate_parameters"
        self._transitions = {
            "validate_parameters": "generate_script",
            "generate_script": "validate_script",
            "validate_script": "run_script",
            "run_script": "verify_result",
            "verify_result": None,
            "rollback_changes": None
        }
        # Optional parallel execution groups
        self._parallel_groups = {
            # Example: "parallel_validation": ["validate_parameters", "validate_system_requirements"]
        }
        
    async def get_node(self, node_name: str) -> Optional[Callable[[WorkflowState, Optional[Dict[str, Any]]], Awaitable[Dict[str, Any]]]]:
        """
        Get a workflow node by name.
        
        Args:
            node_name: Name of the node to retrieve
            
        Returns:
            Node function or None if not found
        """
        return self._nodes.get(node_name)
        
    async def invoke(self, state_dict: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute the workflow graph.
        
        Args:
            state_dict: Initial state dictionary
            config: Optional configuration
            
        Returns:
            Updated state dictionary after workflow execution
        """
        state = WorkflowState(**state_dict)
        workflow_config = ensure_workflow_config(config)
        current_node = self._start
        
        # Determine nodes to skip based on configuration
        skip_nodes = []
        if config and "configurable" in config:
            skip_verify = config["configurable"].get("skip_verification", False)
            if skip_verify and state.action in ["remove", "uninstall"]:
                skip_nodes.append("verify_result")
                logger.info("Skipping verification for removal/uninstall action (configured)")
        
        logger.info(f"Starting workflow execution from node: {current_node}")
        
        # Determine execution mode
        async_execution = workflow_config.async_execution
        
        if async_execution:
            logger.info("Using asynchronous workflow execution")
            return await self._invoke_async(state, skip_nodes, config)
        else:
            logger.info("Using sequential workflow execution")
            return await self._invoke_sequential(state, skip_nodes, config)
    
    async def _invoke_sequential(self, state: WorkflowState, skip_nodes: List[str], config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute workflow nodes sequentially.
        
        Args:
            state: Workflow state
            skip_nodes: List of nodes to skip
            config: Optional configuration
            
        Returns:
            Updated state dictionary after workflow execution
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
                current_node = "rollback_changes"
                continue
            
            current_node = self._transitions.get(current_node)
            if current_node:
                logger.info(f"Transitioning to node: {current_node}")
            else:
                logger.info("Workflow execution completed")
        
        return state.dict()
    
    async def _invoke_async(self, state: WorkflowState, skip_nodes: List[str], config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute workflow with potential parallel execution of node groups.
        
        Args:
            state: Workflow state
            skip_nodes: List of nodes to skip
            config: Optional configuration
            
        Returns:
            Updated state dictionary after workflow execution
        """
        current_node = self._start
        
        while current_node:
            # Check if current node is part of a parallel group
            parallel_group = None
            for group_name, nodes in self._parallel_groups.items():
                if current_node in nodes:
                    parallel_group = group_name
                    break
            
            if parallel_group:
                # Execute nodes in parallel group
                logger.info(f"Executing parallel node group: {parallel_group}")
                nodes_to_execute = [node for node in self._parallel_groups[parallel_group] if node not in skip_nodes]
                
                if not nodes_to_execute:
                    # All nodes in group are skipped
                    logger.info(f"All nodes in group {parallel_group} are skipped")
                    # Find the next node after this group
                    next_nodes = set()
                    for node in self._parallel_groups[parallel_group]:
                        next_node = self._transitions.get(node)
                        if next_node:
                            next_nodes.add(next_node)
                    
                    if len(next_nodes) == 1:
                        current_node = next(iter(next_nodes))
                    else:
                        state.error = f"Ambiguous transition from parallel group {parallel_group}"
                        logger.error(state.error)
                        current_node = "rollback_changes"
                    continue
                
                # Execute nodes in parallel
                tasks = []
                for node in nodes_to_execute:
                    node_func = self._nodes.get(node)
                    if node_func:
                        tasks.append(node_func(state, config))
                    else:
                        state.error = f"Node {node} not found in workflow graph"
                        logger.error(f"Missing node in workflow graph: {node}")
                
                # Wait for all tasks to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.exception(f"Error executing node {nodes_to_execute[i]}: {result}")
                        state.error = f"Error in {nodes_to_execute[i]}: {str(result)}"
                        break
                    elif isinstance(result, dict):
                        for key, value in result.items():
                            setattr(state, key, value)
                        if "error" in result:
                            logger.error(f"Node {nodes_to_execute[i]} returned error: {result['error']}")
                            state.error = result["error"]
                            break
                
                if state.error:
                    current_node = "rollback_changes"
                    continue
                
                # Find the next node after this group
                next_nodes = set()
                for node in nodes_to_execute:
                    next_node = self._transitions.get(node)
                    if next_node:
                        next_nodes.add(next_node)
                
                if len(next_nodes) == 1:
                    current_node = next(iter(next_nodes))
                else:
                    state.error = f"Ambiguous transition from parallel group {parallel_group}"
                    logger.error(state.error)
                    current_node = "rollback_changes"
            else:
                # Execute single node
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
                    current_node = "rollback_changes"
                    continue
                
                current_node = self._transitions.get(current_node)
                if current_node:
                    logger.info(f"Transitioning to node: {current_node}")
                else:
                    logger.info("Workflow execution completed")
        
        return state.dict()
        
    def register_node(self, name: str, func: Callable[[WorkflowState, Optional[Dict[str, Any]]], Awaitable[Dict[str, Any]]]) -> None:
        """
        Register a new node in the workflow graph.
        
        Args:
            name: Node name
            func: Node function
        """
        self._nodes[name] = func
        logger.info(f"Registered workflow node: {name}")
    
    def set_transition(self, from_node: str, to_node: Optional[str]) -> None:
        """
        Set or update a transition between nodes.
        
        Args:
            from_node: Source node name
            to_node: Target node name or None for terminal node
        """
        if from_node not in self._nodes:
            raise ValueError(f"Source node '{from_node}' not found in graph")
        
        if to_node is not None and to_node not in self._nodes:
            raise ValueError(f"Target node '{to_node}' not found in graph")
        
        self._transitions[from_node] = to_node
        logger.info(f"Set transition: {from_node} -> {to_node or 'END'}")
    
    def define_parallel_group(self, group_name: str, node_names: List[str]) -> None:
        """
        Define a group of nodes that can be executed in parallel.
        
        Args:
            group_name: Name for the parallel group
            node_names: List of node names in the group
        """
        # Validate that all nodes exist
        for node in node_names:
            if node not in self._nodes:
                raise ValueError(f"Node '{node}' not found in graph")
        
        self._parallel_groups[group_name] = node_names
        logger.info(f"Defined parallel group '{group_name}' with nodes: {', '.join(node_names)}")

# Create default graph instance
graph = WorkflowGraph()
