"""
Factory for creating LLM providers.
"""
import logging
from typing import Dict, Any, Optional
from enum import Enum
from .providers import BaseLLMProvider, OpenAIProvider, GeminiProvider, AnthropicProvider, MockProvider

logger = logging.getLogger(__name__)

class LLMProviderType(str, Enum):
    """Supported LLM provider types."""
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    MOCK = "mock"

class LLMProviderFactory:
    """Factory for creating LLM providers."""
    
    @staticmethod
    def create_provider(provider_type: LLMProviderType, config: Optional[Dict[str, Any]] = None) -> BaseLLMProvider:
        """
        Create an LLM provider.
        
        Args:
            provider_type: Type of provider to create
            config: Provider-specific configuration
            
        Returns:
            An instance of a provider
            
        Raises:
            ValueError: If provider_type is invalid
        """
        config = config or {}
        
        if provider_type == LLMProviderType.OPENAI:
            return OpenAIProvider(config)
        elif provider_type == LLMProviderType.GEMINI:
            return GeminiProvider(config)
        elif provider_type == LLMProviderType.ANTHROPIC:
            return AnthropicProvider(config)
        elif provider_type == LLMProviderType.MOCK:
            return MockProvider(config)
        else:
            logger.error(f"Unsupported provider type: {provider_type}")
            raise ValueError(f"Unsupported provider type: {provider_type}")
