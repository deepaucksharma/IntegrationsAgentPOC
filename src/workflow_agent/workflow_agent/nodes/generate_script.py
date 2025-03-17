import os
import time
import json
import asyncio
import uuid
import importlib
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Union
from jinja2 import Template, Environment, FileSystemLoader, TemplateError
import logging
from ..state import WorkflowState, Change
from ..configuration import ensure_workflow_config, script_templates, load_templates
from ..history import get_execution_history, get_execution_statistics
from ..system_context import get_system_context
from ..integration_handler import IntegrationHandler

logger = logging.getLogger(__name__)

# Check for OpenAI API key - required for LLM optimization
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Global variable for script optimizers
SCRIPT_OPTIMIZERS = {}

def register_optimizer(name: str, optimizer_func: Callable):
    """
    Register a script optimizer function.
    
    Args:
        name: Name for the optimizer
        optimizer_func: Function that optimizes scripts
    """
    SCRIPT_OPTIMIZERS[name] = optimizer_func
    logger.debug(f"Registered script optimizer: {name}")

# Try to import and register optimizers
try:
    # LangChain OpenAI optimizer
    if OPENAI_API_KEY:
        try:
            from langchain_openai import ChatOpenAI
            
            async def llm_optimize(script: str, state: WorkflowState, system_context: Dict, history: List, stats: Dict) -> str:
                """Optimize script using LangChain OpenAI."""
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
1) Return only a valid bash script (no markdown, no explanations).
2) Add robust error handling and logging.
3) Make it idempotent.
4) Include relevant checks for environment.
5) The script should validate that required tools are installed.
6) The script should gracefully handle errors and provide useful error messages.
7) The script should clean up temporary files and resources even if it fails.
8) The script should be secure and follow best practices.

Now produce the improved script:
"""
                try:
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
                    raise e
            
            register_optimizer("llm", llm_optimize)
            logger.info("Registered LangChain OpenAI optimizer")
        except ImportError:
            logger.warning("LangChain OpenAI module not available.")
    
    # Register ShellCheck static analyzer optimizer
    try:
        import shellcheck_py
        
        async def shellcheck_optimize(script: str, state: WorkflowState, system_context: Dict, history: List, stats: Dict) -> str:
            """Optimize script using ShellCheck static analyzer."""
            try:
                logger.info("Running ShellCheck static analysis")
                
                # Create a temporary file for the script
                script_path = f"/tmp/workflow_script_{uuid.uuid4()}.sh"
                with open(script_path, "w") as f:
                    f.write(script)
                
                # Run ShellCheck
                result = shellcheck_py.parse(script_path)
                
                # If no issues found, return original script
                if not result:
                    logger.info("ShellCheck found no issues")
                    return script
                
                # Generate fixes for the issues
                fixed_script = script
                for issue in sorted(result, key=lambda x: (x.get("line", 0), x.get("column", 0)), reverse=True):
                    line = issue.get("line", 0)
                    column = issue.get("column", 0)
                    code = issue.get("code", "")
                    message = issue.get("message", "")
                    
                    # Log the issue
                    logger.debug(f"ShellCheck issue: {code} at line {line}, column {column}: {message}")
                    
                    # Add header comment with summary of fixes
                    if "fixed_header" not in locals():
                        fixed_header = f"""#!/usr/bin/env bash
# Script optimized with ShellCheck static analysis
# Original issues:
"""
                        for i, issue in enumerate(result):
                            fixed_header += f"# {i+1}. {issue.get('code', '')}: {issue.get('message', '')}\n"
                        fixed_header += "\n"
                        fixed_script = fixed_header + fixed_script
                    
                    # Apply common fixes based on code
                    if code == "SC2086":  # Double quote to prevent globbing and word splitting
                        script_lines = fixed_script.split("\n")
                        if 0 < line <= len(script_lines):
                            # Add double quotes around variable references
                            if "$(" in script_lines[line-1] and ")" in script_lines[line-1][column:]:
                                # Handle command substitution
                                pass
                            elif "${" in script_lines[line-1] and "}" in script_lines[line-1][column:]:
                                # Handle parameter expansion
                                pass
                            else:
                                # Simple variable
                                var_start = script_lines[line-1].rfind("$", 0, column)
                                if var_start >= 0:
                                    var_end = column
                                    for i in range(column, len(script_lines[line-1])):
                                        if not (script_lines[line-1][i].isalnum() or script_lines[line-1][i] == '_'):
                                            var_end = i
                                            break
                                    
                                    var = script_lines[line-1][var_start:var_end]
                                    script_lines[line-1] = script_lines[line-1][:var_start] + '"' + var + '"' + script_lines[line-1][var_end:]
                            
                            fixed_script = "\n".join(script_lines)
                    
                    # Add explicit error handling for common issues
                    elif code == "SC2015":  # Use || true to avoid exiting on non-zero status
                        script_lines = fixed_script.split("\n")
                        if 0 < line <= len(script_lines) and " && " in script_lines[line-1]:
                            # Add explicit error handling
                            script_lines[line-1] = script_lines[line-1].replace(" && ", " && true || ")
                            fixed_script = "\n".join(script_lines)
                
                # Always add set -e if not present
                if "set -e" not in fixed_script:
                    lines = fixed_script.split("\n")
                    for i, line in enumerate(lines):
                        if line.startswith("#!"):
                            lines.insert(i+1, "set -e")
                            break
                    else:
                        lines.insert(0, "set -e")
                    fixed_script = "\n".join(lines)
                
                # Always add error handling function if not present
                if "function error_exit" not in fixed_script and "error_exit()" not in fixed_script:
                    error_func = """
# Error handling function
error_exit() {
    local message="$1"
    local code="${2:-1}"
    echo "ERROR: $message" >&2
    exit "$code"
}
"""
                    lines = fixed_script.split("\n")
                    for i, line in enumerate(lines):
                        if line.startswith("set -e") or (i > 0 and lines[i-1].startswith("#!") and not line.startswith("#")):
                            lines.insert(i+1, error_func)
                            break
                    fixed_script = "\n".join(lines)
                
                logger.info("ShellCheck optimization completed")
                
                # Clean up temporary file
                try:
                    os.remove(script_path)
                except:
                    pass
                
                return fixed_script
            except Exception as e:
                logger.error(f"Error in ShellCheck optimization: {e}")
                # Return original script if optimization fails
                return script
        
        register_optimizer("shellcheck", shellcheck_optimize)
        logger.info("Registered ShellCheck optimizer")
    except ImportError:
        logger.warning("ShellCheck module not available.")
    
    # Simple rule-based optimizer
    async def rule_based_optimize(script: str, state: WorkflowState, system_context: Dict, history: List, stats: Dict) -> str:
        """Apply simple rule-based optimizations to the script."""
        try:
            logger.info("Applying rule-based optimizations")
            
            # Split into lines for easier processing
            lines = script.split("\n")
            
            # Add shebang if missing
            if not any(line.startswith("#!/") for line in lines):
                lines.insert(0, "#!/usr/bin/env bash")
            
            # Add set -e if missing
            if not any(line.strip() == "set -e" for line in lines):
                # Insert after shebang
                for i, line in enumerate(lines):
                    if line.startswith("#!"):
                        lines.insert(i+1, "set -e")
                        break
                else:
                    lines.insert(1, "set -e")
            
            # Add basic error handling function
            if not any("error_exit" in line for line in lines):
                error_func = """
error_exit() {
    echo "ERROR: $1" >&2
    exit 1
}
"""
                lines.insert(2, error_func)
            
            # Replace echo with printf for better formatting
            for i, line in enumerate(lines):
                if line.startswith("echo "):
                    lines[i] = "printf '%s\\n' " + line[5:]
            
            # Rejoin the lines
            script = "\n".join(lines)
            
            logger.info("Rule-based optimizations applied")
            return script
        except Exception as e:
            logger.error(f"Error applying rule-based optimizations: {e}")
            return script
    
    register_optimizer("rule_based", rule_based_optimize)
    logger.info("Registered rule-based optimizer")
except Exception as e:
    logger.warning(f"Failed to load script optimizers: {e}")

async def generate_script(state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Generates a script based on the workflow state and configuration.
    
    This function uses Jinja2 templates to generate the script.
    It also applies script optimizations if enabled.
    
    Args:
        state: Current workflow state
        config: Optional configuration
        
    Returns:
        Dict with the generated script or an error message
    """
    try:
        # Load script templates
        templates = script_templates()
        
        # Get the template based on the integration type and action
        template_name = f"{state.integration_type}_{state.action}.sh.j2"
        template = templates.get(template_name)
        if not template:
            template_name = f"default_{state.action}.sh.j2"
            template = templates.get(template_name)
        if not template:
            template_name = "default.sh.j2"
            template = templates.get(template_name)
        if not template:
            error_msg = f"No script template found for integration type '{state.integration_type}' and action '{state.action}'"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Prepare template variables
        template_vars: Dict[str, Any] = {
            "state": state,
            "config": config,
            "system_context": get_system_context(),
            "timestamp": int(time.time()),
            "uuid": str(uuid.uuid4())
        }
        
        # Render the template
        try:
            rendered_script = template.render(template_vars)
        except TemplateError as e:
            error_msg = f"Error rendering script template: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Apply script optimizations
        if config and config.get("script_optimization", True):
            history = get_execution_history(state.target_name, state.action, limit=10, user_id=state.user_id)
            stats = get_execution_statistics(state.target_name, state.action, user_id=state.user_id)
            
            for optimizer_name in config.get("script_optimizers", ["llm", "shellcheck", "rule_based"]):
                optimizer_func = SCRIPT_OPTIMIZERS.get(optimizer_name)
                if optimizer_func:
                    try:
                        logger.info(f"Applying optimizer: {optimizer_name}")
                        rendered_script = await optimizer_func(rendered_script, state, get_system_context(), history, stats)
                    except Exception as e:
                        logger.warning(f"Optimizer {optimizer_name} failed: {e}")
        
        return {"script": rendered_script}
    except Exception as e:
        logger.error(f"Error generating script: {e}")
        return {"error": str(e)}