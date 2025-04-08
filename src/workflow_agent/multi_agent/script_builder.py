"""
ScriptBuilderAgent: Responsible for generating and validating scripts.
"""
import logging
from typing import Dict, Any, Optional

from ..core.message_bus import MessageBus
from ..core.state import WorkflowState
from ..core.agents import BaseAgent
from ..scripting.generator import ScriptGenerator
from ..scripting.validator import ScriptValidator

logger = logging.getLogger(__name__)

class ScriptBuilderAgent(BaseAgent):
    """
    Agent responsible for script generation and validation.
    """
    
    def __init__(self, message_bus: MessageBus):
        super().__init__(message_bus, "ScriptBuilderAgent")
        self.generator = ScriptGenerator()
        self.validator = ScriptValidator()
        
        # Register handlers for events
        self.register_handler("generate_script", self._handle_generate_script)
        self.register_handler("validate_script", self._handle_validate_script)
    
    async def _handle_generate_script(self, message: Dict[str, Any]) -> None:
        """Handle generate script request."""
        workflow_id = message["workflow_id"]
        state_dict = message["state"]
        config = message.get("config")
        try:
            state = WorkflowState(**state_dict)
            state = await self._apply_optimizations(state)
            gen_result = await self.generator.generate_script(state, config)
            if "error" in gen_result:
                await self.publish("error", {
                    "workflow_id": workflow_id,
                    "error": gen_result["error"],
                    "state": state.model_dump()
                })
                return
                
            # Update state with generated script
            state = state.set_script(gen_result.get("script", ""))
            if "template_key" in gen_result:
                state = state.evolve(template_key=gen_result.get("template_key"))
                
            logger.info(f"Generated script for {state.action} on {state.target_name}")
            
            # Publish success event
            await self.publish("script_generated", {
                "workflow_id": workflow_id,
                "state": state.model_dump()
            })
        except Exception as e:
            logger.error(f"Error generating script: {e}")
            await self.publish("error", {
                "workflow_id": workflow_id,
                "error": f"Error generating script: {str(e)}"
            })
    
    async def _handle_validate_script(self, message: Dict[str, Any]) -> None:
        """Handle validate script request."""
        workflow_id = message["workflow_id"]
        state_dict = message["state"]
        config = message.get("config")
        try:
            state = WorkflowState(**state_dict)
            validation_result = await self.validator.validate_script(state, config)
            
            if "error" in validation_result:
                await self.publish("error", {
                    "workflow_id": workflow_id,
                    "error": validation_result["error"],
                    "state": state.model_dump()
                })
                return
                
            # Add any warnings
            if "warnings" in validation_result:
                for warning in validation_result["warnings"]:
                    state = state.add_warning(warning)
                    
            logger.info(f"Validated script for {state.action} on {state.target_name}")
            
            # Publish success event
            await self.publish("script_validated", {
                "workflow_id": workflow_id,
                "state": state.model_dump()
            })
        except Exception as e:
            logger.error(f"Error validating script: {e}")
            await self.publish("error", {
                "workflow_id": workflow_id,
                "error": f"Error validating script: {str(e)}"
            })
    
    async def _apply_optimizations(self, state: WorkflowState) -> WorkflowState:
        """Apply optimizations to the state based on system context."""
        if not state.system_context:
            return state
            
        # Get platform information
        platform = state.system_context.get("platform", {}).get("system", "").lower()
        package_managers = state.system_context.get("package_managers", {})
        
        # Initialize template_data if needed
        template_data = dict(state.template_data or {})
        template_data["platform"] = platform
        
        # Determine package manager based on platform
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
            template_data["package_manager"] = package_manager
            
        # Update state with optimized template_data
        return state.evolve(template_data=template_data)
