# src/workflow_agent/scripting/optimizers/rule_based.py
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

async def rule_based_optimize(
    script: str,
    state: Any,
    system_context: Dict,
    history: List,
    stats: Dict
) -> str:
    """
    Apply simple rule-based optimizations to the script.
    
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
# Error handling function
error_exit() {
    local message="$1"
    local code="${2:-1}"
    echo "ERROR: $message" >&2
    exit "$code"
}
"""
            # Insert after set -e
            for i, line in enumerate(lines):
                if line.strip() == "set -e":
                    lines.insert(i+1, error_func)
                    break
            else:
                # Insert after shebang
                for i, line in enumerate(lines):
                    if line.startswith("#!"):
                        lines.insert(i+1, error_func)
                        break
        
        # Add logging function
        if not any("log_message" in line for line in lines):
            log_func = """
# Logging function
log_message() {
    local level="$1"
    local message="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message"
}
"""
            # Insert after error handling function or set -e
            for i, line in enumerate(lines):
                if "error_exit" in line and "}" in line:
                    lines.insert(i+1, log_func)
                    break
                elif line.strip() == "set -e" and not any("error_exit" in l for l in lines):
                    lines.insert(i+1, log_func)
                    break
        
        # Add check for required commands
        if not any("command -v" in line for line in lines):
            commands_to_check = []
            
            # Detect commands used in the script
            for line in lines:
                if line.strip() and not line.strip().startswith("#"):
                    # Extract command (first word after pipe or at start of line)
                    parts = line.split("|")
                    for part in parts:
                        words = part.strip().split()
                        if words and words[0] not in ["if", "then", "else", "fi", "for", "do", "done", "while", 
                                                     "case", "esac", "function", "echo", "set", "local", "export",
                                                     "return", "exit", "{", "}", "cd", "source", ":", "[", "[[",
                                                     "read", "printf", "eval"]:
                            commands_to_check.append(words[0])
            
            # Remove duplicates and common built-ins
            commands_to_check = list(set(commands_to_check))
            
            if commands_to_check:
                check_commands = "\n# Check for required commands"
                for cmd in commands_to_check:
                    check_commands += f"""
if ! command -v {cmd} &> /dev/null; then
    error_exit "{cmd} is required but not installed" 1
fi
"""
                
                # Insert after functions
                for i, line in enumerate(lines):
                    if (line.strip() == "" and i > 2 and
                        any(func in "\n".join(lines[:i]) for func in ["error_exit", "log_message"])):
                        lines.insert(i, check_commands)
                        break
                else:
                    # Insert after shebang and set -e
                    for i, line in enumerate(lines):
                        if line.strip() == "set -e":
                            lines.insert(i + 1, check_commands)
                            break
        
        # Add trap for cleanup
        if (state.action in ["install", "update"] and 
            not any("trap" in line and "EXIT" in line for line in lines)):
            
            cleanup_func = """
# Cleanup function
cleanup() {
    # Remove temporary files
    if [[ -d "${tmp_dir}" ]]; then
        rm -rf "${tmp_dir}"
        log_message "INFO" "Cleaned up temporary directory"
    fi
}

# Create a temporary directory
tmp_dir=$(mktemp -d)
log_message "INFO" "Created temporary directory: ${tmp_dir}"

# Set trap to clean up on exit
trap cleanup EXIT
"""
            
            # Insert after command checks or functions
            inserted = False
            for i, line in enumerate(lines):
                if "command -v" in line and "fi" in line and i < len(lines) - 1 and lines[i+1].strip() == "":
                    lines.insert(i+1, cleanup_func)
                    inserted = True
                    break
            
            if not inserted:
                for i, line in enumerate(lines):
                    if (line.strip() == "" and i > 2 and
                        any(func in "\n".join(lines[:i]) for func in ["error_exit", "log_message"])):
                        lines.insert(i, cleanup_func)
                        break
        
        # Add idempotency checks for common operations
        if state.action == "install":
            # For package installations
            for i, line in enumerate(lines):
                if ("apt-get install" in line or "yum install" in line) and "if" not in line:
                    package = line.split("install")[-1].strip().split()[0].strip()
                    if package != "-y":
                        package = package.replace("-y", "").strip()
                        check = f"""
# Check if {package} is already installed
if dpkg -l | grep -q "^ii\\s*{package}\\s" 2>/dev/null || rpm -q {package} &>/dev/null; then
    log_message "INFO" "{package} is already installed, skipping installation"
else
    log_message "INFO" "Installing {package}"
    {line}
fi
"""
                        lines[i] = check
        
        # Join lines back into script
        optimized_script = "\n".join(lines)
        
        logger.info("Rule-based optimization completed")
        return optimized_script
    except Exception as e:
        logger.error(f"Error in rule-based optimization: {e}")
        # Return original script if optimization fails
        return script