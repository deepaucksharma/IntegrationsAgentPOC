"""LLM-based script generation."""
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import os
import json
from ..core.state import WorkflowState
from ..error.exceptions import ScriptError

logger = logging.getLogger(__name__)

# Check for Google Generative AI availability
try:
    import google.generativeai as genai
    HAVE_GENAI = True
except ImportError:
    HAVE_GENAI = False
    logger.warning("Google Generative AI package not found. Falling back to template-based generation.")

class ScriptGenerator:
    """Generates scripts using LLM."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """Initialize the LLM-based script generator."""
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name or "gemini-1.5-flash"
        self.model = None
        
        # Initialize Gemini if available
        if HAVE_GENAI and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                logger.info(f"Initialized Gemini model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini model: {e}", exc_info=True)
                self.model = None

    async def generate_script(self, state: WorkflowState) -> Dict[str, Any]:
        """Generate a script using LLM."""
        try:
            # Check if Gemini is available
            if not HAVE_GENAI or not self.model:
                return {
                    "success": False,
                    "error": "Gemini LLM not available"
                }
                
            # Create the prompt
            prompt = self._create_prompt(state)
            
            # Generate script with Gemini
            response = self.model.generate_content(prompt)
            if not response.text:
                return {"success": False, "error": "Empty response from LLM"}
                
            script = response.text
            
            # Extract code if wrapped in Markdown code blocks
            if "```" in script:
                code_blocks = script.split("```")
                if len(code_blocks) >= 3:  # At least one complete code block
                    code_block = code_blocks[1].strip()
                    # Remove language identifier if present
                    if code_block.startswith(("bash", "powershell", "sh", "python")):
                        code_block = code_block.split("\n", 1)[1]
                    script = code_block
            
            # Save script to file
            script_dir = Path("generated_scripts")
            script_dir.mkdir(exist_ok=True)
            
            # Determine file extension based on platform
            is_windows = state.system_context.get("platform", {}).get("system", "").lower() == "windows"
            ext = ".ps1" if is_windows else ".sh"
            
            # Create filename
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{state.target_name}_{state.action}_llm_{timestamp}{ext}"
            
            script_path = script_dir / filename
            with open(script_path, "w") as f:
                f.write(script)
            
            return {
                "success": True,
                "script_path": str(script_path),
                "script": script
            }
        except Exception as e:
            logger.error(f"Error generating script with LLM: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
            
    def _create_prompt(self, state: WorkflowState) -> str:
        """Create a prompt for the LLM."""
        is_windows = state.system_context.get("platform", {}).get("system", "").lower() == "windows"
        script_type = "PowerShell" if is_windows else "Bash"
        
        # System prompt
        system_prompt = f"""You are an expert DevOps engineer creating {script_type} scripts for automated deployments.
        
Your task is to generate a script for the '{state.action}' action on '{state.target_name}' for the '{state.integration_type}' integration.

Target system: {state.system_context.get('platform', {}).get('system', 'unknown')}
Distribution: {state.system_context.get('platform', {}).get('distribution', 'unknown')}
Version: {state.system_context.get('platform', {}).get('version', 'unknown')}"""

        # User prompt
        action_descriptions = {
            "install": f"Install the {state.target_name} integration",
            "verify": f"Verify the {state.target_name} integration installation",
            "uninstall": f"Remove the {state.target_name} integration"
        }
        
        action_description = action_descriptions.get(state.action, f"Perform {state.action} on {state.target_name}")
        
        # Format parameters
        param_lines = []
        for key, value in state.parameters.items():
            if isinstance(value, dict):
                param_lines.append(f"- {key}: {json.dumps(value)}")
            else:
                param_lines.append(f"- {key}: {value}")
        
        parameters_text = "\n".join(param_lines)
        
        user_prompt = f"""Create a script to {action_description}.

Parameters:
{parameters_text}

Please ensure the script:
1. Has proper error handling
2. Logs each step of the process
3. Returns appropriate exit codes
4. Includes verification of completion
5. Is secure and follows best practices

Respond only with the script code, no explanations or markdown formatting."""

        # Combine prompts
        return f"{system_prompt}\n\n{user_prompt}"
