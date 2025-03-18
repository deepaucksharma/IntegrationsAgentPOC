import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class WorkflowNode:
    """Represents a node in the workflow graph."""
    name: str
    handler: callable
    retry_count: int = 0
    retry_delay: float = 1.0
    timeout: Optional[float] = None
    optional: bool = False
    requires_previous: bool = True

class WorkflowGraph:
    """Represents a directed graph of workflow nodes."""
    
    def __init__(self):
        self.nodes: Dict[str, WorkflowNode] = {}
        self.transitions: Dict[str, List[str]] = {}
        self.start_nodes: List[str] = []
        self.parallel_groups: Dict[str, List[str]] = {}
    
    def add_node(self, name: str, handler: callable, **kwargs) -> None:
        """Add a node to the graph."""
        self.nodes[name] = WorkflowNode(name=name, handler=handler, **kwargs)
    
    def add_transition(self, from_node: str, to_nodes: List[str]) -> None:
        """Add transitions from one node to others."""
        self.transitions[from_node] = to_nodes
    
    def set_start_nodes(self, nodes: List[str]) -> None:
        """Set the starting nodes of the workflow."""
        self.start_nodes = nodes
    
    def add_parallel_group(self, name: str, nodes: List[str]) -> None:
        """Add a group of nodes that can be executed in parallel."""
        self.parallel_groups[name] = nodes

class WorkflowExecutor:
    """Executes workflows with concurrency control and error handling."""
    
    def __init__(self, graph: WorkflowGraph, max_concurrent_tasks: int = 5):
        self.graph = graph
        self.max_concurrent_tasks = max_concurrent_tasks
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._running_tasks: Dict[str, asyncio.Task] = {}
    
    async def execute_workflow(self, state: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the workflow with concurrency control."""
        try:
            # Initialize result tracking
            results: Dict[str, Any] = {}
            errors: Dict[str, str] = {}
            
            # Create tasks for start nodes
            tasks = []
            for node_name in self.graph.start_nodes:
                task = asyncio.create_task(
                    self._execute_node(node_name, state, config, results, errors)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)
            
            # Check for errors
            if errors:
                return {
                    "success": False,
                    "error": "Workflow execution failed",
                    "errors": errors,
                    "results": results
                }
            
            return {
                "success": True,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_node(self, node_name: str, state: Dict[str, Any], 
                          config: Optional[Dict[str, Any]], results: Dict[str, Any],
                          errors: Dict[str, str]) -> None:
        """Execute a single node with concurrency control."""
        node = self.graph.nodes[node_name]
        
        # Skip if node is optional and previous nodes failed
        if node.requires_previous and any(node_name in errors for node_name in self.graph.transitions):
            return
        
        # Acquire semaphore for concurrency control
        async with self.semaphore:
            try:
                # Execute node with timeout if specified
                if node.timeout:
                    result = await asyncio.wait_for(
                        node.handler(state, config),
                        timeout=node.timeout
                    )
                else:
                    result = await node.handler(state, config)
                
                results[node_name] = result
                
                # Execute next nodes
                next_nodes = self.graph.transitions.get(node_name, [])
                tasks = []
                for next_node in next_nodes:
                    task = asyncio.create_task(
                        self._execute_node(next_node, state, config, results, errors)
                    )
                    tasks.append(task)
                
                if tasks:
                    await asyncio.gather(*tasks)
                
            except asyncio.TimeoutError:
                errors[node_name] = f"Node execution timed out after {node.timeout} seconds"
            except Exception as e:
                errors[node_name] = str(e)
                logger.error(f"Error executing node {node_name}: {e}")
    
    async def cleanup(self) -> None:
        """Clean up running tasks."""
        try:
            # Cancel all running tasks
            for task in self._running_tasks.values():
                if not task.done():
                    task.cancel()
            
            # Wait for all tasks to complete
            if self._running_tasks:
                await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)
            
            self._running_tasks.clear()
            
        except Exception as e:
            logger.error(f"Error during workflow executor cleanup: {e}")
            # Don't re-raise as cleanup should be best-effort 