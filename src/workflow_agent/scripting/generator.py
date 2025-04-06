"""
Script generation for integration actions.
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from ..error.exceptions import TemplateError
from ..templates.manager import TemplateManager
from ..config.configuration import WorkflowConfiguration
from ..core.state import WorkflowState
from .validator import ScriptValidator

logger = logging.getLogger(__name__)

class ScriptGenerator:
    """Generates scripts for integration actions."""
    
    def __init__(self, config: WorkflowConfiguration, template_manager: TemplateManager):
        """
        Initialize script generator.
        
        Args:
            config: Workflow configuration
            template_manager: Template manager for rendering templates
        """
        self.config = config
        self.template_manager = template_manager
        self.validator = ScriptValidator(config)
        
    async def generate_script(self, state: WorkflowState) -> WorkflowState:
        """
        Generate a script based on workflow state.
        
        Args:
            state: Workflow state with template and parameters
            
        Returns:
            Updated workflow state with generated script
        """
        # Get template key from state or discover based on integration type
        template_key = state.template_key
        
        if not template_key:
            template_key = await self._discover_template_key(state)
            
        if not template_key:
            error_msg = f"No template found for {state.integration_type}/{state.action}/{state.target_name}"
            logger.error(error_msg)
            return state.set_error(error_msg)
            
        logger.info(f"Generating script using template: {template_key}")
        
        # Prepare template context
        context = self._prepare_template_context(state)
        
        # Render the template
        try:
            script = self.template_manager.render_template(template_key, context)
            
            if not script:
                error_msg = f"Failed to render template: {template_key}"
                logger.error(error_msg)
                return state.set_error(error_msg)
                
            # Validate the script
            validation_result = self.validator.validate(script)
            
            if not validation_result["valid"]:
                warnings = "\n".join(validation_result["warnings"])
                error_msg = f"Script validation failed:\n{warnings}"
                
                # Only fail if least privilege execution is enabled
                if self.config.least_privilege_execution:
                    logger.error(error_msg)
                    return state.set_error(error_msg)
                else:
                    logger.warning(error_msg)
                    state = state.add_warning(error_msg)
            
            # Store the script in state
            state = state.set_script(script)
            
            # Add diagnostics
            diagnostics = {
                "template_key": template_key,
                "script_size": len(script),
                "validation_warnings": validation_result.get("warnings", [])
            }
            
            state = state.evolve(
                template_data={
                    **state.template_data,
                    "script_diagnostics": diagnostics
                }
            )
            
            logger.info(f"Script generated successfully ({len(script)} bytes)")
            return state
            
        except Exception as e:
            logger.error(f"Error generating script: {e}", exc_info=True)
            return state.set_error(f"Error generating script: {str(e)}")
    
    async def _discover_template_key(self, state: WorkflowState) -> Optional[str]:
        """
        Discover the appropriate template key based on state.
        
        Args:
            state: Workflow state
            
        Returns:
            Template key or None if not found
        """
        # Try several options in order of specificity
        options = [
            f"{state.action}/{state.integration_type}/{state.target_name}",
            f"{state.action}/{state.integration_type}/default",
            f"{state.action}/default"
        ]
        
        # Check on-disk templates
        for option in options:
            logger.debug(f"Checking template: {option}")
            if self.template_manager.get_template(option):
                return option
                
        # If using an LLM, we can dynamically generate a template
        if self.config.script_generator == "llm" and hasattr(self, "_generate_llm_template"):
            logger.info("No static template found, generating with LLM")
            try:
                llm_template = await self._generate_llm_template(state)
                
                if llm_template:
                    # Store in a temporary location
                    template_path = Path(self.config.template_dir) / f"{state.action}/{state.integration_type}"
                    template_path.mkdir(parents=True, exist_ok=True)
                    
                    template_file = template_path / f"{state.target_name}.j2"
                    with open(template_file, "w") as f:
                        f.write(llm_template)
                        
                    # Reload templates
                    self.template_manager.reload_templates()
                    
                    return f"{state.action}/{state.integration_type}/{state.target_name}"
                    
            except Exception as e:
                logger.error(f"Error generating LLM template: {e}")
                
        return None
    
    def _prepare_template_context(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Prepare the template context from state.
        
        Args:
            state: Workflow state
            
        Returns:
            Template context dictionary
        """
        context = {
            "action": state.action,
            "target_name": state.target_name,
            "integration_type": state.integration_type,
            "execution_id": state.execution_id,
            "system_context": state.system_context
        }
        
        # Add parameters
        if state.parameters:
            context.update(state.parameters)
            
        # Add template data
        if state.template_data:
            context.update(state.template_data)
            
        return context
