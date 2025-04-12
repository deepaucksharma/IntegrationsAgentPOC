"""
ExecutionAgent: Responsible for script execution and verification.
Implements the ExecutionAgentInterface from the multi-agent architecture.
"""
import logging
from typing import Dict, Any, Optional, List

from .interfaces import ExecutionAgentInterface
from ..core.message_bus import MessageBus
from ..core.state import WorkflowState
from ..execution.executor import ScriptExecutor
from ..verification.verifier import Verifier
from ..rollback.recovery import RecoveryManager
from ..error.handler import handle_safely_async

logger = logging.getLogger(__name__)

class ExecutionAgent(ExecutionAgentInterface):
    """
    Agent responsible for script execution and verification.
    """
    
    def __init__(self, message_bus: MessageBus):
        super().__init__(message_bus, "ExecutionAgent")
        self.executor = ScriptExecutor()
        self.verifier = Verifier()
        self.recovery = RecoveryManager()
        
        # Register message handlers
        self.register_handler("execute_script", self._handle_execute_script)
        self.register_handler("verify_result", self._handle_verify_result)
    
    async def initialize(self) -> None:
        """Initialize the execution agent."""
        await super().initialize()
        logger.info("Initializing script executor...")
        await self.executor.initialize()
        logger.info("ExecutionAgent initialization complete")
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Starting ExecutionAgent cleanup...")
        logger.debug("Cleaning up script executor...")
        await self.executor.cleanup()
        logger.debug("Cleaning up recovery manager...")
        await self.recovery.cleanup()
        await super().cleanup()
        logger.info("ExecutionAgent cleanup complete")
    
    async def _handle_execute_script(self, message: Dict[str, Any]) -> None:
        workflow_id = message["workflow_id"]
        state_dict = message["state"]
        config = message.get("config")
        try:
            state = WorkflowState(**state_dict)
            logger.info("[ExecutionAgent] Starting script execution for %s action on %s (workflow_id: %s)", 
                       state.action, state.target_name, workflow_id)
            logger.debug("[ExecutionAgent] Execution configuration: %s", config)
            logger.debug("[ExecutionAgent] Initial state: %s", state.model_dump())
            
            exec_result = await self.executor.run_script(state, config)
            if "error" in exec_result:
                logger.error("[ExecutionAgent] Execution error for %s: %s", state.target_name, exec_result["error"])
                state_dict = state.model_dump()
                state_dict["error"] = exec_result["error"]
                state = WorkflowState(**state_dict)
                logger.warning("[ExecutionAgent] Initiating rollback for %s due to execution error", state.target_name)
                
                rollback_result = await self.recovery.rollback_changes(state, config)
                if "error" in rollback_result:
                    logger.error("[ExecutionAgent] Rollback failed for %s: %s", state.target_name, rollback_result["error"])
                    warnings = list(state.warnings)
                    warnings.append(f"Rollback failed: {rollback_result['error']}")
                    state_dict = state.model_dump()
                    state_dict["warnings"] = warnings
                    state = WorkflowState(**state_dict)
                else:
                    logger.info("[ExecutionAgent] Rollback successful for %s", state.target_name)
                
                await self.publish("execution_complete", {
                    "workflow_id": workflow_id,
                    "state": state.model_dump(),
                    "status": "failed"
                })
                logger.debug("[ExecutionAgent] Published execution failure for workflow %s", workflow_id)
                return
            
            # Update state with execution results
            state_dict = state.model_dump()
            for key in ["output", "metrics", "changes", "transaction_id", "execution_id"]:
                if key in exec_result:
                    logger.debug("[ExecutionAgent] Setting %s in state: %s", key, exec_result[key])
                    state_dict[key] = exec_result[key]
            
            state = WorkflowState(**state_dict)
            logger.info("[ExecutionAgent] Script execution successful for %s (workflow_id: %s)", state.target_name, workflow_id)
            logger.debug("[ExecutionAgent] Final execution state: %s", state.model_dump())
            
            await self.publish("execution_complete", {
                "workflow_id": workflow_id,
                "state": state.model_dump(),
                "status": "success"
            })
            logger.debug("[ExecutionAgent] Published execution success for workflow %s", workflow_id)
        except Exception as e:
            logger.error(f"Error executing script: {e}")
            await self.publish("error", {
                "workflow_id": workflow_id,
                "error": f"Error executing script: {str(e)}"
            })
    
    # Implement ExecutionAgentInterface required methods
    @handle_safely_async
    async def execute_task(self, task: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a specific task and return results.
        
        Args:
            task: Task specification including script, parameters and action
            context: Additional execution context
            
        Returns:
            Execution results
        """
        logger.info(f"Executing task: {task.get('name', 'unnamed')}")
        
        # Extract task information
        script = task.get("script")
        action = task.get("action", "execute")
        parameters = task.get("parameters", {})
        task_id = task.get("id", "unknown")
        
        # Create or use provided context
        exec_context = context or {}
        
        # Create a state object for execution
        state_dict = {
            "script": script,
            "action": action,
            "parameters": parameters,
            "task_id": task_id,
            "integration_type": task.get("integration_type", "unknown"),
            "target_name": task.get("target_name", "unknown")
        }
        
        # Add any additional context to state
        for key, value in exec_context.items():
            if key not in state_dict:
                state_dict[key] = value
                
        state = WorkflowState(**state_dict)
        
        # Execute the script
        try:
            config = exec_context.get("config", {})
            exec_result = await self.executor.run_script(state, config)
            
            if "error" in exec_result:
                logger.error(f"Task execution failed: {exec_result['error']}")
                return {
                    "success": False,
                    "error": exec_result["error"],
                    "task_id": task_id,
                    "changes": exec_result.get("changes", [])
                }
            
            # Successful execution
            return {
                "success": True,
                "output": exec_result.get("output", ""),
                "task_id": task_id,
                "changes": exec_result.get("changes", []),
                "metrics": exec_result.get("metrics", {})
            }
        except Exception as e:
            logger.error(f"Error executing task: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "task_id": task_id
            }
    
    @handle_safely_async
    async def validate_execution(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the results of an execution.
        
        Args:
            execution_result: Results to validate
            
        Returns:
            Validation results
        """
        logger.info(f"Validating execution result for task: {execution_result.get('task_id', 'unknown')}")
        
        # Extract validation information
        task_id = execution_result.get("task_id", "unknown")
        changes = execution_result.get("changes", [])
        output = execution_result.get("output", "")
        
        # Check for success or errors
        if not execution_result.get("success", False):
            logger.warning(f"Validation skipped for failed execution: {execution_result.get('error', 'Unknown error')}")
            return {
                "valid": False,
                "error": f"Execution failed: {execution_result.get('error', 'Unknown error')}",
                "task_id": task_id
            }
        
        # Create a state object for validation
        state_dict = {
            "output": output,
            "changes": changes,
            "task_id": task_id,
            "integration_type": execution_result.get("integration_type", "unknown"),
            "target_name": execution_result.get("target_name", "unknown")
        }
        
        # Perform validation
        try:
            state = WorkflowState(**state_dict)
            verify_result = await self.verifier.verify(state_dict)
            
            if "error" in verify_result:
                logger.error(f"Validation error: {verify_result['error']}")
                return {
                    "valid": False,
                    "error": verify_result["error"],
                    "task_id": task_id
                }
            
            # Check for warnings
            warnings = []
            if "warning" in verify_result:
                warnings.append(verify_result["warning"])
            
            # Return successful validation
            return {
                "valid": True,
                "warnings": warnings,
                "validation_details": verify_result.get("details", {}),
                "task_id": task_id
            }
            
        except Exception as e:
            logger.error(f"Error during validation: {e}", exc_info=True)
            return {
                "valid": False,
                "error": str(e),
                "task_id": task_id
            }
    
    @handle_safely_async
    async def handle_execution_error(self, error: Exception, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle errors during task execution.
        
        Args:
            error: Exception that occurred
            task: Task that failed
            context: Execution context
            
        Returns:
            Error handling results including recovery action
        """
        logger.error(f"Handling execution error for task {task.get('id', 'unknown')}: {error}")
        
        # Extract task information
        task_id = task.get("id", "unknown")
        integration_type = task.get("integration_type", "unknown")
        target_name = task.get("target_name", "unknown")
        
        # Create a state object for recovery
        state_dict = {
            "error": str(error),
            "task_id": task_id,
            "integration_type": integration_type,
            "target_name": target_name
        }
        
        # Add any changes that might have been recorded
        changes = context.get("changes", [])
        if changes:
            state_dict["changes"] = changes
            
        state = WorkflowState(**state_dict)
        config = context.get("config", {})
            
        # Attempt recovery
        try:
            rb_result = await self.recovery.rollback_changes(state, config)
            
            if "error" in rb_result:
                logger.error(f"Recovery failed: {rb_result['error']}")
                return {
                    "recovered": False,
                    "error": f"Initial error: {error}. Recovery failed: {rb_result['error']}",
                    "task_id": task_id,
                    "action_taken": "attempted_rollback"
                }
            
            # Successful recovery
            logger.info(f"Successfully recovered from error via rollback")
            return {
                "recovered": True,
                "original_error": str(error),
                "task_id": task_id,
                "action_taken": "rollback",
                "recovery_details": rb_result.get("details", {})
            }
            
        except Exception as recovery_error:
            logger.error(f"Error during recovery attempt: {recovery_error}", exc_info=True)
            return {
                "recovered": False,
                "error": f"Initial error: {error}. Recovery error: {recovery_error}",
                "task_id": task_id,
                "action_taken": "failed_recovery_attempt"
            }
    
    async def _handle_verify_result(self, message: Dict[str, Any]) -> None:
        workflow_id = message["workflow_id"]
        state_dict = message["state"]
        config = message.get("config")
        verification_type = message.get("verification_type", "verify_result")
        
        try:
            state = WorkflowState(**state_dict)
            logger.info(f"[ExecutionAgent] Verifying {state.target_name} ({verification_type})")
            verify_result = await self.verifier.verify(state_dict)
            
            if "error" in verify_result:
                logger.error(f"[ExecutionAgent] Verification error: {verify_result['error']}")
                state_dict = state.model_dump()
                state_dict["error"] = verify_result["error"]
                state = WorkflowState(**state_dict)
                
                if verification_type == "verify_result":
                    logger.info(f"[ExecutionAgent] Attempting rollback due to verification failure")
                    rb_result = await self.recovery.rollback_changes(state, config)
                    if "error" in rb_result:
                        logger.error(f"[ExecutionAgent] Rollback failed: {rb_result['error']}")
                        warnings = list(state.warnings)
                        warnings.append(f"Rollback failed: {rb_result['error']}")
                        state_dict = state.model_dump()
                        state_dict["warnings"] = warnings
                        state = WorkflowState(**state_dict)
                    else:
                        logger.info(f"[ExecutionAgent] Rollback successful")
                
                await self.publish("verification_complete", {
                    "workflow_id": workflow_id,
                    "state": state.model_dump(),
                    "status": "failed"
                })
                return
            
            if "warning" in verify_result:
                warnings = list(state.warnings)
                warnings.append(verify_result["warning"])
                state_dict = state.model_dump()
                state_dict["warnings"] = warnings
                state = WorkflowState(**state_dict)
            
            logger.info(f"[ExecutionAgent] Verification successful for {state.target_name}")
            await self.publish("verification_complete", {
                "workflow_id": workflow_id,
                "state": state.model_dump(),
                "status": "success"
            })
        except Exception as e:
            logger.error(f"Error during verification: {e}")
            await self.publish("error", {
                "workflow_id": workflow_id,
                "error": f"Error during verification: {str(e)}"
            })
