"""
ExecutionAgent: Responsible for script execution and verification.
"""
import logging
from typing import Dict, Any, Optional

from ..core.agents.base_agent import BaseAgent
from ..core.message_bus import MessageBus
from ..core.state import WorkflowState
from ..execution.executor import ScriptExecutor
from ..verification.verifier import Verifier
from ..rollback.recovery import RecoveryManager

logger = logging.getLogger(__name__)

class ExecutionAgent(BaseAgent):
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
