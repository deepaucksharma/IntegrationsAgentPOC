"""
WorkflowTracker: Tracks the state and progress of workflows.
Provides immutable state transitions and history tracking.
"""
import asyncio
import logging
import copy
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from ..core.state import WorkflowState

logger = logging.getLogger(__name__)

class WorkflowTracker:
    """
    Tracks the state and progress of workflows with immutable state transitions.
    Provides history tracking and checkpointing capabilities.
    """
    
    def __init__(self):
        """Initialize the workflow tracker."""
        self.workflows = {}
        self.history = {}
        self.checkpoints = {}
        self._lock = asyncio.Lock()
    
    async def create_workflow(self, workflow_id: str, initial_state: Dict[str, Any]) -> str:
        """
        Create a new workflow with initial state.
        
        Args:
            workflow_id: Unique workflow identifier
            initial_state: Initial workflow state
            
        Returns:
            Workflow ID
        """
        async with self._lock:
            # Create workflow record
            self.workflows[workflow_id] = {
                "state": initial_state,
                "status": "created",
                "created_at": datetime.now(),
                "steps": [],
                "current_step": None
            }
            
            # Initialize history
            self.history[workflow_id] = [{
                "timestamp": datetime.now(),
                "step": "create",
                "state": copy.deepcopy(initial_state)
            }]
            
            # Create initial checkpoint
            self.checkpoints[workflow_id] = {
                "initial": {
                    "timestamp": datetime.now(),
                    "state": copy.deepcopy(initial_state)
                }
            }
            
            logger.info(f"Created workflow {workflow_id}")
            return workflow_id
            
    async def update_workflow(self, 
                             workflow_id: str, 
                             state_update: Dict[str, Any], 
                             step: Optional[str] = None) -> Dict[str, Any]:
        """
        Update workflow state and record history.
        
        Args:
            workflow_id: Workflow identifier
            state_update: State updates to apply
            step: Current workflow step
            
        Returns:
            Updated workflow state
        """
        async with self._lock:
            if workflow_id not in self.workflows:
                raise ValueError(f"Workflow {workflow_id} not found")
                
            workflow = self.workflows[workflow_id]
            
            # Create immutable snapshot of previous state
            prev_state = copy.deepcopy(workflow["state"])
            
            # Update state
            if isinstance(workflow["state"], dict):
                workflow["state"].update(state_update)
            elif hasattr(workflow["state"], "model_dump"):
                # For Pydantic models
                state_dict = workflow["state"].model_dump()
                state_dict.update(state_update)
                workflow["state"] = WorkflowState(**state_dict)
            else:
                # Just replace if we can't update
                workflow["state"] = state_update
                
            # Update step if provided
            if step:
                workflow["steps"].append(step)
                workflow["current_step"] = step
                workflow["status"] = "in_progress"
                
            # Record history
            self.history[workflow_id].append({
                "timestamp": datetime.now(),
                "step": step or "update",
                "prev_state": prev_state,
                "new_state": copy.deepcopy(workflow["state"])
            })
            
            logger.debug(f"Updated workflow {workflow_id}" + (f" - Step: {step}" if step else ""))
            return workflow["state"]
            
    async def create_checkpoint(self, workflow_id: str, checkpoint_name: str) -> bool:
        """
        Create a named checkpoint for a workflow.
        
        Args:
            workflow_id: Workflow identifier
            checkpoint_name: Name for the checkpoint
            
        Returns:
            True if checkpoint was created
        """
        async with self._lock:
            if workflow_id not in self.workflows:
                raise ValueError(f"Workflow {workflow_id} not found")
                
            # Get current state
            current_state = copy.deepcopy(self.workflows[workflow_id]["state"])
            
            # Create checkpoint
            if workflow_id not in self.checkpoints:
                self.checkpoints[workflow_id] = {}
                
            self.checkpoints[workflow_id][checkpoint_name] = {
                "timestamp": datetime.now(),
                "state": current_state
            }
            
            logger.info(f"Created checkpoint '{checkpoint_name}' for workflow {workflow_id}")
            return True
            
    async def restore_checkpoint(self, workflow_id: str, checkpoint_name: str) -> Dict[str, Any]:
        """
        Restore workflow state from a checkpoint.
        
        Args:
            workflow_id: Workflow identifier
            checkpoint_name: Name of checkpoint to restore
            
        Returns:
            Restored workflow state
        """
        async with self._lock:
            if workflow_id not in self.workflows:
                raise ValueError(f"Workflow {workflow_id} not found")
                
            if workflow_id not in self.checkpoints or checkpoint_name not in self.checkpoints[workflow_id]:
                raise ValueError(f"Checkpoint '{checkpoint_name}' not found for workflow {workflow_id}")
                
            # Get checkpoint state
            checkpoint = self.checkpoints[workflow_id][checkpoint_name]
            checkpoint_state = copy.deepcopy(checkpoint["state"])
            
            # Update workflow with checkpoint state
            prev_state = copy.deepcopy(self.workflows[workflow_id]["state"])
            self.workflows[workflow_id]["state"] = checkpoint_state
            self.workflows[workflow_id]["status"] = "restored"
            
            # Record history
            self.history[workflow_id].append({
                "timestamp": datetime.now(),
                "step": f"restore_checkpoint_{checkpoint_name}",
                "prev_state": prev_state,
                "new_state": checkpoint_state
            })
            
            logger.info(f"Restored checkpoint '{checkpoint_name}' for workflow {workflow_id}")
            return checkpoint_state
            
    async def set_workflow_status(self, workflow_id: str, status: str) -> bool:
        """
        Set workflow status.
        
        Args:
            workflow_id: Workflow identifier
            status: New status
            
        Returns:
            True if status was updated
        """
        async with self._lock:
            if workflow_id not in self.workflows:
                raise ValueError(f"Workflow {workflow_id} not found")
                
            self.workflows[workflow_id]["status"] = status
            
            # Record history
            self.history[workflow_id].append({
                "timestamp": datetime.now(),
                "step": f"set_status_{status}",
                "status": status
            })
            
            logger.info(f"Set workflow {workflow_id} status to '{status}'")
            return True
            
    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get current workflow state and metadata.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            Workflow state and metadata
        """
        async with self._lock:
            if workflow_id not in self.workflows:
                raise ValueError(f"Workflow {workflow_id} not found")
                
            workflow = self.workflows[workflow_id]
            return {
                "id": workflow_id,
                "state": copy.deepcopy(workflow["state"]),
                "status": workflow["status"],
                "created_at": workflow["created_at"],
                "steps": copy.deepcopy(workflow["steps"]),
                "current_step": workflow["current_step"]
            }
            
    async def get_workflow_history(self, workflow_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get workflow history.
        
        Args:
            workflow_id: Workflow identifier
            limit: Maximum number of history entries to return (newest first)
            
        Returns:
            List of history entries
        """
        async with self._lock:
            if workflow_id not in self.workflows:
                raise ValueError(f"Workflow {workflow_id} not found")
                
            history = self.history.get(workflow_id, [])
            
            if limit is not None and limit > 0:
                # Return most recent entries
                history = history[-limit:]
                
            return copy.deepcopy(history)
            
    async def delete_workflow(self, workflow_id: str) -> bool:
        """
        Delete a workflow and its history.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            True if workflow was deleted
        """
        async with self._lock:
            if workflow_id not in self.workflows:
                return False
                
            # Remove workflow data
            del self.workflows[workflow_id]
            
            # Remove history
            if workflow_id in self.history:
                del self.history[workflow_id]
                
            # Remove checkpoints
            if workflow_id in self.checkpoints:
                del self.checkpoints[workflow_id]
                
            logger.info(f"Deleted workflow {workflow_id}")
            return True
