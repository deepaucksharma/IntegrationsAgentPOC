"""
ExecutionAgent: Responsible for script execution and verification.
"""
import logging
from typing import Dict, Any, Optional
from ..core.message_bus import MessageBus
from ..core.state import WorkflowState
from ..execution.executor import ScriptExecutor
from ..verification.verifier import Verifier
from ..rollback.recovery import RecoveryManager

logger = logging.getLogger(__name__)

class ExecutionAgent:
    """
    Agent responsible for script execution and verification.
    """
    
    def __init__(self, message_bus: MessageBus):
        self.message_bus = message_bus
        self.executor = ScriptExecutor()
        self.verifier = Verifier()
        self.recovery = RecoveryManager()
    
    async def initialize(self) -> None:
        """Initialize the execution agent."""
        logger.info("Initializing ExecutionAgent...")
        logger.debug("Subscribing to message bus topics...")
        await self.message_bus.subscribe("execute_script", self._handle_execute_script)
        await self.message_bus.subscribe("verify_result", self._handle_verify_result)
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
            logger.debug("[ExecutionAgent] Initial state: %s", state.dict())
            
            exec_result = await self.executor.run_script(state, config)
            if "error" in exec_result:
                logger.error("[ExecutionAgent] Execution error for %s: %s", state.target_name, exec_result["error"])
                state.error = exec_result["error"]
                logger.warning("[ExecutionAgent] Initiating rollback for %s due to execution error", state.target_name)
                
                rollback_result = await self.recovery.rollback_changes(state, config)
                if "error" in rollback_result:
                    logger.error("[ExecutionAgent] Rollback failed for %s: %s", state.target_name, rollback_result["error"])
                    state.warnings.append(f"Rollback failed: {rollback_result['error']}")
                else:
                    logger.info("[ExecutionAgent] Rollback successful for %s", state.target_name)
                
                await self.message_bus.publish("execution_complete", {
                    "workflow_id": workflow_id,
                    "state": state.dict(),
                    "status": "failed"
                })
                logger.debug("[ExecutionAgent] Published execution failure for workflow %s", workflow_id)
                return
            
            for key in ["output", "metrics", "changes", "legacy_changes", "transaction_id", "execution_id"]:
                if key in exec_result:
                    logger.debug("[ExecutionAgent] Setting %s in state: %s", key, exec_result[key])
                    setattr(state, key, exec_result[key])
            
            logger.info("[ExecutionAgent] Script execution successful for %s (workflow_id: %s)", state.target_name, workflow_id)
            logger.debug("[ExecutionAgent] Final execution state: %s", state.dict())
            
            await self.message_bus.publish("execution_complete", {
                "workflow_id": workflow_id,
                "state": state.dict(),
                "status": "success"
            })
            logger.debug("[ExecutionAgent] Published execution success for workflow %s", workflow_id)
        except Exception as e:
            logger.error(f"Error executing script: {e}")
            await self.message_bus.publish("error", {
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
            verify_result = await self.verifier.verify_result(state, config)
            if "error" in verify_result:
                logger.error(f"[ExecutionAgent] Verification error: {verify_result['error']}")
                state.error = verify_result["error"]
                
                if verification_type == "verify_result":
                    logger.info(f"[ExecutionAgent] Attempting rollback due to verification failure")
                    rb_result = await self.recovery.rollback_changes(state, config)
                    if "error" in rb_result:
                        logger.error(f"[ExecutionAgent] Rollback failed: {rb_result['error']}")
                        state.warnings.append(f"Rollback failed: {rb_result['error']}")
                    else:
                        logger.info(f"[ExecutionAgent] Rollback successful")
                
                await self.message_bus.publish("verification_complete", {
                    "workflow_id": workflow_id,
                    "state": state.dict(),
                    "status": "failed"
                })
                return
            
            if "warning" in verify_result:
                state.warnings.append(verify_result["warning"])
            
            logger.info(f"[ExecutionAgent] Verification successful for {state.target_name}")
            await self.message_bus.publish("verification_complete", {
                "workflow_id": workflow_id,
                "state": state.dict(),
                "status": "success"
            })
        except Exception as e:
            logger.error(f"Error during verification: {e}")
            await self.message_bus.publish("error", {
                "workflow_id": workflow_id,
                "error": f"Error during verification: {str(e)}"
            })