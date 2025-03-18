"""
ScriptBuilderAgent: Responsible for generating and validating scripts.
"""
import logging
from typing import Dict, Any, Optional

from ..core.message_bus import MessageBus
from ..core.state import WorkflowState
from ..scripting.generator import ScriptGenerator
from ..scripting.validator import ScriptValidator

logger = logging.getLogger(__name__)

class ScriptBuilderAgent:
    """
    Agent responsible for script generation and validation.
    """
    
    def __init__(self, message_bus: MessageBus):
        self.message_bus = message_bus
        self.generator = ScriptGenerator()
        self.validator = ScriptValidator()
    
    async def initialize(self) -> None:
        """Initialize the script builder agent."""
        await self.message_bus.subscribe("generate_script", self._handle_generate_script)
        await self.message_bus.subscribe("validate_script", self._handle_validate_script)
    
    async def _handle_generate_script(self, message: Dict[str, Any]) -> None:
        workflow_id = message["workflow_id"]
        state_dict = message["state"]
        config = message.get("config")
        try:
            state = WorkflowState(**state_dict)
            state = await self._apply_optimizations(state)
            gen_result = await self.generator.generate_script(state, config)
            if "error" in gen_result:
                await self.message_bus.publish("error", {
                    "workflow_id": workflow_id,
                    "error": gen_result["error"],
                    "state": state.dict()
                })
                return
            state.script = gen_result.get("script")
            state.template_key = gen_result.get("template_key")
            state.optimized = True
            logger.info(f"[ScriptBuilderAgent] Generated script for {state.action} on {state.target_name}")
            await self.message_bus.publish("script_generated", {
                "workflow_id": workflow_id,
                "state": state.dict()
            })
        except Exception as e:
            logger.error(f"Error generating script: {e}")
            await self.message_bus.publish("error", {
                "workflow_id": workflow_id,
                "error": f"Error generating script: {str(e)}"
            })
    
    async def _handle_validate_script(self, message: Dict[str, Any]) -> None:
        workflow_id = message["workflow_id"]
        state_dict = message["state"]
        config = message.get("config")
        try:
            state = WorkflowState(**state_dict)
            validation_result = await self.validator.validate_script(state, config)
            if "error" in validation_result:
                await self.message_bus.publish("error", {
                    "workflow_id": workflow_id,
                    "error": validation_result["error"],
                    "state": state.dict()
                })
                return
            if "warnings" in validation_result:
                state.warnings.extend(validation_result["warnings"])
            logger.info(f"[ScriptBuilderAgent] Validated script for {state.action} on {state.target_name}")
            await self.message_bus.publish("script_validated", {
                "workflow_id": workflow_id,
                "state": state.dict()
            })
        except Exception as e:
            logger.error(f"Error validating script: {e}")
            await self.message_bus.publish("error", {
                "workflow_id": workflow_id,
                "error": f"Error validating script: {str(e)}"
            })
    
    async def _apply_optimizations(self, state: WorkflowState) -> WorkflowState:
        if not state.system_context:
            return state
        platform = state.system_context.get("platform", {}).get("system", "").lower()
        package_managers = state.system_context.get("package_managers", {})
        if not state.template_data:
            state.template_data = {}
        state.template_data["platform"] = platform
        package_manager = None
        if platform == "linux":
            if package_managers.get("apt"):
                package_manager = "apt-get"
            elif package_managers.get("yum"):
                package_manager = "yum"
            elif package_managers.get("dnf"):
                package_manager = "dnf"
            elif package_managers.get("zypper"):
                package_manager = "zypper"
        if package_manager:
            state.template_data["package_manager"] = package_manager
        return state