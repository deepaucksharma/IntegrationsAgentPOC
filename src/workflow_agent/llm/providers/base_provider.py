"""
Base LLM provider interface.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the LLM provider.
        
        Args:
            config: Provider-specific configuration
        """
        self.config = config or {}
        
    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate text from LLM.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt for models that support it
            
        Returns:
            Generated text
        """
        pass
        
    @abstractmethod  
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate JSON from LLM.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt for models that support it
            
        Returns:
            Generated JSON as a dictionary
        """
        pass
        
    @abstractmethod
    async def generate_code(self, prompt: str, system_prompt: Optional[str] = None, language: str = "bash") -> str:
        """
        Generate code from LLM.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt for models that support it
            language: Programming language
            
        Returns:
            Generated code
        """
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the name of the provider."""
        pass
        
    @property
    @abstractmethod
    def default_model(self) -> str:
        """Get the default model for this provider."""
        pass
