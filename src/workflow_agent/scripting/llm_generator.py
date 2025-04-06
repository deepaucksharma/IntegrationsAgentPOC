"""LLM-based script generator with support for multiple LLM providers."""
import logging
import os
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from ..core.state import WorkflowState
from ..error.exceptions import ScriptError
from .generator import ScriptGenerator
from .gemini_client import GeminiClient

# Only import langchain if available
try:
    from langchain.chat_models import ChatOpenAI
    from langchain.schema import HumanMessage, SystemMessage
    HAVE_LANGCHAIN = True
except ImportError:
    HAVE_LANGCHAIN = False

logger = logging.getLogger(__name__)

class LLMScriptGenerator(ScriptGenerator):
    """Generates scripts using LLM with fallback to templates."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, template_dir: Optional[str] = None):
        """Initialize the LLM script generator."""
        super().__init__(template_dir)
        self.config = config or {}
        self.llm_client = None
        self.template_engine = ScriptGenerator(template_dir)
        
    async def initialize(self) -> None:
        """Initialize the LLM client."""
        # Determine LLM provider from config
        llm_provider = self.config.get("llm_provider", "gemini").lower()
        
        try:
            if llm_provider == "gemini":
                api_key = self.config.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
                if not api_key:
                    logger.warning("No Gemini API key provided. LLM script generation will not be available.")
                    return
                    
                self.llm_client = GeminiClient(api_key)
                logger.info("Gemini LLM client initialized successfully")
                
            elif llm_provider == "openai" and HAVE_LANGCHAIN:
                api_key = self.config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    logger.warning("No OpenAI API key provided. LLM script generation will not be available.")
                    return
                    
                # Configure OpenAI client via LangChain
                self.llm_client = ChatOpenAI(temperature=0.7, model="gpt-3.5-turbo", openai_api_key=api_key)
                logger.info("OpenAI LLM client initialized successfully")
                
            else:
                logger.warning(f"Unsupported LLM provider: {llm_provider}")
                
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}", exc_info=True)
            raise ScriptError(f"LLM client initialization failed: {e}")

    async def generate_script(self, state: WorkflowState) -> Dict[str, Any]:
        """Generate a script using LLM with fallback to templates."""
        try:
            logger.info(f"Generating LLM script for {state.action} on {state.target_name}")
            
            # If no LLM client is available, fall back to template-based generation
            if not self.llm_client:
                logger.warning("No LLM client available. Falling back to template-based generation.")
                return await self.template_engine.generate_script(state)
                
            # Get template for reference
            template_result = await self.template_engine.generate_script(state)
            template_content = template_result.get("script", "") if "error" not in template_result else ""
            
            # Prepare the system prompt
            system_prompt = self._create_system_prompt(state)
            
            # Prepare the user prompt
            user_prompt = self._create_user_prompt(state)
            
            # Use different generation methods based on LLM provider
            if isinstance(self.llm_client, GeminiClient):
                # Use Gemini client
                result = await self.llm_client.generate_script(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    template_content=template_content
                )
            elif HAVE_LANGCHAIN and hasattr(self.llm_client, "generate"):
                # Use LangChain-based client
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Template reference:\n{template_content}\n\nUser request:\n{user_prompt}")
                ]
                
                response = await self.llm_client.agenerate([messages])
                if not response.generations or not response.generations[0]:
                    return {"error": "LLM returned empty response"}
                    
                script = response.generations[0][0].text
                result = {"script": script}
            else:
                return {"error": "No compatible LLM client available"}
                
            if "error" in result:
                logger.warning(f"LLM script generation failed: {result['error']}. Falling back to template.")
                return await self.template_engine.generate_script(state)
                
            # Save the generated script
            script = result["script"]
            script_path = self._save_script(state, script)
            
            return {
                "success": True,
                "script": script,
                "script_path": str(script_path),
                "generation_method": "llm"
            }
            
        except Exception as e:
            logger.error(f"Error in LLM script generation: {e}", exc_info=True)
            
            # Fall back to template-based generation
            logger.info("Falling back to template-based generation due to error")
            return await self.template_engine.generate_script(state)
            
    def _create_system_prompt(self, state: WorkflowState) -> str:
        """Create a system prompt for the LLM based on the workflow state."""
        is_windows = state.system_context.get("platform", {}).get("system", "").lower() == "windows"
        script_type = "PowerShell" if is_windows else "Bash"
        
        return f"""You are an expert DevOps engineer creating {script_type} scripts for automated deployments.
        
Your task is to generate a script for the '{state.action}' action on '{state.target_name}' for the '{state.integration_type}' integration.

Target system: {state.system_context.get('platform', {}).get('system', 'unknown')}
Distribution: {state.system_context.get('platform', {}).get('distribution', 'unknown')}
Version: {state.system_context.get('platform', {}).get('version', 'unknown')}

Key requirements:
1. Create a robust script with error handling and logging
2. Include proper validation and prerequisite checks
3. Follow best practices for the target platform
4. Ensure idempotent operations where possible
5. Include descriptive comments for each major section

Respond only with the script content, no additional explanation or markdown."""
        
    def _create_user_prompt(self, state: WorkflowState) -> str:
        """Create a user prompt for the LLM based on the workflow state."""
        action_descriptions = {
            "install": f"Install the {state.target_name} integration",
            "verify": f"Verify the {state.target_name} integration installation",
            "uninstall": f"Remove the {state.target_name} integration"
        }
        
        action_description = action_descriptions.get(state.action, f"Perform {state.action} on {state.target_name}")
        
        prompt = f"""Create a script to {action_description}.

Parameters:
{self._format_parameters(state.parameters)}

Please ensure the script:
1. Has proper error handling
2. Logs each step of the process
3. Returns appropriate exit codes
4. Includes verification of completion
5. Is secure and follows best practices"""

        return prompt
        
    def _format_parameters(self, parameters: Dict[str, Any]) -> str:
        """Format parameters for the prompt."""
        result = []
        for key, value in parameters.items():
            if isinstance(value, dict):
                result.append(f"- {key}: {json.dumps(value)}")
            else:
                result.append(f"- {key}: {value}")
        
        return "\n".join(result)
