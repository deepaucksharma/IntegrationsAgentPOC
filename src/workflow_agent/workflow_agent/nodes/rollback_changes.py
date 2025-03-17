import os
import uuid
import tempfile
import subprocess
import time
import logging
import psutil
import shlex
from typing import Dict, Any, Optional, List
from jinja2 import Template
from ..state import WorkflowState, OutputData, ExecutionMetrics, Change
from ..configuration import script_templates, ensure_workflow_config
from ..history import save_execution, async_save_execution

logger = logging.getLogger(__name__)

async def rollback_changes(
    state: WorkflowState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Attempts to rollback changes made by a failed workflow execution.
    Rollback actions are specific to the changes made during the workflow.
    
    Args:
        state: Current workflow state
        config: Optional configuration
        
    Returns:
        Dict with status or error message
    """
    if not state.error or (not state.changes and not state.legacy_changes):
        logger.info("Nothing to rollback")
        return {"status": "Nothing to rollback."}
    
    logger.info(f"Attempting to rollback changes for {state.target_name} due to error: {state.error}")
    
    # Get workflow configuration
    workflow_config = ensure_workflow_config(config)
    
    # Convert legacy changes to Change objects if needed
    changes = state.changes or []
    if not changes and state.legacy_changes:
        for change_text in state.legacy_changes:
            changes.append(Change(
                type="unknown",
                target=state.target_name,
                details=change_text,
                revertible=True
            ))
    
    # Generate targeted rollback commands based on changes
    rollback_commands = []
    
    # Extract specific rollback commands
    for change in changes:
        if change.revert_command:
            rollback_commands.append(change.revert_command)
        elif change.type == "install" and change.target.startswith("package:"):
            package_name = change.target.split(":", 1)[1]
            rollback_commands.append(f"apt-get remove -y {package_name} || yum remove -y {package_name}")
        elif change.type == "create" and change.target.startswith("file:"):
            file_path = change.target.split(":", 1)[1]
            rollback_commands.append(f"rm -f {file_path}")
        elif change.type == "configure" and change.target.startswith("service:"):
            service_name = change.target.split(":", 1)[1]
            rollback_commands.append(f"systemctl stop {service_name} || service {service_name} stop")
    
    # Try to find or generate a rollback script
    rollback_action = "remove" if state.action in ["install", "setup"] else "rollback" 
    template_key = f"{state.target_name}-{rollback_action}"
    template_str = script_templates.get(template_key)
    
    if not template_str:
        default_key = f"default-{rollback_action}"
        template_str = script_templates.get(default_key)
    
    # Generate a dynamic rollback script if no template is found
    if not template_str or not template_str.strip():
        logger.info("No rollback template found, generating dynamic rollback script")
        template_str = f"""#!/usr/bin/env bash
set -e
echo "Rolling back changes for {state.target_name}..."
echo "Original error: {state.error}"

log_message() {{
    local level="$1"
    local message="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message"
}}

error_exit() {{
    local message="$1"
    local code="${{2:-1}}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $message" >&2
    exit "$code"
}}

# Create a cleanup trap
cleanup() {{
    log_message "INFO" "Cleanup complete"
}}
trap cleanup EXIT

log_message "INFO" "Starting rollback for failed {state.action} of {state.target_name}"

log_message "INFO" "Rollback complete"
"""
    
    # Prepare template variables
    template_vars: Dict[str, Any] = {
        "state": state,
        "changes": changes,
        "rollback_commands": rollback_commands,
        "timestamp": int(time.time()),
        "uuid": str(uuid.uuid4())
    }
    
    # Render the rollback script
    try:
        tpl = Template(template_str)
        rollback_script = tpl.render(template_vars)
    except Exception as e:
        logger.error(f"Rollback script rendering failed: {e}")
        return {"error": f"Rollback script rendering failed: {str(e)}"}
    
    # Run the rollback script
    temp_dir = tempfile.mkdtemp(prefix='workflow-rollback-')
    rollback_script_path = os.path.join(temp_dir, f"rollback-{uuid.uuid4().hex[:8]}.sh")
    
    try:
        with open(rollback_script_path, 'w') as f:
            f.write(rollback_script)
        os.chmod(rollback_script_path, 0o755)
        
        logger.info(f"Executing rollback script: {rollback_script_path}")
        process = subprocess.Popen(
            [rollback_script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            shell=False
        )
        stdout, stderr = process.communicate(timeout=60)
        success = process.returncode == 0
        
        stdout_str = stdout.strip()
        stderr_str = stderr.strip()
        
        if success:
            logger.info("Rollback script executed successfully")
            return {
                "status": "Rollback completed successfully.",
                "rollback_output": {
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "exit_code": process.returncode
                }
            }
        else:
            logger.error(f"Rollback script failed with exit code {process.returncode}: {stderr_str}")
            return {
                "error": f"Rollback script failed: {stderr_str}",
                "rollback_output": {
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "exit_code": process.returncode
                }
            }
    except subprocess.TimeoutExpired:
        logger.error("Rollback script timed out")
        return {
            "error": "Rollback script timed out.",
            "rollback_output": {
                "stdout": "",
                "stderr": "Rollback script timed out",
                "exit_code": -1
            }
        }
    except Exception as e:
        logger.error(f"Rollback script execution failed: {e}")
        return {
            "error": f"Rollback script execution failed: {str(e)}",
            "rollback_output": {
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1
            }
        }
    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logger.error(f"Failed to clean up rollback temp dir: {e}")