"""
ScriptBuilderAgent: Responsible for generating and validating scripts.
"""
import logging
from typing import Dict, Any, Optional

from .interfaces import ScriptBuilderAgentInterface
from ..core.state import WorkflowState
from ..core.message_bus import MessageBus
from ..scripting.generator import ScriptGenerator
from ..scripting.validator import ScriptValidator

logger = logging.getLogger(__name__)

class ScriptBuilderAgent(ScriptBuilderAgentInterface):
    """
    Agent responsible for script generation and validation.
    Implements the ScriptBuilderAgentInterface from the multi-agent system.
    """
    
    def __init__(
        self, 
        message_bus: MessageBus,
        coordinator: Any = None,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            coordinator=coordinator or message_bus, 
            agent_id="ScriptBuilderAgent"
        )
        self.message_bus = message_bus
        self.generator = ScriptGenerator()
        self.validator = ScriptValidator()
        self.config = config or {}
        
        # Register handlers for events (legacy event-based system)
        self.register_handler("generate_script", self._handle_generate_script_legacy)
        self.register_handler("validate_script", self._handle_validate_script_legacy)
        
        # Register message-based handlers (new interface-based system)
        self.register_message_handler("generate_script", self._handle_generate_script_message)
        self.register_message_handler("validate_script", self._handle_validate_script_message)
    
    # ScriptBuilderAgentInterface implementation methods
    
    async def generate_script(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a script based on workflow state.
        
        Args:
            state: Current workflow state
            config: Additional configuration options
            
        Returns:
            Dictionary containing the generated script and related metadata
        """
        try:
            # Apply optimizations to the state
            optimized_state = await self._apply_optimizations(state)
            
            # Generate the script
            result = await self.generator.generate_script(optimized_state, config)
            
            if "error" not in result:
                logger.info(f"Generated script for {optimized_state.action} on {optimized_state.target_name}")
            else:
                logger.error(f"Error generating script: {result['error']}")
                
            return result
            
        except Exception as e:
            logger.error(f"Error in generate_script: {e}", exc_info=True)
            return {"error": f"Script generation failed: {str(e)}"}
    
    async def validate_script(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate a script for correctness and safety.
        
        Args:
            state: Current workflow state containing script
            config: Additional configuration options
            
        Returns:
            Validation results
        """
        try:
            # Validate the script
            result = await self.validator.validate_script(state, config)
            
            if "error" not in result:
                logger.info(f"Validated script for {state.action} on {state.target_name}")
            else:
                logger.error(f"Error validating script: {result['error']}")
                
            return result
            
        except Exception as e:
            logger.error(f"Error in validate_script: {e}", exc_info=True)
            return {"error": f"Script validation failed: {str(e)}"}
    
    async def optimize_script(self, state: WorkflowState, target_env: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize a script for a specific environment.
        
        Args:
            state: Current workflow state containing script
            target_env: Target environment details
            
        Returns:
            Optimization results including optimized script
        """
        try:
            # Apply environment-specific optimizations to the script
            optimized_state = await self._apply_optimizations(state, target_env)
            
            if not state.script:
                return {
                    "warning": "No script to optimize",
                    "state": optimized_state.model_dump() 
                }
            
            # Get the optimized script from the state
            optimized_script = optimized_state.script
            
            # Perform additional optimizations based on target environment
            # Here we would apply more advanced optimizations if needed
            
            logger.info(f"Optimized script for {optimized_state.action} on {optimized_state.target_name}")
            
            return {
                "optimized": True,
                "script": optimized_script,
                "state": optimized_state.model_dump(),
                "optimizations_applied": True
            }
            
        except Exception as e:
            logger.error(f"Error in optimize_script: {e}", exc_info=True)
            return {"error": f"Script optimization failed: {str(e)}"}
    
    # Message handlers for the new interface
    
    async def _handle_generate_script_message(self, message: Any) -> None:
        """
        Handle generate script request via message interface.
        
        Args:
            message: MultiAgentMessage containing the request
        """
        try:
            content = message.content
            state_dict = content.get("state", {})
            config = content.get("config", {})
            
            # Create workflow state
            state = WorkflowState(**state_dict) if isinstance(state_dict, dict) else state_dict
            
            # Generate script
            result = await self.generate_script(state, config)
            
            if "error" not in result:
                # Update state with generated script
                updated_state = state.set_script(result.get("script", ""))
                if "template_key" in result:
                    updated_state = updated_state.evolve(template_key=result.get("template_key"))
                
                # Create response
                response = message.create_response(
                    content={
                        "result": result,
                        "state": updated_state.model_dump()
                    },
                    metadata={"success": True}
                )
            else:
                # Create error response
                response = message.create_response(
                    content={
                        "error": result["error"],
                        "state": state.model_dump()
                    },
                    metadata={"success": False}
                )
            
            # Send response
            await self.coordinator.route_message(response, message.sender)
            
        except Exception as e:
            logger.error(f"Error handling generate script message: {e}", exc_info=True)
            
            # Send error response
            error_response = message.create_response(
                content={"error": str(e)},
                metadata={"success": False}
            )
            await self.coordinator.route_message(error_response, message.sender)
    
    async def _handle_validate_script_message(self, message: Any) -> None:
        """
        Handle validate script request via message interface.
        
        Args:
            message: MultiAgentMessage containing the request
        """
        try:
            content = message.content
            state_dict = content.get("state", {})
            config = content.get("config", {})
            
            # Create workflow state
            state = WorkflowState(**state_dict) if isinstance(state_dict, dict) else state_dict
            
            # Validate script
            result = await self.validate_script(state, config)
            
            if "error" not in result:
                updated_state = state
                
                # Add any warnings
                if "warnings" in result:
                    for warning in result["warnings"]:
                        updated_state = updated_state.add_warning(warning)
                
                # Create response
                response = message.create_response(
                    content={
                        "result": result,
                        "state": updated_state.model_dump()
                    },
                    metadata={"success": True}
                )
            else:
                # Create error response
                response = message.create_response(
                    content={
                        "error": result["error"],
                        "state": state.model_dump()
                    },
                    metadata={"success": False}
                )
            
            # Send response
            await self.coordinator.route_message(response, message.sender)
            
        except Exception as e:
            logger.error(f"Error handling validate script message: {e}", exc_info=True)
            
            # Send error response
            error_response = message.create_response(
                content={"error": str(e)},
                metadata={"success": False}
            )
            await self.coordinator.route_message(error_response, message.sender)
    
    # Legacy event-based handlers (for backward compatibility)
    
    async def _handle_generate_script_legacy(self, message: Dict[str, Any]) -> None:
        """Handle generate script request through legacy event system."""
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
    
    async def _handle_validate_script_legacy(self, message: Dict[str, Any]) -> None:
        """Handle validate script request through legacy event system."""
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
    
    # Helper methods
    
    async def _apply_optimizations(self, state: WorkflowState, target_env: Optional[Dict[str, Any]] = None) -> WorkflowState:
        """
        Apply optimizations to the state based on system context.
        
        Args:
            state: The workflow state to optimize
            target_env: Optional target environment information (if different from state.system_context)
            
        Returns:
            Optimized workflow state
        """
        # Use target_env if provided, otherwise use system_context from state
        system_context = target_env if target_env else state.system_context
        
        if not system_context:
            return state
            
        # Get platform information
        platform = system_context.get("platform", {}).get("system", "").lower()
        package_managers = system_context.get("package_managers", {})
        
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
    
    # MultiAgentBase abstract method implementation
    
    async def _handle_message(self, message: Any) -> None:
        """
        Handle a message that has no specific handler.
        
        Args:
            message: Message to handle
        """
        message_type = getattr(message, "message_type", None)
        
        if message_type == "generate_script":
            await self._handle_generate_script_message(message)
        elif message_type == "validate_script":
            await self._handle_validate_script_message(message)
        else:
            logger.warning(f"No handler for message type: {message_type}")
    
    # Publishing methods for legacy support
    
    async def publish(self, event: str, data: Dict[str, Any]) -> None:
        """
        Publish an event to the message bus (legacy method).
        
        Args:
            event: Event name
            data: Event data
        """
        if hasattr(self, "message_bus") and self.message_bus:
            await self.message_bus.publish(event, data)
        else:
            logger.warning(f"Cannot publish event {event}: no message bus available")
