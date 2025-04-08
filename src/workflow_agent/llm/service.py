"""
Unified LLM service for agentic architecture.
Provides a centralized interface for all LLM operations, supporting multiple providers and advanced prompting.
"""
import logging
import os
import json
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime
import hashlib
import time
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Define the supported LLM providers
class LLMProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    MOCK = "mock"  # For testing purposes

class LLMResponseFormat(str, Enum):
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"
    CODE = "code"

class LLMRequest:
    """Request object for LLM calls with enhanced context and caching support."""
    
    def __init__(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        provider: LLMProvider = LLMProvider.GEMINI,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
        request_id: Optional[str] = None,
        stream: bool = False,
        cache_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.prompt = prompt
        self.system_prompt = system_prompt
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.response_format = response_format
        self.request_id = request_id or f"req-{int(time.time())}-{os.urandom(4).hex()}"
        self.stream = stream
        self.cache_key = cache_key
        self.context = context or {}
        self.created_at = datetime.now()
    
    def get_cache_key(self) -> str:
        """Generate a cache key for this request based on prompt content."""
        if self.cache_key:
            return self.cache_key
            
        # Generate hash based on prompt, system prompt, provider, model, and temperature
        components = [
            self.prompt,
            self.system_prompt or "",
            self.provider,
            self.model or "",
            str(self.temperature)
        ]
        
        key = hashlib.md5(''.join(components).encode('utf-8')).hexdigest()
        return f"llm-{key}"
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary."""
        return {
            "prompt": self.prompt,
            "system_prompt": self.system_prompt,
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": self.response_format,
            "request_id": self.request_id,
            "stream": self.stream,
            "context": self.context,
            "created_at": self.created_at.isoformat()
        }

class LLMResponse:
    """Response object from LLM service with metadata and parsing helpers."""
    
    def __init__(
        self,
        content: str,
        request_id: str,
        model: str,
        provider: LLMProvider,
        tokens_used: Optional[int] = None,
        is_cached: bool = False,
        latency_ms: Optional[int] = None,
        error: Optional[str] = None,
    ):
        self.content = content
        self.request_id = request_id
        self.model = model
        self.provider = provider
        self.tokens_used = tokens_used
        self.is_cached = is_cached
        self.latency_ms = latency_ms
        self.error = error
        self.created_at = datetime.now()
    
    def to_json(self) -> Dict[str, Any]:
        """Parse the content as JSON and return the parsed object."""
        try:
            # Find JSON in the content if it's not pure JSON
            json_match = re.search(r'```json\n(.*?)\n```', self.content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = self.content
                
            return json.loads(json_str)
        except Exception as e:
            logger.warning(f"Failed to parse response as JSON: {e}")
            return {"error": "Failed to parse response as JSON", "content": self.content}
            
    def extract_code(self) -> str:
        """Extract code blocks from the content."""
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', self.content, re.DOTALL)
        if code_blocks:
            return '\n\n'.join(code_blocks)
        return self.content
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary."""
        return {
            "content": self.content,
            "request_id": self.request_id,
            "model": self.model,
            "provider": self.provider,
            "tokens_used": self.tokens_used,
            "is_cached": self.is_cached,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "created_at": self.created_at.isoformat()
        }

class LLMService:
    """Unified service for LLM operations across multiple providers."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize LLM service with configuration."""
        self.config = config or {}
        self.cache = {}  # Simple in-memory cache
        self.cache_dir = Path(self.config.get("cache_dir", "cache"))
        self.cache_dir.mkdir(exist_ok=True)
        
        self.openai_client = None
        self.gemini_model = None
        self.anthropic_client = None
        
        # Default provider settings
        self.default_provider = LLMProvider(self.config.get("default_provider", "gemini"))
        
        # Model configurations by provider
        self.model_configs = {
            LLMProvider.GEMINI: {
                "default": "gemini-1.5-flash",
                "creative": "gemini-1.5-pro",
                "vision": "gemini-1.5-pro-vision",
            },
            LLMProvider.OPENAI: {
                "default": "gpt-3.5-turbo",
                "advanced": "gpt-4",
                "vision": "gpt-4-vision-preview",
            },
            LLMProvider.ANTHROPIC: {
                "default": "claude-instant-1.2",
                "advanced": "claude-2.1",
            }
        }
        
        # Initialize clients
        self._initialize_clients()
        
        logger.info(f"LLM service initialized with default provider: {self.default_provider}")
    
    def _initialize_clients(self):
        """Initialize clients for each LLM provider."""
        # Initialize OpenAI if available
        if self.default_provider == LLMProvider.OPENAI or self.config.get("initialize_all", False):
            api_key = self.config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
            if api_key:
                try:
                    import openai
                    self.openai_client = openai.AsyncOpenAI(api_key=api_key)
                    logger.info("OpenAI client initialized")
                except ImportError:
                    logger.warning("OpenAI package not installed. OpenAI provider unavailable.")
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI client: {e}")
        
        # Initialize Gemini if available
        if self.default_provider == LLMProvider.GEMINI or self.config.get("initialize_all", False):
            api_key = self.config.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
            if api_key:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    model_name = self.model_configs[LLMProvider.GEMINI]["default"]
                    self.gemini_model = genai.GenerativeModel(model_name)
                    logger.info(f"Gemini model initialized: {model_name}")
                except ImportError:
                    logger.warning("Google Generative AI package not installed. Gemini provider unavailable.")
                except Exception as e:
                    logger.error(f"Failed to initialize Gemini model: {e}")
        
        # Initialize Anthropic if available
        if self.default_provider == LLMProvider.ANTHROPIC or self.config.get("initialize_all", False):
            api_key = self.config.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                try:
                    import anthropic
                    self.anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)
                    logger.info("Anthropic client initialized")
                except ImportError:
                    logger.warning("Anthropic package not installed. Anthropic provider unavailable.")
                except Exception as e:
                    logger.error(f"Failed to initialize Anthropic client: {e}")
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
        use_cache: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate text from LLM.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt for models that support it
            provider: LLM provider to use
            model: Model name
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            response_format: Desired response format
            use_cache: Whether to use cache
            context: Additional context
            
        Returns:
            Generated text
        """
        # Create request object
        request = LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            provider=provider or self.default_provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            context=context,
        )
        
        # Generate response
        response = await self._generate_response(request, use_cache)
        
        # Log response metadata
        logger.info(
            f"Generated response for {request.request_id}: "
            f"{response.provider}/{response.model}, "
            f"Tokens: {response.tokens_used}, "
            f"Cached: {response.is_cached}, "
            f"Latency: {response.latency_ms}ms"
        )
        
        # Save response to cache directory
        await self._save_interaction(request, response)
        
        # Return content
        return response.content
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,  # Lower temperature for more deterministic JSON
        max_tokens: Optional[int] = None,
        use_cache: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate JSON from LLM.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt for models that support it
            provider: LLM provider to use
            model: Model name
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            use_cache: Whether to use cache
            context: Additional context
            
        Returns:
            Generated JSON as a dictionary
        """
        # Add JSON instruction to system prompt
        json_system_prompt = (system_prompt or "") + "\nYou must respond with valid JSON only. No explanatory text. No markdown formatting."
        
        # Create request for JSON
        request = LLMRequest(
            prompt=prompt,
            system_prompt=json_system_prompt,
            provider=provider or self.default_provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=LLMResponseFormat.JSON,
            context=context,
        )
        
        # Generate response
        response = await self._generate_response(request, use_cache)
        
        # Parse response as JSON
        json_response = response.to_json()
        
        # Save interaction
        await self._save_interaction(request, response)
        
        return json_response
    
    async def generate_code(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        language: str = "bash",
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        use_cache: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate code from LLM.
        
        Args:
            prompt: Main prompt
            system_prompt: Optional system prompt for models that support it
            provider: LLM provider to use
            model: Model name
            language: Programming language
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            use_cache: Whether to use cache
            context: Additional context
            
        Returns:
            Generated code
        """
        # Add code instruction to system prompt
        code_system_prompt = (system_prompt or "") + f"\nYou must respond with only {language} code. No explanatory text. No markdown formatting."
        
        # Create request for code
        request = LLMRequest(
            prompt=prompt,
            system_prompt=code_system_prompt,
            provider=provider or self.default_provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=LLMResponseFormat.CODE,
            context=context,
        )
        
        # Generate response
        response = await self._generate_response(request, use_cache)
        
        # Extract code from response
        code = response.extract_code()
        
        # Save interaction
        await self._save_interaction(request, response)
        
        return code
    
    async def _generate_response(self, request: LLMRequest, use_cache: bool = True) -> LLMResponse:
        """
        Generate response for a request.
        
        Args:
            request: Request object
            use_cache: Whether to use cache
            
        Returns:
            Response object
        """
        # Check cache
        cache_key = request.get_cache_key()
        if use_cache and cache_key in self.cache:
            logger.debug(f"Using cached response for {cache_key}")
            cached_response = self.cache[cache_key]
            # Update cached response
            cached_response.is_cached = True
            return cached_response
        
        start_time = time.time()
        
        # Select appropriate provider
        if request.provider == LLMProvider.OPENAI:
            response = await self._generate_openai(request)
        elif request.provider == LLMProvider.GEMINI:
            response = await self._generate_gemini(request)
        elif request.provider == LLMProvider.ANTHROPIC:
            response = await self._generate_anthropic(request)
        elif request.provider == LLMProvider.MOCK:
            response = await self._generate_mock(request)
        else:
            # Default to Gemini
            response = await self._generate_gemini(request)
        
        end_time = time.time()
        latency_ms = int((end_time - start_time) * 1000)
        
        # Update response with latency
        response.latency_ms = latency_ms
        
        # Cache response
        if use_cache and not response.error:
            self.cache[cache_key] = response
        
        return response
    
    async def _generate_openai(self, request: LLMRequest) -> LLMResponse:
        """Generate response using OpenAI."""
        if not self.openai_client:
            logger.error("OpenAI client not initialized")
            return LLMResponse(
                content="",
                request_id=request.request_id,
                model="unknown",
                provider=LLMProvider.OPENAI,
                error="OpenAI client not initialized"
            )
        
        try:
            # Determine model
            model = request.model or self.model_configs[LLMProvider.OPENAI]["default"]
            
            # Prepare messages
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.prompt})
            
            # Handle response format
            response_format = None
            if request.response_format == LLMResponseFormat.JSON:
                response_format = {"type": "json_object"}
            
            # Generate response
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                response_format=response_format,
                stream=request.stream
            )
            
            # Extract content and metadata
            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if hasattr(response, "usage") else None
            
            return LLMResponse(
                content=content,
                request_id=request.request_id,
                model=model,
                provider=LLMProvider.OPENAI,
                tokens_used=tokens_used
            )
            
        except Exception as e:
            logger.error(f"Error generating with OpenAI: {e}")
            return LLMResponse(
                content="",
                request_id=request.request_id,
                model="unknown",
                provider=LLMProvider.OPENAI,
                error=str(e)
            )
    
    async def _generate_gemini(self, request: LLMRequest) -> LLMResponse:
        """Generate response using Google Gemini."""
        import google.generativeai as genai
        
        if not self.gemini_model:
            logger.error("Gemini model not initialized")
            return LLMResponse(
                content="",
                request_id=request.request_id,
                model="unknown",
                provider=LLMProvider.GEMINI,
                error="Gemini model not initialized"
            )
        
        try:
            # Determine model
            model_name = request.model or self.model_configs[LLMProvider.GEMINI]["default"]
            
            # Recreate model if different from current
            if not hasattr(self.gemini_model, "model_name") or self.gemini_model.model_name != model_name:
                self.gemini_model = genai.GenerativeModel(model_name)
            
            # Prepare content
            if request.system_prompt:
                chat = self.gemini_model.start_chat(history=[
                    {"role": "user", "parts": [request.system_prompt]},
                    {"role": "model", "parts": ["I'll follow these instructions."]}
                ])
                response = chat.send_message(request.prompt)
            else:
                response = self.gemini_model.generate_content(request.prompt)
            
            # Extract content
            if hasattr(response, "text"):
                content = response.text
            else:
                content = response.parts[0].text if hasattr(response, "parts") and response.parts else ""
            
            return LLMResponse(
                content=content,
                request_id=request.request_id,
                model=model_name,
                provider=LLMProvider.GEMINI
            )
            
        except Exception as e:
            logger.error(f"Error generating with Gemini: {e}")
            return LLMResponse(
                content="",
                request_id=request.request_id,
                model="unknown",
                provider=LLMProvider.GEMINI,
                error=str(e)
            )
    
    async def _generate_anthropic(self, request: LLMRequest) -> LLMResponse:
        """Generate response using Anthropic Claude."""
        if not self.anthropic_client:
            logger.error("Anthropic client not initialized")
            return LLMResponse(
                content="",
                request_id=request.request_id,
                model="unknown",
                provider=LLMProvider.ANTHROPIC,
                error="Anthropic client not initialized"
            )
        
        try:
            # Determine model
            model = request.model or self.model_configs[LLMProvider.ANTHROPIC]["default"]
            
            # Prepare system and prompt
            system = request.system_prompt or ""
            
            # Generate response
            response = await self.anthropic_client.messages.create(
                model=model,
                system=system,
                messages=[{"role": "user", "content": request.prompt}],
                temperature=request.temperature,
                max_tokens=request.max_tokens or 1024
            )
            
            # Extract content
            content = response.content[0].text
            
            return LLMResponse(
                content=content,
                request_id=request.request_id,
                model=model,
                provider=LLMProvider.ANTHROPIC
            )
            
        except Exception as e:
            logger.error(f"Error generating with Anthropic: {e}")
            return LLMResponse(
                content="",
                request_id=request.request_id,
                model="unknown",
                provider=LLMProvider.ANTHROPIC,
                error=str(e)
            )
    
    async def _generate_mock(self, request: LLMRequest) -> LLMResponse:
        """Generate mock response for testing."""
        logger.info("Generating mock response")
        
        # Simulate latency
        await asyncio.sleep(0.5)
        
        # Generate different responses based on request type
        if request.response_format == LLMResponseFormat.JSON:
            content = '{"status": "success", "message": "This is a mock response", "data": {"foo": "bar"}}'
        elif request.response_format == LLMResponseFormat.CODE:
            content = "#!/bin/bash\necho 'This is a mock script'\nexit 0"
        else:
            content = f"This is a mock response to: {request.prompt[:50]}..."
        
        return LLMResponse(
            content=content,
            request_id=request.request_id,
            model="mock-model",
            provider=LLMProvider.MOCK,
            tokens_used=len(content.split())
        )
    
    async def _save_interaction(self, request: LLMRequest, response: LLMResponse) -> None:
        """Save the interaction to the cache directory for audit and reuse."""
        try:
            interaction_dir = self.cache_dir / "interactions"
            interaction_dir.mkdir(exist_ok=True)
            
            # Create a file with the interaction data
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{request.request_id}.json"
            
            interaction_data = {
                "request": request.to_dict(),
                "response": response.to_dict()
            }
            
            with open(interaction_dir / filename, "w") as f:
                json.dump(interaction_data, f, indent=2, default=str)
                
            logger.debug(f"Saved interaction to {filename}")
            
        except Exception as e:
            logger.warning(f"Failed to save interaction: {e}")
