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

class EnhancedScriptGenerator:
    """Enhanced script generator that uses LLM when available with template fallback."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        """
        Initialize the enhanced script generator.
        
        Args:
            api_key: Optional API key for LLM service
            model: LLM model to use
        """
        self.llm_generator = LLMScriptGenerator(api_key=api_key, model=model)
        self.template_generator = ScriptGenerator()
        self.priority = "llm"  # 'llm' or 'template' - default to LLM if available
        
    async def initialize(self) -> None:
        """Initialize the script generators."""
        await self.llm_generator.initialize()
        # No initialization needed for template generator
        
    async def generate_script(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a script using LLM with template fallback.
        
        Args:
            state: Workflow state
            config: Optional configuration
            
        Returns:
            Dictionary with script or error
        """
        try:
            # Get configuration
            workflow_config = ensure_workflow_config(config or {})
            
            # Check if LLM is explicitly disabled in config
            use_llm = workflow_config.use_llm if hasattr(workflow_config, "use_llm") else True
            
            # Get API key from config if not provided during initialization
            api_key = getattr(self.llm_generator, "api_key", None)
            if not api_key and use_llm:
                # Try to get API key from config or environment
                config_api_key = getattr(workflow_config, "openai_api_key", None) if hasattr(workflow_config, "openai_api_key") else None
                env_api_key = os.environ.get("OPENAI_API_KEY")
                
                api_key = config_api_key or env_api_key
                if api_key:
                    self.llm_generator.api_key = api_key
                    await self.llm_generator.initialize()
            
            # Determine generation approach
            if not use_llm or self.priority == "template":
                # Use template-based generation as primary
                try:
                    logger.info("Using template-based script generation")
                    result = await self.template_generator.generate_script(state, config)
                    if "error" in result:
                        # Fall back to LLM if template fails
                        logger.warning(f"Template generation failed: {result['error']}. Trying LLM generation.")
                        if use_llm and api_key:
                            result = await self.llm_generator.generate_script(state, config)
                    return result
                except Exception as e:
                    logger.error(f"Template generation failed with error: {e}")
                    if use_llm and api_key:
                        logger.info("Falling back to LLM generation")
                        return await self.llm_generator.generate_script(state, config)
                    raise
            else:
                # Use LLM-based generation as primary
                if use_llm and api_key:
                    try:
                        logger.info("Using LLM-based script generation")
                        result = await self.llm_generator.generate_script(state, config)
                        if "error" in result:
                            # Fall back to template if LLM fails
                            logger.warning(f"LLM generation failed: {result['error']}. Falling back to template generation.")
                            result = await self.template_generator.generate_script(state, config)
                        return result
                    except Exception as e:
                        logger.error(f"LLM generation failed with error: {e}")
                        logger.info("Falling back to template generation")
                        return await self.template_generator.generate_script(state, config)
                else:
                    # Use template if LLM not available
                    logger.info("LLM not available. Using template-based generation.")
                    return await self.template_generator.generate_script(state, config)
        
        except Exception as e:
            logger.error(f"Script generation failed: {e}", exc_info=True)
            context = ErrorContext(
                component="EnhancedScriptGenerator",
                operation="generate_script",
                details={"error": str(e)}
            )
            raise ScriptError(f"Script generation failed: {str(e)}", context=context)

    def set_priority(self, priority: str) -> None:
        """
        Set the priority for script generation.
        
        Args:
            priority: Either 'llm' or 'template'
        """
        if priority not in ["llm", "template"]:
            raise ValueError("Priority must be either 'llm' or 'template'")
        self.priority = priority
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
        generator = EnhancedScriptGenerator(api_key=api_key, model=model)
        
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