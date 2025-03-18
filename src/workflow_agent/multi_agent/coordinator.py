"""
CoordinatorAgent: Central orchestrator that manages workflow across specialized agents.
"""
import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, List

from ..core.state import WorkflowState
from ..core.message_bus import MessageBus
from ..utils.system import get_system_context
from ..error.exceptions import WorkflowError

logger = logging.getLogger(__name__)

class CoordinatorAgent:
    """
    Coordinates all agents and manages workflow execution.
    """
    
    def __init__(self, message_bus: MessageBus):
        self.message_bus = message_bus
        self.active_workflows = {}
        self._workflow_events = {}
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize and subscribe to relevant topics."""
        await self.message_bus.subscribe("knowledge_retrieved", self._handle_knowledge_retrieved)
        await self.message_bus.subscribe("script_generated", self._handle_script_generated)
        await self.message_bus.subscribe("script_validated", self._handle_script_validated)
        await self.message_bus.subscribe("execution_complete", self._handle_execution_complete)
        await self.message_bus.subscribe("verification_complete", self._handle_verification_complete)
        await self.message_bus.subscribe("error", self._handle_error)
    
    async def start_workflow(self, input_state: Dict[str, Any] | WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start a new workflow based on the input state."""
        workflow_id = str(uuid.uuid4())
        
        try:
            if isinstance(input_state, dict):
                if "transaction_id" not in input_state:
                    input_state["transaction_id"] = workflow_id
                state = WorkflowState(**input_state)
            else:
                state = input_state
                if not state.transaction_id:
                    # Create a new state with the workflow_id as transaction_id
                    state_dict = state.dict()
                    state_dict["transaction_id"] = workflow_id
                    state = WorkflowState(**state_dict)
                
            if not state.system_context:
                state.system_context = get_system_context()
        except Exception as e:
            logger.error(f"Invalid input state: {e}")
            return {"error": str(e), "workflow_id": workflow_id}
        
        async with self._lock:
            self.active_workflows[workflow_id] = {
                "state": state,
                "config": config,
                "status": "started",
                "steps": [],
                "current_step": "initialization"
            }
            self._workflow_events[workflow_id] = asyncio.Event()
        
        workflow_plan = self._create_workflow_plan(state)
        await self._execute_next_step(workflow_id, workflow_plan)
        
        return {
            "status": "in_progress",
            "workflow_id": workflow_id,
            "message": f"Started {state.action} workflow for {state.target_name}"
        }
    
    async def wait_for_completion(self, workflow_id: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Wait for workflow completion and return the final result."""
        async with self._lock:
            if workflow_id not in self._workflow_events:
                return {"error": f"Workflow {workflow_id} not found"}
            event = self._workflow_events[workflow_id]
        
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            async with self._lock:
                if workflow_id in self.active_workflows:
                    workflow = self.active_workflows[workflow_id]
                    return workflow.get("state", {}).dict()
                return {"error": f"Workflow {workflow_id} result not found"}
        except asyncio.TimeoutError:
            return {"error": f"Workflow {workflow_id} timed out after {timeout} seconds"}
    
    def _create_workflow_plan(self, state: WorkflowState) -> List[str]:
        """Create a workflow plan based on the requested action."""
        if state.action == "install":
            return ["retrieve_knowledge", "generate_script", "validate_script", "execute_script", "verify_result"]
        elif state.action == "remove":
            return ["retrieve_knowledge", "generate_script", "validate_script", "execute_script", "verify_removal"]
        elif state.action == "verify":
            return ["retrieve_knowledge", "verify_standalone"]
        else:
            return ["retrieve_knowledge", "generate_script", "validate_script", "execute_script", "verify_result"]
    
    async def _execute_next_step(self, workflow_id: str, workflow_plan: List[str]) -> None:
        """Execute the next step in the workflow plan."""
        # Get workflow data under the lock
        current_step = None
        state = None
        config = None
        
        async with self._lock:
            if workflow_id not in self.active_workflows:
                logger.error(f"Workflow {workflow_id} not found")
                return
            workflow = self.active_workflows[workflow_id]
            current_step_index = len(workflow["steps"])
            if current_step_index >= len(workflow_plan):
                workflow["status"] = "completed"
                if workflow_id in self._workflow_events:
                    self._workflow_events[workflow_id].set()
                return
            current_step = workflow_plan[current_step_index]
            workflow["current_step"] = current_step
            workflow["steps"].append(current_step)
            state = workflow["state"]
            config = workflow["config"]
        
        # Execute step outside the lock to avoid deadlock
        logger.info(f"[Coordinator] Executing step: {current_step} for workflow {workflow_id}")
        try:
            if current_step == "retrieve_knowledge":
                await self.message_bus.publish("retrieve_knowledge", {
                    "workflow_id": workflow_id,
                    "state": state.dict(),
                    "config": config
                })
            elif current_step == "generate_script":
                await self.message_bus.publish("generate_script", {
                    "workflow_id": workflow_id,
                    "state": state.dict(),
                    "config": config
                })
            elif current_step == "validate_script":
                await self.message_bus.publish("validate_script", {
                    "workflow_id": workflow_id,
                    "state": state.dict(),
                    "config": config
                })
            elif current_step == "execute_script":
                await self.message_bus.publish("execute_script", {
                    "workflow_id": workflow_id,
                    "state": state.dict(),
                    "config": config
                })
            elif current_step in ["verify_result", "verify_removal", "verify_standalone"]:
                await self.message_bus.publish("verify_result", {
                    "workflow_id": workflow_id,
                    "state": state.dict(),
                    "config": config,
                    "verification_type": current_step
                })
            else:
                await self.message_bus.publish("error", {
                    "workflow_id": workflow_id,
                    "error": f"Unknown step: {current_step}"
                })
        except Exception as e:
            logger.exception(f"Error executing step {current_step}: {e}")
            await self.message_bus.publish("error", {
                "workflow_id": workflow_id,
                "error": f"Error in {current_step}: {str(e)}"
            })
    
    async def _handle_knowledge_retrieved(self, message: Dict[str, Any]) -> None:
        workflow_id = message["workflow_id"]
        workflow_plan = None
        
        async with self._lock:
            if workflow_id not in self.active_workflows:
                logger.error(f"Workflow {workflow_id} not found")
                return
            workflow = self.active_workflows[workflow_id]
            if "state" in message:
                workflow["state"] = WorkflowState(**message["state"])
            workflow_plan = self._create_workflow_plan(workflow["state"])
        
        # Execute next step outside the lock
        await self._execute_next_step(workflow_id, workflow_plan)
    
    async def _handle_script_generated(self, message: Dict[str, Any]) -> None:
        workflow_id = message["workflow_id"]
        workflow_plan = None
        
        async with self._lock:
            if workflow_id not in self.active_workflows:
                logger.error(f"Workflow {workflow_id} not found")
                return
            workflow = self.active_workflows[workflow_id]
            if "state" in message:
                workflow["state"] = WorkflowState(**message["state"])
            workflow_plan = self._create_workflow_plan(workflow["state"])
        
        # Execute next step outside the lock
        await self._execute_next_step(workflow_id, workflow_plan)
    
    async def _handle_script_validated(self, message: Dict[str, Any]) -> None:
        workflow_id = message["workflow_id"]
        workflow_plan = None
        
        async with self._lock:
            if workflow_id not in self.active_workflows:
                logger.error(f"Workflow {workflow_id} not found")
                return
            workflow = self.active_workflows[workflow_id]
            if "state" in message:
                workflow["state"] = WorkflowState(**message["state"])
            workflow_plan = self._create_workflow_plan(workflow["state"])
        
        # Execute next step outside the lock
        await self._execute_next_step(workflow_id, workflow_plan)
    
    async def _handle_execution_complete(self, message: Dict[str, Any]) -> None:
        workflow_id = message["workflow_id"]
        workflow_plan = None
        should_execute_next = True
        
        async with self._lock:
            if workflow_id not in self.active_workflows:
                logger.error(f"Workflow {workflow_id} not found")
                return
            workflow = self.active_workflows[workflow_id]
            if "state" in message:
                workflow["state"] = WorkflowState(**message["state"])
            if workflow["state"].error:
                workflow["status"] = "failed"
                if workflow_id in self._workflow_events:
                    self._workflow_events[workflow_id].set()
                should_execute_next = False
            else:
                workflow_plan = self._create_workflow_plan(workflow["state"])
        
        # Execute next step outside the lock if needed
        if should_execute_next:
            await self._execute_next_step(workflow_id, workflow_plan)
    
    async def _handle_verification_complete(self, message: Dict[str, Any]) -> None:
        workflow_id = message["workflow_id"]
        should_analyze_failure = False
        workflow_state = None
        workflow_config = None
        
        async with self._lock:
            if workflow_id not in self.active_workflows:
                logger.error(f"Workflow {workflow_id} not found")
                return
            workflow = self.active_workflows[workflow_id]
            if "state" in message:
                workflow["state"] = WorkflowState(**message["state"])
            if workflow["state"].error:
                should_analyze_failure = True
                workflow_state = workflow["state"].dict()
                workflow_config = workflow["config"]
                workflow["status"] = "failed"
            else:
                workflow["status"] = "completed"
            if workflow_id in self._workflow_events:
                self._workflow_events[workflow_id].set()
        
        # Publish analyze_failure outside the lock
        if should_analyze_failure:
            await self.message_bus.publish("analyze_failure", {
                "workflow_id": workflow_id,
                "state": workflow_state,
                "config": workflow_config,
                "error": workflow_state.get("error")
            })
    
    async def _handle_error(self, message: Dict[str, Any]) -> None:
        workflow_id = message.get("workflow_id")
        error = message.get("error", "Unknown error")
        workflow_state = None
        workflow_config = None
        
        if not workflow_id:
            logger.error(f"Error without workflow ID: {error}")
            return
            
        async with self._lock:
            if workflow_id not in self.active_workflows:
                logger.error(f"Workflow {workflow_id} not found for error: {error}")
                return
            workflow = self.active_workflows[workflow_id]
            workflow["status"] = "failed"
            if "state" in workflow:
                workflow["state"].error = error
                workflow_state = workflow["state"].dict()
                workflow_config = workflow["config"]
        
        # Publish analyze_failure outside the lock
        await self.message_bus.publish("analyze_failure", {
            "workflow_id": workflow_id,
            "state": workflow_state,
            "config": workflow_config,
            "error": error
        })
