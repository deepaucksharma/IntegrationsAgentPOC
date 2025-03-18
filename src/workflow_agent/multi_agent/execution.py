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
        await self.message_bus.subscribe("execute_script", self._handle_execute_script)
        await self.message_bus.subscribe("verify_result", self._handle_verify_result)
        await self.executor.initialize()
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.executor.cleanup()
        await self.recovery.cleanup()
    
    async def _handle_execute_script(self, message: Dict[str, Any]) -> None:
        workflow_id = message["workflow_id"]
        state_dict = message["state"]
        config = message.get("config")
        try:
            state = WorkflowState(**state_dict)
            logger.info(f"[ExecutionAgent] Executing script for {state.action} on {state.target_name}")
            exec_result = await self.executor.run_script(state, config)
            if "error" in exec_result:
                logger.error(f"[ExecutionAgent] Execution error: {exec_result['error']}")
                state.error = exec_result["error"]
                logger.info(f"[ExecutionAgent] Attempting rollback for {state.target_name}")
                rollback_result = await self.recovery.rollback_changes(state, config)
                if "error" in rollback_result:
                    logger.error(f"[ExecutionAgent] Rollback failed: {rollback_result['error']}")
                    state.warnings.append(f"Rollback failed: {rollback_result['error']}")
                else:
                    logger.info(f"[ExecutionAgent] Rollback successful for {state.target_name}")
                await self.message_bus.publish("execution_complete", {
                    "workflow_id": workflow_id,
                    "state": state.dict(),
                    "status": "failed"
                })
                return
            
            for key in ["output", "metrics", "changes", "legacy_changes", "transaction_id", "execution_id"]:
                if key in exec_result:
                    setattr(state, key, exec_result[key])
            
            logger.info(f"[ExecutionAgent] Script execution successful for {state.target_name}")
            await self.message_bus.publish("execution_complete", {
                "workflow_id": workflow_id,
                "state": state.dict(),
                "status": "success"
            })
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