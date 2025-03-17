# src/workflow_agent/scripting/optimizers/shellcheck.py
import os
import uuid
import logging
import tempfile
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

async def shellcheck_optimize(
    script: str,
    state: Any,
    system_context: Dict,
    history: List,
    stats: Dict
) -> str:
    """
    Optimize script using ShellCheck static analyzer.
    
    Args:
        script: Original script content
        state: Current workflow state
        system_context: System context information
        history: Execution history
        stats: Execution statistics
    
    Returns:
        Optimized script
    """
    try:
        import shellcheck_py
    except ImportError:
        logger.warning("ShellCheck not available, skipping optimization")
        return script
    
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
        fixed_header = None
        
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