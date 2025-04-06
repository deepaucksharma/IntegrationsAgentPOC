"""Script enhancement using LLM."""
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import os
from datetime import datetime
from ..core.state import WorkflowState
from ..error.exceptions import ScriptError

logger = logging.getLogger(__name__)

# Check for Google Generative AI availability
try:
    import google.generativeai as genai
    HAVE_GENAI = True
except ImportError:
    HAVE_GENAI = False
    logger.warning("Google Generative AI package not found. Script enhancement not available.")

class ScriptEnhancer:
    """Enhances scripts using LLM."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """Initialize the LLM-based script enhancer."""
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name or "gemini-1.5-flash"
        self.model = None
        
        # Initialize Gemini if available
        if HAVE_GENAI and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                logger.info(f"Initialized Gemini model for script enhancement: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini model for enhancement: {e}", exc_info=True)
                self.model = None

    async def enhance_script(self, state: WorkflowState, script_path: Path) -> Dict[str, Any]:
        """Enhance a script using LLM."""
        try:
            # Check if script path exists
            if not script_path.exists():
                return {
                    "success": False,
                    "error": f"Script file not found: {script_path}"
                }
                
            # Read the script content
            script = script_path.read_text()
            
            # Check if Gemini is available
            if not HAVE_GENAI or not self.model:
                logger.warning("Gemini LLM not available for script enhancement.")
                return {
                    "success": True,
                    "script": script,
                    "script_path": str(script_path),
                    "enhanced": False
                }
                
            # Create the enhancement prompt
            enhancement_prompt = self._create_enhancement_prompt(state, script)
            
            # Generate enhanced script with Gemini
            response = self.model.generate_content(enhancement_prompt)
            if not response.text:
                logger.warning("Empty response from LLM during enhancement.")
                return {
                    "success": True,
                    "script": script,
                    "script_path": str(script_path),
                    "enhanced": False
                }
                
            enhanced_script = response.text
            
            # Extract code if wrapped in Markdown code blocks
            if "```" in enhanced_script:
                code_blocks = enhanced_script.split("```")
                if len(code_blocks) >= 3:  # At least one complete code block
                    code_block = code_blocks[1].strip()
                    # Remove language identifier if present
                    if code_block.startswith(("bash", "powershell", "sh", "python")):
                        code_block = code_block.split("\n", 1)[1]
                    enhanced_script = code_block
            
            # Save enhanced script to file
            script_dir = Path("generated_scripts")
            script_dir.mkdir(exist_ok=True)
            
            # Create enhanced filename based on original
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            enhanced_filename = f"{script_path.stem}_enhanced_{timestamp}{script_path.suffix}"
            
            enhanced_path = script_dir / enhanced_filename
            with open(enhanced_path, "w") as f:
                f.write(enhanced_script)
            
            logger.info(f"Enhanced script saved to: {enhanced_path}")
            
            return {
                "success": True,
                "script": enhanced_script,
                "script_path": str(enhanced_path),
                "enhanced": True
            }
        except Exception as e:
            logger.error(f"Error enhancing script: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
            
    def _create_enhancement_prompt(self, state: WorkflowState, script: str) -> str:
        """Create an enhancement prompt for the LLM."""
        is_windows = state.system_context.get("platform", {}).get("system", "").lower() == "windows"
        script_type = "PowerShell" if is_windows else "Bash"
        
        system_prompt = f"""You are an expert DevOps engineer improving {script_type} scripts for the '{state.action}' action on '{state.target_name}'.

Please enhance the provided script with:
1. Robust error handling and recovery mechanisms
2. Improved logging and output formatting
3. Verification steps after key operations
4. Performance optimizations
5. Security best practices
6. Idempotent operations

Target system: {state.system_context.get('platform', {}).get('system', 'unknown')}
Distribution: {state.system_context.get('platform', {}).get('distribution', 'unknown')}

Respond only with the improved script code, no explanations."""

        user_prompt = f"Enhance this script:\n\n{script}"
        
        return f"{system_prompt}\n\n{user_prompt}"
