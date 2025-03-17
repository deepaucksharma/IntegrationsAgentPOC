# src/workflow_agent/scripting/optimizers/llm.py
import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Check for OpenAI API key - required for LLM optimization
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

async def llm_optimize(
    script: str,
    state: Any,
    system_context: Dict,
    history: List,
    stats: Dict
) -> str:
    """
    Optimize script using LLM (OpenAI).
    
    Args:
        script: Original script content
        state: Current workflow state
        system_context: System context information
        history: Execution history
        stats: Execution statistics
    
    Returns:
        Optimized script
    """
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not available, skipping LLM optimization")
        return script
    
    try:
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(model="gpt-4", api_key=OPENAI_API_KEY)
        
        platform_info = f"OS: {system_context['platform']['system']} {system_context['platform']['release']}"
        package_manager = system_context.get("package_managers", {}).get("primary", "unknown")
        
        common_errors = stats.get("common_errors", [])
        error_summary = "\n".join([f"- Error (count {e['count']}): {e['message']}" for e in common_errors])
        
        param_summary = "\n".join([f"- {k}: {v}" for k, v in state.parameters.items()])
        
        prompt = f"""
You are an expert system administrator. Improve the following script for reliability and idempotency.

TASK: Create a script to {state.action} {state.target_name} integration for New Relic infra agent.

SYSTEM INFO:
{platform_info}, pkg mgr: {package_manager}, Docker: {system_context.get('docker_available', False)}

PARAMETERS:
{param_summary}

BASE TEMPLATE:
```bash
{script}
```

HISTORY (total: {stats.get('total_executions', 0)}, success rate: {stats.get('success_rate', 1.0)*100:.1f}%, avg time: {stats.get('average_execution_time', 0):.1f}ms)

COMMON ERRORS:
{error_summary}

REQUIREMENTS:
- Return only a valid bash script (no markdown, no explanations).
- Add robust error handling and logging.
- Make it idempotent.
- Include relevant checks for environment.
- The script should validate that required tools are installed.
- The script should gracefully handle errors and provide useful error messages.
- The script should clean up temporary files and resources even if it fails.
- The script should be secure and follow best practices.

Now produce the improved script:
"""
        logger.info("Sending prompt to LLM")
        response = await llm.acall(prompt)
        raw_script = getattr(response, "content", response)
        
        # Extract the script from the response.
        if "```bash" in raw_script:
            extracted = raw_script.split("```bash")[1].split("```")[0].strip()
        elif "```sh" in raw_script:
            extracted = raw_script.split("```sh")[1].split("```")[0].strip()
        elif "```" in raw_script:
            extracted = raw_script.split("```")[1].strip()
        else:
            extracted = raw_script.strip()
        
        logger.info("Successfully optimized script with LLM")
        return extracted
    except Exception as e:
        logger.error(f"Error in LLM optimization: {e}")
        return script