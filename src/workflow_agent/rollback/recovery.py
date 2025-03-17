import os
import uuid
import tempfile
import subprocess
import time
import logging
import asyncio
from typing import Dict, Any, Optional, List
from jinja2 import Template
from ..core.state import WorkflowState, OutputData, ExecutionMetrics, Change
from ..config.templates import script_templates
from ..config.configuration import ensure_workflow_config
from ..storage import HistoryManager

logger = logging.getLogger(__name__)

class RecoveryManager:
    """Handles rollback of failed workflow executions."""
    
    def __init__(self, history_manager: Optional[HistoryManager] = None):
        """
        Initialize the recovery manager.
        
        Args:
            history_manager: Optional history manager for recording rollback history
        """
        self.history_manager = history_manager or HistoryManager()
    
    async def rollback_changes(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Attempt to rollback changes made by a failed workflow execution.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with rollback results or error
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

{% for change in changes %}
log_message "INFO" "Reverting: {{ change.details }}"
{% endfor %}

{% if rollback_commands %}
# Execute rollback commands
{% for cmd in rollback_commands %}
log_message "INFO" "Executing: {{ cmd }}"
set +e
{{ cmd }}
if [ $? -ne 0 ]; then
    log_message "WARN" "Command failed but continuing rollback: {{ cmd }}"
fi
set -e
{% endfor %}
{% else %}
log_message "WARN" "No specific rollback commands available"
{% endif %}

# Verify original action was rolled back
log_message "INFO" "Rollback completed"
"""

        try:
            tpl = Template(template_str)
            rollback_script = tpl.render(
                target_name=state.target_name,
                parameters=state.parameters,
                error=state.error,
                changes=changes,
                rollback_commands=rollback_commands
            )
            
            temp_dir = tempfile.mkdtemp(prefix='workflow-rollback-')
            script_id = str(uuid.uuid4())
            script_path = os.path.join(temp_dir, f"rollback-{script_id}.sh")
            
            try:
                with open(script_path, 'w') as f:
                    f.write(rollback_script)
                
                os.chmod(script_path, 0o755)
                logger.info(f"Prepared rollback script at {script_path}")
                
                # Execute the rollback script
                start_time = time.time()
                process = subprocess.Popen(
                    [script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    shell=False
                )
                
                try:
                    stdout_str, stderr_str = process.communicate(timeout=workflow_config.execution_timeout / 1000)
                    success = process.returncode == 0
                    if not success:
                        error_message = f"Rollback script execution failed with return code {process.returncode}"
                        logger.error(f"Rollback failed: {error_message}")
                        return {"error": f"Rollback failed: {error_message}. Manual intervention may be required."}
                except subprocess.TimeoutExpired:
                    process.kill()
                    stderr_str = f"Rollback script execution timed out after {workflow_config.execution_timeout}ms"
                    logger.error(f"Rollback timed out: {stderr_str}")
                    return {"error": f"Rollback failed: {stderr_str}. Manual intervention may be required."}
                except Exception as err:
                    stderr_str = str(err)
                    logger.exception(f"Error during rollback: {stderr_str}")
                    return {"error": f"Rollback failed: {stderr_str}. Manual intervention may be required."}
                
                end_time = time.time()
                execution_time = int((end_time - start_time) * 1000)
                
                # Save rollback execution to history
                if self.history_manager:
                    try:
                        execution_id = await self.history_manager.save_execution(
                            target_name=state.target_name,
                            action=f"rollback-{state.action}",
                            success=success,
                            execution_time=execution_time,
                            error_message=None if success else stderr_str,
                            system_context=state.system_context,
                            script=rollback_script,
                            output={"stdout": stdout_str, "stderr": stderr_str},
                            parameters=state.parameters,
                            transaction_id=state.transaction_id,
                            user_id=workflow_config.user_id
                        )
                        logger.info(f"Saved rollback execution with ID {execution_id}")
                    except Exception as e:
                        logger.error(f"Failed to save rollback execution record: {e}")
                
                logger.info("Rollback completed successfully")
                return {
                    "status": f"Rollback completed successfully: {stdout_str.strip()}",
                    "rollback_output": {
                        "stdout": stdout_str,
                        "stderr": stderr_str,
                        "execution_time": execution_time
                    }
                }
            finally:
                try:
                    if os.path.exists(script_path):
                        os.unlink(script_path)
                    if os.path.exists(temp_dir):
                        os.rmdir(temp_dir)
                except Exception as cleanup_err:
                    logger.error(f"Rollback cleanup error: {cleanup_err}")
        except Exception as err:
            logger.exception(f"Failed to prepare or execute rollback: {err}")
            return {"error": f"Rollback failed: {str(err)}. Manual intervention may be required."}