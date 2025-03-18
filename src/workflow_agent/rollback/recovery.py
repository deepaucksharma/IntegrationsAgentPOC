"""Recovery and rollback functionality for workflow agent."""
import os
import uuid
import tempfile
import time
import logging
import asyncio
from typing import Dict, Any, Optional, List
from jinja2 import Template

from ..core.state import WorkflowState, Change
from ..config.configuration import ensure_workflow_config
from ..config.templates import get_template

logger = logging.getLogger(__name__)

class RecoveryManager:
    """Handles rollback of failed workflow executions."""
    
    def __init__(self, history_manager=None):
        self.history_manager = history_manager
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        if self.history_manager:
            await self.history_manager.initialize(config)
    
    async def cleanup(self) -> None:
        if self.history_manager:
            await self.history_manager.cleanup()
    
    async def rollback_changes(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not state.error or (not state.changes and not state.legacy_changes):
            logger.info("Nothing to rollback")
            return {"status": "Nothing to rollback."}
        
        logger.info(f"Attempting to rollback changes for {state.target_name} due to error: {state.error}")
        workflow_config = ensure_workflow_config(config or {})
        
        changes = state.changes or []
        if not changes and state.legacy_changes:
            for change_text in state.legacy_changes:
                changes.append(Change(
                    type="unknown",
                    target=state.target_name,
                    details=change_text,
                    revertible=True
                ))
        
        rollback_commands = []
        for change in changes:
            if change.revert_command:
                rollback_commands.append(change.revert_command)
            elif change.type == "install" and hasattr(change, 'target') and change.target.startswith("package:"):
                pkg_name = change.target.split(":", 1)[1]
                rollback_commands.append(f"apt-get remove -y {pkg_name} || yum remove -y {pkg_name}")
            elif change.type == "create" and hasattr(change, 'target') and change.target.startswith("file:"):
                file_path = change.target.split(":", 1)[1]
                rollback_commands.append(f"rm -f {file_path}")
            elif change.type == "configure" and hasattr(change, 'target') and change.target.startswith("service:"):
                svc_name = change.target.split(":", 1)[1]
                rollback_commands.append(f"systemctl stop {svc_name} || service {svc_name} stop")
        
        rollback_action = "remove" if state.action in ["install", "setup"] else "rollback"
        template_key = f"{state.target_name}-{rollback_action}"
        template_str = get_template(template_key)
        if not template_str:
            default_key = f"default-{rollback_action}"
            template_str = get_template(default_key)
        if not template_str or not template_str.strip():
            logger.info("No rollback template found, generating dynamic rollback script")
            template_str = """#!/usr/bin/env bash
set -e
echo "Rolling back changes for {{ target_name }}..."
echo "Original error: {{ error }}"

{% for cmd in rollback_commands %}
echo "Executing: {{ cmd }}"
{{ cmd }} || echo "Command failed but continuing rollback: {{ cmd }}"
{% endfor %}

echo "Rollback completed"
"""
        with tempfile.TemporaryDirectory(prefix='workflow-rollback-') as temp_dir:
            script_id = str(uuid.uuid4())
            script_path = os.path.join(temp_dir, f"rollback-{script_id}.sh")
            try:
                tpl = Template(template_str)
                rollback_script = tpl.render(
                    target_name=state.target_name,
                    parameters=state.parameters,
                    error=state.error or "",
                    changes=changes,
                    rollback_commands=rollback_commands,
                    action=state.action
                )
                with open(script_path, 'w') as f:
                    f.write(rollback_script)
                os.chmod(script_path, 0o755)
                process = await asyncio.create_subprocess_exec(
                    script_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                try:
                    stdout, stderr = await asyncio.wait_for(process.communicate(),
                                                            timeout=workflow_config.execution_timeout / 1000)
                    stdout_str = stdout.decode('utf-8')
                    stderr_str = stderr.decode('utf-8')
                    success = process.returncode == 0
                    if not success:
                        error_message = f"Rollback script execution failed with return code {process.returncode}"
                        logger.error(f"Rollback failed: {error_message}")
                        return {"error": f"Rollback failed: {error_message}. Manual intervention may be required."}
                except asyncio.TimeoutError:
                    process.kill()
                    stderr_str = f"Rollback script execution timed out after {workflow_config.execution_timeout}ms"
                    logger.error(f"Rollback timed out: {stderr_str}")
                    return {"error": f"Rollback failed: {stderr_str}. Manual intervention may be required."}
                if self.history_manager:
                    try:
                        execution_id = await self.history_manager.save_execution(
                            target_name=state.target_name,
                            action=f"rollback-{state.action}",
                            success=True,
                            execution_time=int(workflow_config.execution_timeout),
                            error_message=None,
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
                    "status": "Rollback completed successfully",
                    "rollback_output": {
                        "stdout": stdout_str,
                        "stderr": stderr_str
                    }
                }
            except Exception as err:
                logger.exception(f"Failed to prepare or execute rollback: {err}")
                return {"error": f"Rollback failed: {str(err)}. Manual intervention may be required."}