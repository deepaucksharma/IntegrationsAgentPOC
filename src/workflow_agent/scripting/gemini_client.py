"""Google Gemini LLM client implementation."""
import logging
import os
from typing import Dict, Any, List, Optional
import google.generativeai as genai
from ..error.exceptions import ScriptError

logger = logging.getLogger(__name__)

class GeminiClient:
    """Client for interacting with Google's Gemini LLM."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Gemini client."""
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ScriptError("Gemini API key not provided")
        
        # Configure the Gemini client
        genai.configure(api_key=self.api_key)
        
        # Get the model
        try:
            # List available models
            models = genai.list_models()
            model_name = None
            
            # First try to find gemini-1.5-flash
            for model in models:
                if "gemini-1.5-flash" in model.name.lower():
                    model_name = model.name
                    break
            
            # If not found, try any gemini model
            if not model_name:
                for model in models:
                    if "gemini" in model.name.lower():
                        model_name = model.name
                        break
            
            if not model_name:
                raise ScriptError("No Gemini model found")
            
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"Using Gemini model: {model_name}")
        except Exception as e:
            raise ScriptError(f"Failed to initialize Gemini model: {str(e)}")
    
    async def generate_script(
        self,
        system_prompt: str,
        user_prompt: str,
        template_content: Optional[str] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Generate a script using Gemini."""
        try:
            # Combine prompts
            combined_prompt = f"{system_prompt}\n\nTemplate reference:\n{template_content}\n\nUser request:\n{user_prompt}"
            
            # Generate response with retries
            for attempt in range(max_retries):
                try:
                    response = self.model.generate_content(combined_prompt)
                    
                    if not response.text:
                        if attempt < max_retries - 1:
                            logger.warning(f"Empty response from Gemini (attempt {attempt + 1}/{max_retries})")
                            continue
                        return {"error": "Gemini returned empty response"}
                    
                    # Extract the script from the response
                    script = response.text
                    if "```" in script:
                        # Extract code from markdown code blocks if present
                        script = script.split("```")[1].strip()
                        if script.startswith(("bash", "powershell", "sh")):
                            script = script.split("\n", 1)[1]
                    
                    return {"script": script}
                
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Gemini generation failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                        continue
                    raise
            
            return {"error": "Failed to generate script after all retries"}
        
        except Exception as e:
            logger.error(f"Error in Gemini script generation: {str(e)}", exc_info=True)
            return {"error": f"Gemini generation error: {str(e)}"} 