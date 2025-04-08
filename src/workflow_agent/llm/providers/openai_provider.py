"""
OpenAI provider implementation.
"""
import logging
import os
import json
import re
from typing import Dict, Any, Optional

from .base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)

class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider implementation."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the OpenAI provider.
        
        Args:
            config: Provider-specific configuration
        """
        super().__init__(config)
        self.client = None
        self._initialize_client()
        
    def _initialize_client(self):
        """Initialize the OpenAI client."""
        api_key = self.config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OpenAI API key not provided")
            return
            
        try:
            import openai
            self.client = openai.AsyncOpenAI(api_key=api_key)
            logger.info("OpenAI client initialized")
        except ImportError:
            logger.warning("OpenAI package not installed. OpenAI provider unavailable.")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
    
    @property
    def provider_name(self) -> str:
        """Get the name of the provider."""
        return "openai"
        
    @property
    def default_model(self) -> str:
        """Get the default model for this provider."""
        return self.config.get("default_model", "gpt-3.5-turbo")
    
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate text from OpenAI.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt
            
        Returns:
            Generated text
        """
        if not self.client:
            error_msg = "OpenAI client not initialized"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        
        try:
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Generate response
            model = self.config.get("model", self.default_model)
            temperature = float(self.config.get("temperature", 0.2))
            max_tokens = self.config.get("max_tokens")
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extract content
            content = response.choices[0].message.content
            
            return content
            
        except Exception as e:
            error_msg = f"Error generating with OpenAI: {e}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
    
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate JSON from OpenAI.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt
            
        Returns:
            Generated JSON as a dictionary
        """
        # Add JSON instruction to system prompt
        json_system_prompt = (system_prompt or "") + "\nYou must respond with valid JSON only. No explanatory text. No markdown formatting."
        
        # Generate with JSON response format
        if not self.client:
            return {"error": "OpenAI client not initialized"}
        
        try:
            # Prepare messages
            messages = []
            if json_system_prompt:
                messages.append({"role": "system", "content": json_system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Generate response
            model = self.config.get("model", self.default_model)
            temperature = float(self.config.get("temperature", 0.1))  # Lower temperature for more deterministic JSON
            max_tokens = self.config.get("max_tokens")
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
            
            # Extract content
            content = response.choices[0].message.content
            
            # Parse JSON
            return json.loads(content)
            
        except Exception as e:
            error_msg = f"Error generating JSON with OpenAI: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    async def generate_code(self, prompt: str, system_prompt: Optional[str] = None, language: str = "bash") -> str:
        """
        Generate code from OpenAI.
        
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
