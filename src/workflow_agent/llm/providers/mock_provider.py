"""
Mock provider implementation for testing.
"""
import logging
import asyncio
import json
from typing import Dict, Any, Optional

from .base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)

class MockProvider(BaseLLMProvider):
    """Mock provider implementation for testing."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the mock provider.
        
        Args:
            config: Provider-specific configuration
        """
        super().__init__(config)
        logger.info("Mock LLM provider initialized")
    
    @property
    def provider_name(self) -> str:
        """Get the name of the provider."""
        return "mock"
        
    @property
    def default_model(self) -> str:
        """Get the default model for this provider."""
        return "mock-model"
    
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate text from mock provider.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt
            
        Returns:
            Generated text
        """
        # Simulate some latency
        await asyncio.sleep(0.5)
        
        # Log the call
        logger.info(f"Mock LLM generate_text called with prompt: {prompt[:50]}...")
        if system_prompt:
            logger.info(f"System prompt: {system_prompt[:50]}...")
        
        # Generate a simple response based on the prompt
        return f"This is a mock response to: {prompt[:50]}..."
    
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate JSON from mock provider.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt
            
        Returns:
            Generated JSON as a dictionary
        """
        # Simulate some latency
        await asyncio.sleep(0.5)
        
        # Log the call
        logger.info(f"Mock LLM generate_json called with prompt: {prompt[:50]}...")
        
        # Generate a simple JSON response
        return {
            "status": "success",
            "message": "This is a mock response",
            "data": {
                "prompt_preview": prompt[:30] + "...",
                "timestamp": "2024-04-08T12:00:00Z"
            }
        }
    
    async def generate_code(self, prompt: str, system_prompt: Optional[str] = None, language: str = "bash") -> str:
        """
        Generate code from mock provider.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt
            language: Programming language
            
        Returns:
            Generated code
        """
        # Simulate some latency
        await asyncio.sleep(0.5)
        
        # Log the call
        logger.info(f"Mock LLM generate_code called with prompt: {prompt[:50]}...")
        logger.info(f"Language: {language}")
        
        # Generate different mock responses based on language
        if language == "bash":
            return "#!/bin/bash\necho 'This is a mock bash script'\necho 'Generated from prompt: " + prompt[:20] + "...'\nexit 0"
        elif language == "python":
            return "def main():\n    print('This is a mock Python script')\n    print('Generated from prompt: " + prompt[:20] + "...')\n\nif __name__ == '__main__':\n    main()"
        elif language == "javascript":
            return "console.log('This is a mock JavaScript code');\nconsole.log('Generated from prompt: " + prompt[:20] + "...');"
        else:
            return f"// Mock code in {language}\n// Generated from prompt: {prompt[:20]}..."
