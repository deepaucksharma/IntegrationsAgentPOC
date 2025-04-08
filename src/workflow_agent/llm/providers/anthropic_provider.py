"""
Anthropic provider implementation.
"""
import logging
import os
import json
import re
from typing import Dict, Any, Optional

from .base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)

class AnthropicProvider(BaseLLMProvider):
    """Anthropic provider implementation."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Anthropic provider.
        
        Args:
            config: Provider-specific configuration
        """
        super().__init__(config)
        self.client = None
        self._initialize_client()
        
    def _initialize_client(self):
        """Initialize the Anthropic client."""
        api_key = self.config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("Anthropic API key not provided")
            return
            
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(api_key=api_key)
            logger.info("Anthropic client initialized")
        except ImportError:
            logger.warning("Anthropic package not installed. Anthropic provider unavailable.")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")
    
    @property
    def provider_name(self) -> str:
        """Get the name of the provider."""
        return "anthropic"
        
    @property
    def default_model(self) -> str:
        """Get the default model for this provider."""
        return self.config.get("default_model", "claude-3-sonnet-20240229")
    
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate text from Anthropic.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt
            
        Returns:
            Generated text
        """
        if not self.client:
            error_msg = "Anthropic client not initialized"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        
        try:
            # Generate response
            model = self.config.get("model", self.default_model)
            temperature = float(self.config.get("temperature", 0.2))
            max_tokens = self.config.get("max_tokens", 1024)
            
            response = await self.client.messages.create(
                model=model,
                system=system_prompt or "",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extract content
            content = response.content[0].text
            
            return content
            
        except Exception as e:
            error_msg = f"Error generating with Anthropic: {e}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
    
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate JSON from Anthropic.
        
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
        Generate code from Anthropic.
        
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
