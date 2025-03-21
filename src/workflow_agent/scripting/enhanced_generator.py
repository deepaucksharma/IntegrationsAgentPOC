"""Integration of LLM script generation into the workflow agent."""
import logging
import asyncio
from typing import Dict, Any, Optional
import os
from datetime import datetime

from ..core.state import WorkflowState
from ..error.exceptions import ScriptError, ErrorContext
from .generator import ScriptGenerator
from .llm_generator import LLMScriptGenerator
from ..config.configuration import ensure_workflow_config

logger = logging.getLogger(__name__)

class EnhancedScriptGenerator(ScriptGenerator):
    """Enhanced script generator that combines template and LLM approaches."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the enhanced script generator."""
        super().__init__()
        self.config = config or {}
        self.llm_generator = None
        self.template_generator = None
    
    async def initialize(self) -> None:
        """Initialize the generator components."""
        try:
            self.llm_generator = LLMScriptGenerator(self.config)
            await self.llm_generator.initialize()
            logger.info("Using LLM-based script generation")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM generator: {str(e)}")
            logger.info("Falling back to template-based generation only")
        
        self.template_generator = ScriptGenerator()
    
    async def generate_script(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate a script using enhanced approach."""
        try:
            # Update config if provided
            if config:
                self.config.update(config)
            
            # Try LLM generation first if available
            if self.llm_generator:
                try:
                    llm_result = await self.llm_generator.generate_script(state)
                    if not llm_result.get("error"):
                        return llm_result
                    logger.warning(f"LLM generation failed: {llm_result['error']}. Falling back to template generation.")
                except Exception as e:
                    logger.warning(f"Error in LLM generation: {str(e)}. Falling back to template generation.")
            
            # Fall back to template generation
            return await self.template_generator.generate_script(state)
        
        except Exception as e:
            logger.error(f"Error in enhanced script generation: {str(e)}")
            return {"error": f"Enhanced generation error: {str(e)}"}

    def set_priority(self, priority: str) -> None:
        """
        Set the priority for script generation.
        
        Args:
            priority: Either 'llm' or 'template'
        """
        if priority not in ["llm", "template"]:
            raise ValueError("Priority must be either 'llm' or 'template'")
        logger.info(f"Script generation priority set to: {priority}")

# Helper function to create a script generator based on configuration
async def create_script_generator(config: Optional[Dict[str, Any]] = None) -> EnhancedScriptGenerator:
    """
    Create a script generator based on configuration.
    
    Args:
        config: Optional configuration
        
    Returns:
        Configured EnhancedScriptGenerator
        
    Raises:
        ScriptError: If initialization fails
    """
    try:
        workflow_config = ensure_workflow_config(config or {})
        
        # Get API key and model from config
        api_key = getattr(workflow_config, "openai_api_key", None) if hasattr(workflow_config, "openai_api_key") else None
        env_api_key = os.environ.get("OPENAI_API_KEY")
        api_key = api_key or env_api_key
        
        model = getattr(workflow_config, "llm_model", "gpt-4") if hasattr(workflow_config, "llm_model") else "gpt-4"
        
        # Create generator
        generator = EnhancedScriptGenerator(config={"api_key": api_key, "model": model})
        
        try:
            # Initialize
            await generator.initialize()
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise ScriptError("Failed to initialize LLM client", 
                            context=ErrorContext(component="EnhancedScriptGenerator", 
                                              operation="initialize"),
                            details={"error": str(e)})
        
        # Set priority
        priority = getattr(workflow_config, "script_generation_priority", "llm") if hasattr(workflow_config, "script_generation_priority") else "llm"
        generator.set_priority(priority)
        
        return generator
    except Exception as e:
        logger.error(f"Failed to create script generator: {e}")
        raise ScriptError("Failed to create script generator",
                         context=ErrorContext(component="EnhancedScriptGenerator",
                                           operation="create"),
                         details={"error": str(e)})