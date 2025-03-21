"""LLM-based script generator implementation."""
import logging
import os
from typing import Dict, Any, Optional
from ..core.state import WorkflowState
from ..config.configuration import ensure_workflow_config
from ..error.exceptions import ScriptError
from .generator import ScriptGenerator
from .gemini_client import GeminiClient

# Only import langchain if using OpenAI
HAVE_LANGCHAIN = False
try:
    from langchain.chat_models import ChatOpenAI
    from langchain.schema import HumanMessage, SystemMessage
    HAVE_LANGCHAIN = True
except ImportError:
    pass

logger = logging.getLogger(__name__)

class LLMScriptGenerator(ScriptGenerator):
    """LLM-based script generator."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the LLM script generator."""
        super().__init__()
        self.config = ensure_workflow_config(config or {})
        self.llm_client = None
        self.gemini_client = None
    
    async def initialize(self) -> None:
        """Initialize the LLM client."""
        if self.config.llm_provider == "openai":
            if not HAVE_LANGCHAIN:
                raise ScriptError(
                    "Required packages for OpenAI LLM generation not installed. "
                    "Please run: pip install -e '.[llm]'"
                )
            
            api_key = self.config.openai_api_key
            if not api_key:
                raise ScriptError("OpenAI API key not configured")
            
            try:
                self.llm_client = ChatOpenAI(
                    temperature=0.7,
                    model_name="gpt-3.5-turbo",
                    openai_api_key=api_key
                )
            except Exception as e:
                raise ScriptError(f"Failed to initialize OpenAI client: {str(e)}")
        
        elif self.config.llm_provider == "gemini":
            try:
                self.gemini_client = GeminiClient(api_key=self.config.gemini_api_key)
            except Exception as e:
                raise ScriptError(f"Failed to initialize Gemini client: {str(e)}")
        
        else:
            raise ScriptError(f"Unsupported LLM provider: {self.config.llm_provider}")
    
    async def generate_script(self, state: WorkflowState) -> Dict[str, Any]:
        """Generate a script using LLM."""
        try:
            # Get template content for reference
            template_result = await super().generate_script(state)
            template_content = template_result.get("script", "")
            
            # Prepare prompts
            system_prompt = (
                "You are an expert script generator. Generate a script that accomplishes "
                "the requested task, using the provided template as a reference. The script "
                "should be compatible with the target system and follow best practices."
            )
            
            user_prompt = (
                f"Generate a script for {state.action} action on {state.target_name}.\n"
                f"System context: {state.system_context}\n"
                f"Parameters: {state.parameters}"
            )
            
            # Generate script using the configured LLM provider
            if self.config.llm_provider == "openai":
                if not self.llm_client:
                    raise ScriptError("OpenAI client not initialized")
                
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Template reference:\n{template_content}"),
                    HumanMessage(content=f"User request:\n{user_prompt}")
                ]
                
                response = await self.llm_client.agenerate([messages])
                if not response.generations:
                    return {"error": "No response from OpenAI"}
                
                script = response.generations[0][0].text
                return {"script": script}
            
            elif self.config.llm_provider == "gemini":
                if not self.gemini_client:
                    raise ScriptError("Gemini client not initialized")
                
                return await self.gemini_client.generate_script(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    template_content=template_content
                )
            
            else:
                raise ScriptError(f"Unsupported LLM provider: {self.config.llm_provider}")
        
        except Exception as e:
            logger.error(f"Error in LLM script generation: {str(e)}", exc_info=True)
            return {"error": f"LLM generation error: {str(e)}"}