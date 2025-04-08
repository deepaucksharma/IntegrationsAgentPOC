"""
Google Gemini provider implementation.
"""
import logging
import os
import json
import re
from typing import Dict, Any, Optional

from .base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)

class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider implementation."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Gemini provider.
        
        Args:
            config: Provider-specific configuration
        """
        super().__init__(config)
        self.model = None
        self._initialize_model()
        
    def _initialize_model(self):
        """Initialize the Gemini model."""
        api_key = self.config.get("api_key") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("Gemini API key not provided")
            return
            
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model_name = self.config.get("model", self.default_model)
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"Gemini model initialized: {model_name}")
        except ImportError:
            logger.warning("Google Generative AI package not installed. Gemini provider unavailable.")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
    
    @property
    def provider_name(self) -> str:
        """Get the name of the provider."""
        return "gemini"
        
    @property
    def default_model(self) -> str:
        """Get the default model for this provider."""
        return self.config.get("default_model", "gemini-1.5-flash")
    
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate text from Gemini.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt
            
        Returns:
            Generated text
        """
        if not self.model:
            error_msg = "Gemini model not initialized"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        
        try:
            import google.generativeai as genai
            
            # Check if we need to recreate the model
            model_name = self.config.get("model", self.default_model)
            if not hasattr(self.model, "model_name") or self.model.model_name != model_name:
                self.model = genai.GenerativeModel(model_name)
            
            # Prepare content
            if system_prompt:
                chat = self.model.start_chat(history=[
                    {"role": "user", "parts": [system_prompt]},
                    {"role": "model", "parts": ["I'll follow these instructions."]}
                ])
                response = await chat.send_message_async(prompt)
            else:
                response = await self.model.generate_content_async(prompt)
            
            # Extract content
            if hasattr(response, "text"):
                content = response.text
            else:
                content = response.parts[0].text if hasattr(response, "parts") and response.parts else ""
            
            return content
            
        except Exception as e:
            error_msg = f"Error generating with Gemini: {e}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
    
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate JSON from Gemini.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt
            
        Returns:
            Generated JSON as a dictionary
        """
        # Add JSON instruction to system prompt
        json_system_prompt = (system_prompt or "") + "\nYou must respond with valid JSON only. No explanatory text. No markdown formatting."
        
        # Generate the response
        response = await self.generate_text(prompt, json_system_prompt)
        
        # Parse JSON
        try:
            # Find JSON in the content if it's not pure JSON
            json_match = re.search(r'```json\n(.*?)\n```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response
                
            return json.loads(json_str)
        except Exception as e:
            error_msg = f"Failed to parse response as JSON: {e}"
            logger.warning(error_msg)
            return {"error": error_msg, "content": response}
    
    async def generate_code(self, prompt: str, system_prompt: Optional[str] = None, language: str = "bash") -> str:
        """
        Generate code from Gemini.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt
            language: Programming language
            
        Returns:
            Generated code
        """
        # Add code instruction to system prompt
        code_system_prompt = (system_prompt or "") + f"\nYou must respond with only {language} code. No explanatory text. No markdown formatting."
        
        # Generate the response
        response = await self.generate_text(prompt, code_system_prompt)
        
        # Extract code blocks if present
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', response, re.DOTALL)
        if code_blocks:
            return '\n\n'.join(code_blocks)
        
        return response
