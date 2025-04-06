"""Enhanced script generator with combined template and LLM approach."""
import logging
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from ..core.state import WorkflowState
from ..error.exceptions import ScriptError
from .generator import ScriptGenerator
from .llm_generator import LLMScriptGenerator

logger = logging.getLogger(__name__)

class EnhancedScriptGenerator:
    """Enhanced script generator that combines templates and LLM improvements."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, template_dir: Optional[str] = None):
        """Initialize the enhanced script generator."""
        self.config = config or {}
        self.template_generator = ScriptGenerator(template_dir)
        self.llm_generator = None
        
    async def initialize(self) -> None:
        """Initialize the enhanced script generator."""
        try:
            # Set up LLM generator if configured
            if self.config.get("use_llm", True):
                self.llm_generator = LLMScriptGenerator(self.config)
                await self.llm_generator.initialize()
                logger.info("LLM script generator initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize enhanced script generator: {e}", exc_info=True)
            logger.info("Continuing with template-based generation only")
            
    async def enhance_script(self, state: WorkflowState, script_path: Path) -> Dict[str, Any]:
        """Enhance an existing script using LLM improvements."""
        try:
            # First try to read the script
            if not script_path.exists():
                return {"error": f"Script file not found: {script_path}"}
                
            script_content = script_path.read_text()
            
            # If no LLM generator available, just return the original script
            if not self.llm_generator or not self.llm_generator.llm_client:
                logger.warning("No LLM client available for script enhancement.")
                return {"script": script_content, "enhanced": False}
                
            # Prepare the enhancement prompt
            system_prompt = self._create_enhancement_prompt(state)
            user_prompt = f"Enhance the following script:\n\n{script_content}"
            
            # Get enhanced script from LLM
            if hasattr(self.llm_generator.llm_client, "generate_script"):
                result = await self.llm_generator.llm_client.generate_script(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt
                )
                
                if "error" in result:
                    logger.warning(f"Script enhancement failed: {result['error']}")
                    return {"script": script_content, "enhanced": False, "error": result["error"]}
                    
                enhanced_script = result["script"]
            else:
                logger.warning("LLM client does not support script enhancement.")
                return {"script": script_content, "enhanced": False}
            
            # Save the enhanced script
            enhanced_path = self._save_enhanced_script(state, script_path, enhanced_script)
            
            return {
                "success": True,
                "script": enhanced_script,
                "script_path": str(enhanced_path),
                "enhanced": True
            }
            
        except Exception as e:
            logger.error(f"Error enhancing script: {e}", exc_info=True)
            return {"error": str(e)}
    
    def _create_enhancement_prompt(self, state: WorkflowState) -> str:
        """Create a system prompt for script enhancement."""
        return f"""As an expert DevOps engineer, improve the provided script for the '{state.action}' action on '{state.target_name}'.

Enhancement goals:
1. Add robust error handling and recovery mechanisms
2. Improve logging and output formatting
3. Add verification steps after key operations
4. Optimize performance where possible
5. Enhance security best practices
6. Ensure idempotent operations

Target system: {state.system_context.get('platform', {}).get('system', 'unknown')}
Distribution: {state.system_context.get('platform', {}).get('distribution', 'unknown')}

Respond only with the improved script, no explanation needed."""

    def _save_enhanced_script(self, state: WorkflowState, original_path: Path, content: str) -> Path:
        """Save the enhanced script."""
        # Create scripts directory if it doesn't exist
        script_dir = Path("generated_scripts")
        script_dir.mkdir(exist_ok=True)
        
        # Create filename based on original with _enhanced suffix
        original_stem = original_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        enhanced_filename = f"{original_stem}_enhanced_{timestamp}{original_path.suffix}"
        
        # Save the enhanced script
        enhanced_path = script_dir / enhanced_filename
        with open(enhanced_path, "w") as f:
            f.write(content)
            
        logger.info(f"Enhanced script saved to: {enhanced_path}")
        return enhanced_path
        
# Function to create script generator based on configuration
def create_script_generator(config: Optional[Dict[str, Any]] = None) -> ScriptGenerator:
    """Create the appropriate script generator based on configuration."""
    config = config or {}
    
    # Determine the generator type
    generator_type = config.get("script_generator_type", "template").lower()
    
    if generator_type == "llm":
        return LLMScriptGenerator(config)
    elif generator_type == "enhanced":
        return EnhancedScriptGenerator(config)
    else:
        return ScriptGenerator(config.get("template_dir"))
