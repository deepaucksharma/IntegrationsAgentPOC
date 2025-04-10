"""
Script generation agent implementation.
"""
import logging
from typing import Dict, Any, Optional

from .base_agent import BaseAgent, AgentConfig, AgentCapability, AgentContext, AgentResult
from ..error.exceptions import AgentError
from ..core.state import WorkflowState
from ..templates import TemplateManager

logger = logging.getLogger(__name__)

class ScriptGenerationAgent(BaseAgent):
    """
    Agent for generating scripts using templates.
    """
    
    def __init__(self, template_manager: TemplateManager, config: Optional[AgentConfig] = None):
        """
        Initialize the script generation agent.
        
        Args:
            template_manager: Template manager for rendering templates
            config: Optional agent configuration
        """
        super().__init__(config)
        self.template_manager = template_manager
        
    def _register_capabilities(self) -> None:
        """Register agent capabilities."""
        self.capabilities.add(AgentCapability.SCRIPT_GENERATION)
        
    async def _validate_agent_context(self, context: AgentContext) -> bool:
        """
        Validate agent-specific context requirements.
        
        Args:
            context: Agent execution context
            
        Returns:
            True if context is valid
            
        Raises:
            AgentError: If context is invalid
        """
        # Ensure required parameters are present
        state = context.workflow_state
        
        if not state.integration_type:
            raise AgentError("Integration type is required")
            
        if not state.action:
            raise AgentError("Action is required")
            
        return True
        
    async def _execute_agent_logic(self, context: AgentContext) -> AgentResult:
        """
        Generate a script using templates.
        
        Args:
            context: Agent execution context
            
        Returns:
            Agent result with generated script
        """
        state = context.workflow_state
        
        # Determine template key
        template_key = self._determine_template_key(state)
        if not template_key:
            return AgentResult.error_result(
                workflow_state=state,
                error_message=f"No template found for {state.integration_type}/{state.action}"
            )
        
        logger.info(f"Generating script using template: {template_key}")
        
        # Prepare context
        template_context = self._prepare_template_context(state)
        
        # Render template
        try:
            script = self.template_manager.render_template(template_key, template_context)
            
            if not script:
                return AgentResult.error_result(
                    workflow_state=state,
                    error_message=f"Failed to render template: {template_key}"
                )
                
            # Update state with script
            new_state = state.set_script(script)
            
            # Add diagnostics
            diagnostics = {
                "template_key": template_key,
                "script_size": len(script)
            }
            
            new_state = new_state.evolve(
                template_data={
                    **new_state.template_data,
                    "script_diagnostics": diagnostics
                }
            )
            
            logger.info(f"Script generated successfully ({len(script)} bytes)")
            
            return AgentResult.success_result(
                workflow_state=new_state,
                output=script,
                metadata={"template_key": template_key}
            )
            
        except Exception as e:
            error_msg = f"Error generating script: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            return AgentResult.error_result(
                workflow_state=state,
                error_message=error_msg
            )
            
    def _determine_template_key(self, state: WorkflowState) -> Optional[str]:
        """
        Determine the appropriate template key for the state.
        
        Args:
            state: Workflow state
            
        Returns:
            Template key or None if not found
        """
        # Check if template key is specified in state
        if state.template_key:
            return state.template_key
            
        # Try to resolve template path
        return self.template_manager.resolve_template_path(
            state.integration_type,
            state.action,
            state.target_name
        )
        
    def _prepare_template_context(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Prepare the template context from state.
        
        Args:
            state: Workflow state
            
        Returns:
            Template context dictionary
        """
        # Create a baseline context with key information
        context = {
            "action": state.action,
            "target_name": state.target_name,
            "integration_type": state.integration_type,
            "execution_id": state.execution_id,
            "system_context": state.system_context,
            "parameters": state.parameters  # Add parameters as a nested object
        }
        
        # Add parameters directly to support both direct access and nested access
        if state.parameters:
            context.update(state.parameters)
            
        # Add template data
        if state.template_data:
            context.update(state.template_data)
            
        # Make sure all templates have access to default directory parameters
        if "install_dir" not in context and "parameters" in context:
            context["install_dir"] = context["parameters"].get("install_dir", "")
        if "config_path" not in context and "parameters" in context:
            context["config_path"] = context["parameters"].get("config_path", "")
        if "log_path" not in context and "parameters" in context:
            context["log_path"] = context["parameters"].get("log_path", "")
        
        return context
