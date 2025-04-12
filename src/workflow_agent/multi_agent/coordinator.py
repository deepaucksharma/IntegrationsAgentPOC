"""
CoordinatorAgent: Central orchestrator that manages workflow across specialized agents.
Implements the MultiAgentBase interface and coordinates other specialized agents.
"""
import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
import copy

from .base import MultiAgentBase, MultiAgentMessage, MessageType, MessagePriority
from ..core.state import WorkflowState
from ..error.exceptions import WorkflowError, MultiAgentError
from ..error.handler import handle_safely_async
from .workflow_tracker import WorkflowTracker
from .recovery import WorkflowRecovery, RecoveryStrategy

logger = logging.getLogger(__name__)

class CoordinatorAgent(MultiAgentBase):
    """
    Coordinates all agents and manages workflow execution.
    Enhanced with improved workflow tracking and recovery capabilities.
    """
    
    def __init__(self):
        """Initialize the coordinator agent."""
        # Coordinator is self-referential
        super().__init__(self, "coordinator")
        
        # Initialize workflow tracking and recovery
        self.workflow_tracker = WorkflowTracker()
        self.recovery = WorkflowRecovery(coordinator=self)
        
        # Legacy support (will be maintained but only used internally)
        self.active_workflows = {}
        self._workflow_events = {}
        self._lock = asyncio.Lock()
        
        # Register message handlers
        self.register_message_handler(MessageType.KNOWLEDGE_RESPONSE, self._handle_knowledge_response)
        self.register_message_handler(MessageType.EXECUTION_RESPONSE, self._handle_execution_response) 
        self.register_message_handler(MessageType.VERIFICATION_RESPONSE, self._handle_verification_response)
        self.register_message_handler(MessageType.ERROR_REPORT, self._handle_error_report)
        self.register_message_handler(MessageType.IMPROVEMENT_SUGGESTION, self._handle_improvement_suggestion)
        self.register_message_handler(MessageType.SCRIPT_GENERATION_RESPONSE, self._handle_script_generation_response)
        self.register_message_handler(MessageType.SCRIPT_VALIDATION_RESPONSE, self._handle_script_validation_response)
        
        # Agent registration
        self._registered_agents = {}
    
    async def register_agent(self, agent_id: str, capabilities: List[str]) -> bool:
        """
        Register an agent with the coordinator.
        
        Args:
            agent_id: Unique identifier for the agent
            capabilities: List of capabilities the agent provides
            
        Returns:
            True if agent was registered successfully
        """
        async with self._lock:
            self._registered_agents[agent_id] = {
                "capabilities": capabilities,
                "status": "active",
                "registered_at": datetime.now()
            }
            logger.info(f"Agent {agent_id} registered with capabilities: {capabilities}")
            return True
    
    async def route_message(self, message: MultiAgentMessage, recipient: str) -> bool:
        """
        Route a message to the specified recipient.
        
        Args:
            message: Message to route
            recipient: Recipient ID
            
        Returns:
            True if message was routed successfully
        """
        logger.debug(f"Routing message from {message.sender} to {recipient}")
        
        # Add recipient to metadata
        message.metadata["recipient"] = recipient
        
        # Check if recipient is registered
        async with self._lock:
            is_registered = recipient in self._registered_agents
        
        # If not using message bus, but agent is registered, use direct routing
        if is_registered:
            # This would require agent reference storage, which is beyond current implementation
            logger.warning(f"Direct routing to {recipient} not implemented")
            return False
            
        # Otherwise, log that we don't have a route
        logger.warning(f"No route available to {recipient}")
        return False
            
    @handle_safely_async
    async def start_workflow(self, input_state: Dict[str, Any] | WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Start a new workflow based on the input state.
        
        Args:
            input_state: Initial workflow state
            config: Additional configuration
            
        Returns:
            Dictionary with workflow ID and status
        """
        workflow_id = str(uuid.uuid4())
        logger.info("Starting new workflow with ID: %s", workflow_id)
        
        try:
            # Prepare the workflow state
            if isinstance(input_state, dict):
                logger.debug("Converting input state dictionary to WorkflowState")
                if "transaction_id" not in input_state:
                    input_state["transaction_id"] = workflow_id
                if "status" not in input_state:
                    input_state["status"] = "pending"
                state = WorkflowState(**input_state)
            else:
                state = input_state
                if not state.transaction_id:
                    state.transaction_id = workflow_id
                
            logger.debug("Workflow state initialized: %s", state.model_dump() if hasattr(state, "model_dump") else state)
            
            if not hasattr(state, "model_dump"):
                # This is a safety check, we might need to adapt this for your specific WorkflowState implementation
                return {"error": "Invalid state object", "workflow_id": workflow_id}
                
        except Exception as e:
            logger.error("Failed to initialize workflow state: %s", e, exc_info=True)
            return {"error": str(e), "workflow_id": workflow_id}
        
        # Create workflow in the tracker
        await self.workflow_tracker.create_workflow(workflow_id, state.model_dump())
        
        # Store in active workflows (internal state management)
        async with self._lock:
            logger.debug("Registering workflow %s in active workflows", workflow_id)
            self.active_workflows[workflow_id] = {
                "id": workflow_id,
                "state": state,
                "config": config or {},
                "status": "pending",
                "steps": [],
                "current_step": None
            }
            self._workflow_events[workflow_id] = asyncio.Event()
        
        # Create initial workflow checkpoint
        await self.workflow_tracker.create_checkpoint(workflow_id, "initial")
        
        # Start the workflow
        workflow_plan = self._create_workflow_plan(state)
        logger.debug("Created workflow plan for %s: %s", workflow_id, workflow_plan)
        await self._execute_next_step(workflow_id, workflow_plan)
        
        return {
            "workflow_id": workflow_id,
            "status": "started",
            "transaction_id": state.transaction_id,
            "message": "Workflow started successfully"
        }
    
    async def wait_for_completion(self, workflow_id: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Wait for workflow completion and return the final result.
        
        Args:
            workflow_id: Workflow identifier
            timeout: Maximum time to wait (seconds)
            
        Returns:
            Final workflow state
        """
        async with self._lock:
            if workflow_id not in self._workflow_events:
                return {"error": f"Workflow {workflow_id} not found"}
            event = self._workflow_events[workflow_id]
        
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            
            # Get final workflow state from tracker
            try:
                workflow_data = await self.workflow_tracker.get_workflow(workflow_id)
                return workflow_data["state"]
            except ValueError:
                # Fall back to internal state management
                async with self._lock:
                    if workflow_id in self.active_workflows:
                        workflow = self.active_workflows[workflow_id]
                        return workflow.get("state", {}).model_dump()
                    return {"error": f"Workflow {workflow_id} result not found"}
            
        except asyncio.TimeoutError:
            return {"error": f"Workflow {workflow_id} timed out after {timeout} seconds"}
    
    async def rollback_changes(self, workflow_id: str, state: WorkflowState) -> Dict[str, Any]:
        """
        Roll back changes made during a workflow.
        
        Args:
            workflow_id: Workflow identifier
            state: Current workflow state
            
        Returns:
            Rollback result
        """
        logger.info(f"Rolling back changes for workflow {workflow_id}")
        
        # Check if there are changes to roll back
        changes = state.changes or []
        if not changes:
            logger.info(f"No changes to roll back for workflow {workflow_id}")
            return {
                "success": True,
                "message": "No changes to roll back",
                "state": state.model_dump() if hasattr(state, "model_dump") else state
            }
        
        # Prepare rollback message for execution agent
        try:
            # Send rollback request to execution agent
            rollback_response = await self.send_message(
                recipient="execution",
                message_type=MessageType.EXECUTION_REQUEST,
                content={
                    "workflow_id": workflow_id,
                    "state": state.model_dump() if hasattr(state, "model_dump") else state,
                    "changes": changes,
                    "operation": "rollback"
                },
                metadata={"priority": MessagePriority.HIGH},
                wait_for_response=True,
                response_timeout=300  # 5 minutes timeout
            )
            
            # Process response
            if rollback_response and isinstance(rollback_response.content, dict):
                content = rollback_response.content
                if "success" in content and content["success"]:
                    # Rollback successful
                    updated_state = content.get("state", state.model_dump() if hasattr(state, "model_dump") else state)
                    
                    # Update workflow state
                    await self.workflow_tracker.update_workflow(
                        workflow_id,
                        {"changes": [], "rollback": True},
                        "rollback"
                    )
                    
                    return {
                        "success": True,
                        "message": "Successfully rolled back changes",
                        "state": updated_state
                    }
                else:
                    # Rollback failed
                    error = content.get("error", "Unknown rollback error")
                    logger.error(f"Rollback failed for workflow {workflow_id}: {error}")
                    return {
                        "success": False,
                        "error": error,
                        "state": state.model_dump() if hasattr(state, "model_dump") else state
                    }
            else:
                # No valid response
                logger.error(f"No valid rollback response for workflow {workflow_id}")
                return {
                    "success": False,
                    "error": "No valid rollback response",
                    "state": state.model_dump() if hasattr(state, "model_dump") else state
                }
        except Exception as e:
            logger.error(f"Error during rollback for workflow {workflow_id}: {e}")
            return {
                "success": False,
                "error": f"Rollback error: {str(e)}",
                "state": state.model_dump() if hasattr(state, "model_dump") else state
            }
    
    async def retry_step(self, workflow_id: str, step: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retry a workflow step.
        
        Args:
            workflow_id: Workflow identifier
            step: Step to retry
            state: Current workflow state
            
        Returns:
            Retry result
        """
        logger.info(f"Retrying step {step} for workflow {workflow_id}")
        
        # Create workflow state if needed
        if not isinstance(state, WorkflowState):
            try:
                workflow_state = WorkflowState(**state)
            except Exception as e:
                logger.error(f"Error creating WorkflowState for retry: {e}")
                return {
                    "success": False,
                    "error": f"Invalid state for retry: {str(e)}",
                    "state": state
                }
        else:
            workflow_state = state
        
        # Get configuration
        config = None
        async with self._lock:
            if workflow_id in self.active_workflows:
                config = self.active_workflows[workflow_id].get("config")
        
        # Update workflow state for retry
        retry_state = workflow_state.model_dump()
        retry_state["retry_attempt"] = retry_state.get("retry_attempt", 0) + 1
        retry_state["retry_step"] = step
        
        # Update workflow tracker
        await self.workflow_tracker.update_workflow(
            workflow_id,
            retry_state,
            f"retry_{step}"
        )
        
        # Create checkpoint before retry
        await self.workflow_tracker.create_checkpoint(workflow_id, f"before_retry_{step}")
        
        # Execute the step again
        workflow_plan = self._create_workflow_plan(WorkflowState(**retry_state))
        
        # Find the position of the step in the plan
        try:
            step_index = workflow_plan.index(step)
            
            # Update workflow steps to reset to this point
            async with self._lock:
                if workflow_id in self.active_workflows:
                    workflow = self.active_workflows[workflow_id]
                    # Truncate steps to include everything before the retry step
                    workflow["steps"] = workflow["steps"][:step_index]
                    workflow["current_step"] = step
                    workflow["state"] = WorkflowState(**retry_state)
            
            # Execute the step
            await self._execute_step(workflow_id, step, WorkflowState(**retry_state), config)
            
            return {
                "success": True,
                "message": f"Retrying step {step}",
                "state": retry_state
            }
        except ValueError:
            logger.error(f"Step {step} not found in workflow plan for {workflow_id}")
            return {
                "success": False,
                "error": f"Step {step} not found in workflow plan",
                "state": retry_state
            }
        except Exception as e:
            logger.error(f"Error retrying step {step} for workflow {workflow_id}: {e}")
            return {
                "success": False,
                "error": f"Retry error: {str(e)}",
                "state": retry_state
            }
    
    async def continue_workflow(self, workflow_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Continue workflow execution despite errors.
        
        Args:
            workflow_id: Workflow identifier
            state: Current workflow state
            
        Returns:
            Continuation result
        """
        logger.info(f"Continuing workflow {workflow_id} despite errors")
        
        # Create workflow state if needed
        if not isinstance(state, WorkflowState):
            try:
                workflow_state = WorkflowState(**state)
            except Exception as e:
                logger.error(f"Error creating WorkflowState for continuation: {e}")
                return {
                    "success": False,
                    "error": f"Invalid state for continuation: {str(e)}",
                    "state": state
                }
        else:
            workflow_state = state
        
        # Update workflow tracker
        continue_state = workflow_state.model_dump()
        await self.workflow_tracker.update_workflow(
            workflow_id,
            continue_state,
            "continue_after_error"
        )
        
        # Create continuation checkpoint
        await self.workflow_tracker.create_checkpoint(workflow_id, "continue_point")
        
        # Update active workflows
        async with self._lock:
            if workflow_id in self.active_workflows:
                workflow = self.active_workflows[workflow_id]
                workflow["state"] = WorkflowState(**continue_state)
                current_step = workflow.get("current_step")
                
                # Determine next step
                workflow_plan = self._create_workflow_plan(workflow["state"])
                if current_step in workflow_plan:
                    step_index = workflow_plan.index(current_step)
                    if step_index + 1 < len(workflow_plan):
                        next_step = workflow_plan[step_index + 1]
                        
                        # Execute next step
                        await self._execute_next_step(workflow_id, workflow_plan)
                        
                        return {
                            "success": True,
                            "message": f"Continuing to step {next_step}",
                            "state": continue_state
                        }
                    else:
                        # Workflow already complete
                        workflow["status"] = "completed"
                        if workflow_id in self._workflow_events:
                            self._workflow_events[workflow_id].set()
                        
                        return {
                            "success": True,
                            "message": "Workflow already at final step",
                            "state": continue_state
                        }
                else:
                    # Current step not in plan, restart from beginning
                    logger.warning(f"Current step {current_step} not in plan, restarting workflow {workflow_id}")
                    workflow["steps"] = []
                    await self._execute_next_step(workflow_id, workflow_plan)
                    
                    return {
                        "success": True,
                        "message": "Restarting workflow",
                        "state": continue_state
                    }
            else:
                return {
                    "success": False,
                    "error": f"Workflow {workflow_id} not found",
                    "state": continue_state
                }
    
    async def abort_workflow(self, workflow_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Abort workflow execution.
        
        Args:
            workflow_id: Workflow identifier
            state: Current workflow state
            
        Returns:
            Abort result
        """
        logger.info(f"Aborting workflow {workflow_id}")
        
        # Update workflow tracker
        abort_state = state.copy() if isinstance(state, dict) else state.model_dump()
        abort_state["status"] = "aborted"
        abort_state["aborted_at"] = datetime.now().isoformat()
        
        # Update workflow tracker
        await self.workflow_tracker.update_workflow(
            workflow_id,
            abort_state,
            "abort"
        )
        
        # Update status
        await self.workflow_tracker.set_workflow_status(workflow_id, "aborted")
        
        # Update active workflows
        async with self._lock:
            if workflow_id in self.active_workflows:
                workflow = self.active_workflows[workflow_id]
                if isinstance(state, dict):
                    workflow["state"] = WorkflowState(**state)
                else:
                    workflow["state"] = state
                workflow["status"] = "aborted"
                
                # Set the event to release any waiters
                if workflow_id in self._workflow_events:
                    self._workflow_events[workflow_id].set()
        
        return {
            "success": True,
            "message": "Workflow aborted",
            "state": abort_state
        }
    
    def _create_workflow_plan(self, state: WorkflowState) -> List[str]:
        """
        Create a workflow plan based on the requested action.
        
        Args:
            state: Workflow state
            
        Returns:
            List of workflow steps
        """
        if state.action == "install":
            return ["retrieve_knowledge", "generate_script", "validate_script", "execute_script", "verify_result"]
        elif state.action == "remove":
            return ["retrieve_knowledge", "generate_script", "validate_script", "execute_script", "verify_removal"]
        elif state.action == "standalone":
            return ["retrieve_knowledge", "generate_script", "validate_script", "execute_script", "verify_result"]
        else:
            return ["retrieve_knowledge", "generate_script", "validate_script", "execute_script", "verify_result"]
    
    async def _execute_next_step(self, workflow_id: str, workflow_plan: List[str]) -> None:
        """
        Execute the next step in the workflow plan.
        
        Args:
            workflow_id: Workflow identifier
            workflow_plan: Workflow plan
        """
        # Get workflow data under the lock
        current_step = None
        state = None
        config = None
        
        async with self._lock:
            if workflow_id not in self.active_workflows:
                logger.error(f"Workflow {workflow_id} not found for executing next step")
                return
                
            workflow = self.active_workflows[workflow_id]
            steps = workflow["steps"]
            
            if steps:
                last_step_idx = workflow_plan.index(steps[-1]) if steps[-1] in workflow_plan else -1
                if last_step_idx + 1 >= len(workflow_plan):
                    logger.info(f"Workflow {workflow_id} has completed all steps")
                    workflow["status"] = "completed"
                    if workflow_id in self._workflow_events:
                        self._workflow_events[workflow_id].set()
                    return
                current_step = workflow_plan[last_step_idx + 1]
            else:
                # Start with the first step
                current_step = workflow_plan[0]
                
            # Update workflow
            workflow["steps"].append(current_step)
            workflow["current_step"] = current_step
            state = workflow["state"]
            config = workflow["config"]
        
        # Update the workflow tracker
        await self.workflow_tracker.update_workflow(
            workflow_id,
            state.model_dump() if hasattr(state, "model_dump") else state,
            current_step
        )
        
        # Execute step outside the lock to avoid deadlock
        await self._execute_step(workflow_id, current_step, state, config)
    
    async def _execute_step(self, workflow_id: str, current_step: str, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Execute a specific workflow step.
        
        Args:
            workflow_id: Workflow identifier
            current_step: Step to execute
            state: Current workflow state
            config: Additional configuration
        """
        logger.info(f"[Coordinator] Executing step: {current_step} for workflow {workflow_id}")
        
        # Create checkpoint before step execution
        try:
            await self.workflow_tracker.create_checkpoint(workflow_id, f"before_{current_step}")
        except Exception as e:
            logger.warning(f"Failed to create checkpoint: {e}")
        
        try:
            if current_step == "retrieve_knowledge":
                # Send message to knowledge agent
                await self.send_message(
                    recipient="knowledge",
                    message_type=MessageType.KNOWLEDGE_REQUEST,
                    content={
                        "query": f"Get information about {state.integration_type} integration for {state.action} action",
                        "state": state.model_dump(),
                        "config": config
                    },
                    metadata={"workflow_id": workflow_id}
                )
                
            elif current_step == "generate_script":
                # Send message to script builder agent
                await self.send_message(
                    recipient="script_builder",
                    message_type=MessageType.SCRIPT_GENERATION_REQUEST,
                    content={
                        "state": state.model_dump(),
                        "config": config
                    },
                    metadata={"workflow_id": workflow_id}
                )
                
            elif current_step == "validate_script":
                # Send message to script builder agent for validation
                await self.send_message(
                    recipient="script_builder",
                    message_type=MessageType.SCRIPT_VALIDATION_REQUEST,
                    content={
                        "state": state.model_dump(),
                        "config": config
                    },
                    metadata={"workflow_id": workflow_id}
                )
                
            elif current_step == "execute_script":
                # Send message to execution agent
                await self.send_message(
                    recipient="execution",
                    message_type=MessageType.EXECUTION_REQUEST,
                    content={
                        "task": {
                            "name": f"{state.action}_{state.integration_type}",
                            "script": state.script,
                            "action": state.action,
                            "parameters": state.parameters,
                            "id": workflow_id,
                            "integration_type": state.integration_type,
                            "target_name": state.target_name
                        },
                        "state": state.model_dump(),
                        "config": config
                    },
                    metadata={"workflow_id": workflow_id}
                )
                
            elif current_step in ["verify_result", "verify_removal", "verify_standalone"]:
                # Send message to verification agent
                await self.send_message(
                    recipient="verification",
                    message_type=MessageType.VERIFICATION_REQUEST,
                    content={
                        "verification_type": current_step,
                        "state": state.model_dump(),
                        "config": config
                    },
                    metadata={"workflow_id": workflow_id}
                )
                
            else:
                # Send error message for unknown step
                await self.send_message(
                    recipient="coordinator",
                    message_type=MessageType.ERROR_REPORT,
                    content={
                        "error": f"Unknown step: {current_step}",
                        "workflow_id": workflow_id
                    },
                    metadata={"workflow_id": workflow_id}
                )
                
        except Exception as e:
            logger.exception(f"Error executing step {current_step}: {e}")
            
            # Handle the error with recovery
            try:
                state_dict = state.model_dump() if hasattr(state, "model_dump") else state
                recovery_result = await self.recovery.handle_error(workflow_id, e, state_dict)
                
                if recovery_result.get("success", False):
                    logger.info(f"Successfully recovered from error in workflow {workflow_id}")
                    
                    # If recovery suggests continuing, do so
                    if recovery_result.get("strategy") == RecoveryStrategy.CONTINUE:
                        # Get workflow plan
                        workflow_plan = self._create_workflow_plan(state)
                        
                        # Continue to next step (skip current failed step)
                        current_index = workflow_plan.index(current_step)
                        if current_index + 1 < len(workflow_plan):
                            next_step = workflow_plan[current_index + 1]
                            
                            # Update workflow tracker
                            await self.workflow_tracker.update_workflow(
                                workflow_id, 
                                {"recovery_action": "skip_to_next_step"},
                                f"skip_to_{next_step}"
                            )
                            
                            # Update active workflow
                            async with self._lock:
                                if workflow_id in self.active_workflows:
                                    workflow = self.active_workflows[workflow_id]
                                    # Remove the failed step
                                    if workflow["steps"] and workflow["steps"][-1] == current_step:
                                        workflow["steps"].pop()
                            
                            # Execute next step
                            await self._execute_step(workflow_id, next_step, state, config)
                else:
                    # Recovery failed, send error report
                    await self.send_message(
                        recipient="coordinator",
                        message_type=MessageType.ERROR_REPORT,
                        content={
                            "workflow_id": workflow_id,
                            "error": f"Error in {current_step} with failed recovery: {str(e)}"
                        },
                        metadata={"workflow_id": workflow_id, "error": True}
                    )
            except Exception as recovery_error:
                logger.error(f"Error during recovery handling: {recovery_error}")
                await self.send_message(
                    recipient="coordinator",
                    message_type=MessageType.ERROR_REPORT,
                    content={
                        "workflow_id": workflow_id,
                        "error": f"Error in {current_step}: {str(e)}, Recovery error: {str(recovery_error)}"
                    },
                    metadata={"workflow_id": workflow_id, "error": True}
                )
    
    # Message handlers
    
    async def _handle_knowledge_response(self, message: MultiAgentMessage) -> None:
        """
        Handle knowledge response messages.
        
        Args:
            message: Knowledge response message
        """
        logger.info(f"Received knowledge response from {message.sender}")
        content = message.content
        
        # Extract workflow ID from metadata
        workflow_id = message.metadata.get("workflow_id")
        if not workflow_id:
            logger.error("Knowledge response missing workflow ID")
            return
            
        # Update workflow with knowledge
        async with self._lock:
            if workflow_id not in self.active_workflows:
                logger.error(f"Workflow {workflow_id} not found")
                return
                
            workflow = self.active_workflows[workflow_id]
            
            # Update state with knowledge
            if "knowledge" in content:
                state_dict = workflow["state"].model_dump()
                knowledge = content["knowledge"]
                
                # Add knowledge to state
                if "template_data" not in state_dict:
                    state_dict["template_data"] = {}
                    
                state_dict["template_data"]["knowledge"] = knowledge
                
                # Update state
                workflow["state"] = WorkflowState(**state_dict)
                
                # Update workflow tracker
                try:
                    await self.workflow_tracker.update_workflow(
                        workflow_id,
                        state_dict,
                        "knowledge_response"
                    )
                    await self.workflow_tracker.create_checkpoint(workflow_id, "after_knowledge_response")
                except Exception as e:
                    logger.warning(f"Failed to update workflow tracker: {e}")
                
            # Continue workflow
            workflow_plan = self._create_workflow_plan(workflow["state"])
            
        # Execute next step
        await self._execute_next_step(workflow_id, workflow_plan)
    
    async def _handle_script_generation_response(self, message: MultiAgentMessage) -> None:
        """
        Handle script generation response messages.
        
        Args:
            message: Script generation response message
        """
        logger.info(f"Received script generation response from {message.sender}")
        content = message.content
        
        # Extract workflow ID from metadata
        workflow_id = message.metadata.get("workflow_id")
        if not workflow_id:
            logger.error("Script generation response missing workflow ID")
            return
            
        # Update workflow with generated script
        async with self._lock:
            if workflow_id not in self.active_workflows:
                logger.error(f"Workflow {workflow_id} not found")
                return
                
            workflow = self.active_workflows[workflow_id]
            
            # Update state with generated script
            if "result" in content and "script" in content["result"]:
                state_dict = workflow["state"].model_dump()
                script = content["result"]["script"]
                
                # Update state with script
                state_dict["script"] = script
                
                # Add any additional generation data
                if "metadata" in content["result"]:
                    state_dict["script_metadata"] = content["result"]["metadata"]
                
                # Update state
                workflow["state"] = WorkflowState(**state_dict)
                
                # Update workflow tracker
                try:
                    await self.workflow_tracker.update_workflow(
                        workflow_id,
                        state_dict,
                        "script_generated"
                    )
                    await self.workflow_tracker.create_checkpoint(workflow_id, "after_script_generation")
                except Exception as e:
                    logger.warning(f"Failed to update workflow tracker: {e}")
            
            # Continue workflow
            workflow_plan = self._create_workflow_plan(workflow["state"])
            
        # Execute next step
        await self._execute_next_step(workflow_id, workflow_plan)
    
    async def _handle_script_validation_response(self, message: MultiAgentMessage) -> None:
        """
        Handle script validation response messages.
        
        Args:
            message: Script validation response message
        """
        logger.info(f"Received script validation response from {message.sender}")
        content = message.content
        
        # Extract workflow ID from metadata
        workflow_id = message.metadata.get("workflow_id")
        if not workflow_id:
            logger.error("Script validation response missing workflow ID")
            return
            
        # Determine if validation passed
        validation_success = message.metadata.get("success", False)
        validation_passed = content.get("result", {}).get("valid", False)
        
        async with self._lock:
            if workflow_id not in self.active_workflows:
                logger.error(f"Workflow {workflow_id} not found")
                return
                
            workflow = self.active_workflows[workflow_id]
            
            # Update state with validation results
            state_dict = workflow["state"].model_dump()
            if "result" in content:
                state_dict["script_validation"] = content["result"]
                
            # If validation failed, set error
            if not validation_success or not validation_passed:
                validation_errors = content.get("result", {}).get("errors", [])
                error_msg = f"Script validation failed: {', '.join(validation_errors)}" if validation_errors else "Script validation failed"
                state_dict["error"] = error_msg
                workflow["status"] = "failed"
                if workflow_id in self._workflow_events:
                    self._workflow_events[workflow_id].set()
                    
                # Update workflow tracker
                try:
                    await self.workflow_tracker.update_workflow(
                        workflow_id,
                        state_dict,
                        "script_validation_failed"
                    )
                    await self.workflow_tracker.create_checkpoint(workflow_id, "failed_validation")
                    await self.workflow_tracker.set_workflow_status(workflow_id, "failed")
                except Exception as e:
                    logger.warning(f"Failed to update workflow tracker: {e}")
                    
                # Send to improvement agent
                await self.send_message(
                    recipient="improvement",
                    message_type=MessageType.IMPROVEMENT_SUGGESTION,
                    content={
                        "metrics": {
                            "integration_type": state_dict.get("integration_type", "unknown"),
                            "target_name": state_dict.get("target_name", "unknown"),
                            "action": state_dict.get("action", "unknown"),
                            "error_count": 1,
                            "success_rate": 0,
                            "error": error_msg
                        }
                    },
                    metadata={
                        "workflow_id": workflow_id,
                        "priority": MessagePriority.HIGH
                    }
                )
                
                return
                
            # Update state and continue workflow
            workflow["state"] = WorkflowState(**state_dict)
            
            # Update workflow tracker
            try:
                await self.workflow_tracker.update_workflow(
                    workflow_id,
                    state_dict,
                    "script_validated"
                )
                await self.workflow_tracker.create_checkpoint(workflow_id, "after_validation")
            except Exception as e:
                logger.warning(f"Failed to update workflow tracker: {e}")
                
            # Continue workflow
            workflow_plan = self._create_workflow_plan(workflow["state"])
            
        # Execute next step
        await self._execute_next_step(workflow_id, workflow_plan)
    
    async def _handle_execution_response(self, message: MultiAgentMessage) -> None:
        """
        Handle execution response messages.
        
        Args:
            message: Execution response message
        """
        logger.info(f"Received execution response from {message.sender}")
        content = message.content
        
        # Extract workflow ID from metadata
        workflow_id = message.metadata.get("workflow_id")
        if not workflow_id:
            logger.error("Execution response missing workflow ID")
            return
            
        # Check execution success
        execution_success = message.metadata.get("success", False)
        workflow_plan = None
        should_execute_next = True
        
        async with self._lock:
            if workflow_id not in self.active_workflows:
                logger.error(f"Workflow {workflow_id} not found")
                return
                
            workflow = self.active_workflows[workflow_id]
            
            # Update state with execution results
            state_dict = workflow["state"].model_dump()
            
            if "result" in content:
                result = content["result"]
                
                # Update state based on result
                if "output" in result:
                    state_dict["output"] = result["output"]
                if "changes" in result:
                    state_dict["changes"] = result["changes"]
                if "metrics" in result:
                    state_dict["metrics"] = result["metrics"]
                    
            # If execution failed, set error
            if not execution_success and "error" in content:
                state_dict["error"] = content["error"]
                workflow["status"] = "failed"
                if workflow_id in self._workflow_events:
                    self._workflow_events[workflow_id].set()
                should_execute_next = False
                
            # Update state
            workflow["state"] = WorkflowState(**state_dict)
            
            # Update workflow tracker
            try:
                await self.workflow_tracker.update_workflow(
                    workflow_id,
                    state_dict,
                    "execution_response"
                )
                
                if execution_success:
                    await self.workflow_tracker.create_checkpoint(workflow_id, "after_execution_response")
                else:
                    await self.workflow_tracker.create_checkpoint(workflow_id, "failed_execution_response")
                    await self.workflow_tracker.set_workflow_status(workflow_id, "failed")
            except Exception as e:
                logger.warning(f"Failed to update workflow tracker: {e}")
            
            if should_execute_next:
                workflow_plan = self._create_workflow_plan(workflow["state"])
        
        # Execute next step if needed
        if should_execute_next:
            await self._execute_next_step(workflow_id, workflow_plan)
        else:
            # Try to recover from execution error
            try:
                recovery_result = await self.recovery.handle_error(
                    workflow_id,
                    content.get("error", "Execution failed"),
                    state_dict
                )
                
                if recovery_result.get("success", False):
                    logger.info(f"Successfully recovered from execution error in workflow {workflow_id}")
                    
                    # Update workflow state with recovery result
                    if "state" in recovery_result:
                        await self.workflow_tracker.update_workflow(
                            workflow_id,
                            recovery_result["state"],
                            "recovery_after_execution_error"
                        )
            except Exception as e:
                logger.error(f"Error during recovery from execution error: {e}")
    
    async def _handle_verification_response(self, message: MultiAgentMessage) -> None:
        """
        Handle verification response messages.
        
        Args:
            message: Verification response message
        """
        logger.info(f"Received verification response from {message.sender}")
        content = message.content
        
        # Extract workflow ID from metadata
        workflow_id = message.metadata.get("workflow_id")
        if not workflow_id:
            logger.error("Verification response missing workflow ID")
            return
            
        # Check verification success
        verification_success = message.metadata.get("success", False)
        verification_passed = message.metadata.get("passed", False)
        
        async with self._lock:
            if workflow_id not in self.active_workflows:
                logger.error(f"Workflow {workflow_id} not found")
                return
                
            workflow = self.active_workflows[workflow_id]
            
            # Update state with verification results
            state_dict = workflow["state"].model_dump()
            
            if "result" in content:
                result = content["result"]
                
                # Add verification result to state
                verification_type = content.get("verification_type", "verification")
                if "verification_results" not in state_dict:
                    state_dict["verification_results"] = {}
                    
                state_dict["verification_results"][verification_type] = result
                
            # If verification failed, set error
            if not verification_success or not verification_passed:
                if "error" in content:
                    state_dict["error"] = content["error"]
                elif not verification_passed:
                    state_dict["error"] = f"Verification failed: {result.get('reasoning', 'Unknown reason')}"
                    
                workflow["status"] = "failed"
                workflow_state = state_dict
                
                # Send to improvement agent
                await self.send_message(
                    recipient="improvement",
                    message_type=MessageType.IMPROVEMENT_SUGGESTION,
                    content={
                        "metrics": {
                            "integration_type": state_dict.get("integration_type", "unknown"),
                            "target_name": state_dict.get("target_name", "unknown"),
                            "action": state_dict.get("action", "unknown"),
                            "error_count": 1,
                            "success_rate": 0,
                            "error": state_dict.get("error")
                        }
                    },
                    metadata={
                        "workflow_id": workflow_id,
                        "priority": MessagePriority.HIGH
                    }
                )
            else:
                workflow["status"] = "completed"
                
            # Update state
            workflow["state"] = WorkflowState(**state_dict)
            
            # Update workflow tracker
            try:
                await self.workflow_tracker.update_workflow(
                    workflow_id,
                    state_dict,
                    "verification_response"
                )
                
                if verification_success and verification_passed:
                    await self.workflow_tracker.create_checkpoint(workflow_id, "successful_verification")
                    await self.workflow_tracker.set_workflow_status(workflow_id, "completed")
                else:
                    await self.workflow_tracker.create_checkpoint(workflow_id, "failed_verification")
                    await self.workflow_tracker.set_workflow_status(workflow_id, "failed")
            except Exception as e:
                logger.warning(f"Failed to update workflow tracker: {e}")
            
            # Set workflow event
            if workflow_id in self._workflow_events:
                self._workflow_events[workflow_id].set()
    
    async def _handle_error_report(self, message: MultiAgentMessage) -> None:
        """
        Handle error report messages.
        
        Args:
            message: Error report message
        """
        logger.error(f"Received error report from {message.sender}: {message.content.get('error', 'Unknown error')}")
        content = message.content
        
        # Extract workflow ID from metadata
        workflow_id = message.metadata.get("workflow_id")
        if not workflow_id:
            logger.error("Error report missing workflow ID")
            return
            
        error = content.get("error", "Unknown error")
        workflow_state = None
        
        async with self._lock:
            if workflow_id not in self.active_workflows:
                logger.error(f"Workflow {workflow_id} not found")
                return
                
            workflow = self.active_workflows[workflow_id]
            workflow["status"] = "failed"
            
            # Update state with error
            state_dict = workflow["state"].model_dump()
            state_dict["error"] = error
            workflow["state"] = WorkflowState(**state_dict)
            workflow_state = state_dict
            
            # Set workflow event
            if workflow_id in self._workflow_events:
                self._workflow_events[workflow_id].set()
                
        # Update workflow tracker
        try:
            await self.workflow_tracker.update_workflow(
                workflow_id,
                {"error": error, "status": "failed"},
                "error_report"
            )
            await self.workflow_tracker.set_workflow_status(workflow_id, "failed")
        except Exception as e:
            logger.warning(f"Failed to update workflow tracker: {e}")
                
        # Send to improvement agent
        await self.send_message(
            recipient="improvement",
            message_type=MessageType.IMPROVEMENT_SUGGESTION,
            content={
                "metrics": {
                    "integration_type": workflow_state.get("integration_type", "unknown"),
                    "target_name": workflow_state.get("target_name", "unknown"),
                    "action": workflow_state.get("action", "unknown"),
                    "error_count": 1,
                    "success_rate": 0,
                    "error": error
                }
            },
            metadata={
                "workflow_id": workflow_id,
                "priority": MessagePriority.HIGH
            }
        )
    
    async def _handle_improvement_suggestion(self, message: MultiAgentMessage) -> None:
        """
        Handle improvement suggestion messages.
        
        Args:
            message: Improvement suggestion message
        """
        logger.info(f"Received improvement suggestion from {message.sender}")
        # Currently, we just log the suggestions but don't act on them
        content = message.content
        
        if "analysis" in content and "suggestions" in content:
            analysis = content["analysis"]
            suggestions = content["suggestions"]
            
            logger.info(f"Improvement analysis: {analysis.get('description', 'No description')}")
            for suggestion in suggestions:
                logger.info(f"Improvement suggestion: {suggestion.get('description', 'No description')}")
    
    # MultiAgentBase abstract method implementation
    
    async def _handle_message(self, message: MultiAgentMessage) -> None:
        """
        Handle a message that has no specific handler.
        
        Args:
            message: Message to handle
        """
        logger.warning(f"Received message with no specific handler: {message.message_type}")
        # Create a generic response
        response = message.create_response(
            content={"status": "received", "handled": False, "reason": "no_handler"},
            metadata={"success": False}
        )
        await self.route_message(response, message.sender)
