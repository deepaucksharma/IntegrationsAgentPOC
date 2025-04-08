"""
ImprovementAgent: Responsible for analyzing failures and improving templates.
"""
import logging
import re
import json
from typing import Dict, Any, Optional
from pathlib import Path
import os
import asyncio
import tempfile

from ..core.agents.base_agent import BaseAgent
from ..core.message_bus import MessageBus
from ..core.state import WorkflowState
from ..storage.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

class ImprovementAgent(BaseAgent):
    """
    Agent responsible for analyzing failures and generating improvements.
    """
    
    def __init__(self, message_bus: MessageBus, knowledge_base: Optional[KnowledgeBase] = None):
        super().__init__(message_bus, "ImprovementAgent")
        self.knowledge_base = knowledge_base or KnowledgeBase()
        self.learning_data = {}
        self.learning_path = None
        
        # Register message handlers
        self.register_handler("analyze_failure", self._handle_analyze_failure)
        self.register_handler("workflow_complete", self._handle_workflow_complete)
    
    async def initialize(self) -> None:
        """Initialize the improvement agent."""
        await super().initialize()
        
        try:
            storage_dir = os.path.join(os.path.dirname(__file__), "..", "storage")
            os.makedirs(storage_dir, exist_ok=True)
            self.learning_path = Path(storage_dir) / "learning_data.json"
        except Exception as e:
            logger.error(f"Error setting up learning path: {e}")
            self.learning_path = Path(tempfile.gettempdir()) / "workflow_learning_data.json"
            logger.warning(f"Using temporary learning path: {self.learning_path}")
            
        await self._load_learning_data()
        logger.info("ImprovementAgent initialization complete")
    
    async def _load_learning_data(self) -> None:
        """Load existing learning data."""
        if self.learning_path and self.learning_path.exists():
            try:
                with open(self.learning_path, "r") as f:
                    self.learning_data = json.load(f)
                logger.info(f"Loaded learning data with {len(self.learning_data)} entries")
            except Exception as e:
                logger.error(f"Error loading learning data: {e}")
                self.learning_data = {}
    
    async def _save_learning_data(self) -> None:
        """Save learning data to disk."""
        if not self.learning_path:
            logger.error("No learning path configured")
            return
            
        try:
            os.makedirs(self.learning_path.parent, exist_ok=True)
            with open(self.learning_path, "w") as f:
                json.dump(self.learning_data, f, indent=2)
            logger.info(f"Saved learning data with {len(self.learning_data)} entries")
        except Exception as e:
            logger.error(f"Error saving learning data: {e}")
    
    async def _handle_analyze_failure(self, message: Dict[str, Any]) -> None:
        workflow_id = message["workflow_id"]
        state_dict = message["state"]
        error = message.get("error", "Unknown error")
        try:
            state = WorkflowState(**state_dict)
            root_cause = await self._identify_root_cause(state, error)
            integration_key = f"{state.integration_type}_{state.target_name}_{state.action}"
            if integration_key not in self.learning_data:
                self.learning_data[integration_key] = {
                    "failures": [],
                    "successes": 0,
                    "improvements": []
                }
            self.learning_data[integration_key]["failures"].append({
                "error": error,
                "root_cause": root_cause,
                "timestamp": state.metrics.start_time if state.metrics else None,
                "system_context": state.system_context
            })
            improvement = await self._generate_improvement(state, root_cause)
            if improvement:
                self.learning_data[integration_key]["improvements"].append({
                    "root_cause": root_cause,
                    "improvement": improvement,
                    "timestamp": state.metrics.start_time if state.metrics else None
                })
                await self._apply_improvement(state, improvement)
                await self._save_learning_data()
                await self.publish("improvement_generated", {
                    "workflow_id": workflow_id,
                    "state": state.model_dump(),
                    "root_cause": root_cause,
                    "improvement": improvement
                })
            else:
                await self.publish("improvement_failed", {
                    "workflow_id": workflow_id,
                    "root_cause": root_cause
                })
                await self._save_learning_data()
        except Exception as e:
            logger.error(f"Error analyzing failure: {e}")
            await self.publish("error", {
                "workflow_id": workflow_id,
                "error": f"Error analyzing failure: {str(e)}"
            })
    
    async def _handle_workflow_complete(self, message: Dict[str, Any]) -> None:
        state_dict = message.get("state")
        status = message.get("status")
        if status == "completed" and state_dict:
            try:
                state = WorkflowState(**state_dict)
                integration_key = f"{state.integration_type}_{state.target_name}_{state.action}"
                if integration_key not in self.learning_data:
                    self.learning_data[integration_key] = {
                        "failures": [],
                        "successes": 0,
                        "improvements": []
                    }
                self.learning_data[integration_key]["successes"] += 1
                await self._save_learning_data()
            except Exception as e:
                logger.error(f"Error recording workflow completion: {e}")
    
    async def _identify_root_cause(self, state: WorkflowState, error: str) -> str:
        if not state.output:
            return "no_output"
        stderr = state.output.stderr.lower() if state.output.stderr else ""
        if "command not found" in stderr:
            if "apt" in stderr or "apt-get" in stderr:
                return "apt_not_found"
            elif "yum" in stderr:
                return "yum_not_found"
            elif "zypper" in stderr:
                return "zypper_not_found"
            elif "dnf" in stderr:
                return "dnf_not_found"
            return "command_not_found"
        if "no such file or directory" in stderr:
            return "file_not_found"
        if "permission denied" in stderr:
            return "permission_denied"
        if "could not resolve host" in stderr or "network unreachable" in stderr:
            return "network_error"
        if "service not found" in stderr or "unit not found" in stderr:
            return "service_not_found"
        return f"unknown_error: {error}"
    
    async def _generate_improvement(self, state: WorkflowState, root_cause: str) -> Optional[Dict[str, Any]]:
        if not state.script:
            return None
        if root_cause.endswith("_not_found"):
            if any(pm in root_cause for pm in ["apt", "yum", "zypper", "dnf"]):
                return await self._improve_package_manager_detection(state)
        if root_cause == "file_not_found":
            return await self._improve_file_paths(state)
        if root_cause == "permission_denied":
            return await self._improve_permissions(state)
        if root_cause == "network_error":
            return await self._improve_network_handling(state)
        if root_cause == "service_not_found":
            return await self._improve_service_management(state)
        return None
    
    async def _improve_package_manager_detection(self, state: WorkflowState) -> Dict[str, Any]:
        script_lines = state.script.split("\n")
        improved_script = []
        package_manager_detection = """
# Detect package manager
if command -v apt-get >/dev/null 2>&1; then
    PKG_MANAGER="apt-get"
    INSTALL_CMD="apt-get install -y"
    UPDATE_CMD="apt-get update"
elif command -v yum >/dev/null 2>&1; then
    PKG_MANAGER="yum"
    INSTALL_CMD="yum install -y"
    UPDATE_CMD="yum check-update || true"
elif command -v dnf >/dev/null 2>&1; then
    PKG_MANAGER="dnf"
    INSTALL_CMD="dnf install -y"
    UPDATE_CMD="dnf check-update || true"
elif command -v zypper >/dev/null 2>&1; then
    PKG_MANAGER="zypper"
    INSTALL_CMD="zypper install -y"
    UPDATE_CMD="zypper refresh"
else
    echo "No supported package manager found"
    exit 1
fi
"""
        for i, line in enumerate(script_lines):
            if line.startswith("#!/"):
                improved_script.append(line)
                improved_script.append(package_manager_detection)
                continue
            if "apt-get install" in line:
                line = line.replace("apt-get install", "$INSTALL_CMD")
            elif "yum install" in line:
                line = line.replace("yum install", "$INSTALL_CMD")
            elif "zypper install" in line:
                line = line.replace("zypper install", "$INSTALL_CMD")
            elif "dnf install" in line:
                line = line.replace("dnf install", "$INSTALL_CMD")
            if "apt-get update" in line:
                line = line.replace("apt-get update", "$UPDATE_CMD")
            elif "yum check-update" in line:
                line = line.replace("yum check-update", "$UPDATE_CMD")
            elif "zypper refresh" in line:
                line = line.replace("zypper refresh", "$UPDATE_CMD")
            elif "dnf check-update" in line:
                line = line.replace("dnf check-update", "$UPDATE_CMD")
            improved_script.append(line)
        return {
            "type": "script_improvement",
            "original_script": state.script,
            "improved_script": "\n".join(improved_script),
            "description": "Added package manager detection and dynamic commands"
        }
    
    async def _improve_file_paths(self, state: WorkflowState) -> Dict[str, Any]:
        import re
        script_lines = state.script.split("\n")
        improved_script = []
        for line in script_lines:
            if re.search(r"\bcat\s+\S+", line) or re.search(r"\brm\s+\S+", line):
                match = re.search(r"\b(cat|rm)\s+(\S+)", line)
                if match:
                    command = match.group(1)
                    file_path = match.group(2)
                    if line.strip().startswith("if"):
                        improved_script.append(line)
                        continue
                    if "$" in file_path or file_path.startswith("/dev/"):
                        improved_script.append(line)
                        continue
                    improved_script.append(f"if [ -f {file_path} ]; then")
                    improved_script.append(f"  {line}")
                    improved_script.append("else")
                    improved_script.append(f"  echo \"Warning: {file_path} not found, skipping {command}\"")
                    improved_script.append("fi")
                    continue
            improved_script.append(line)
        return {
            "type": "script_improvement",
            "original_script": state.script,
            "improved_script": "\n".join(improved_script),
            "description": "Added file existence checks for critical operations"
        }
    
    async def _improve_permissions(self, state: WorkflowState) -> Dict[str, Any]:
        script_lines = state.script.split("\n")
        improved_script = []
        for line in script_lines:
            if "sudo" in line:
                improved_script.append(line)
                continue
            if any(cmd in line for cmd in ["systemctl", "service", "chown", "chmod", "mkdir /etc", "touch /etc"]):
                if line.strip().startswith("if"):
                    improved_script.append(line)
                    continue
                if line.strip() and not line.strip().startswith("#"):
                    improved_script.append(f"sudo {line}")
                    continue
            improved_script.append(line)
        return {
            "type": "script_improvement",
            "original_script": state.script,
            "improved_script": "\n".join(improved_script),
            "description": "Added sudo for privileged operations"
        }
    
    async def _improve_network_handling(self, state: WorkflowState) -> Dict[str, Any]:
        script_lines = state.script.split("\n")
        improved_script = []
        retry_function = """
# Retry function for network operations
retry_command() {
    local max_attempts=3
    local attempt=1
    local delay=5
    local command="$@"
    while [ $attempt -le $max_attempts ]; do
        echo "Attempt $attempt/$max_attempts: $command"
        eval $command && return 0
        echo "Command failed, retrying in $delay seconds..."
        sleep $delay
        attempt=$((attempt + 1))
        delay=$((delay * 2))
    done
    echo "Command failed after $max_attempts attempts: $command"
    return 1
}
"""
        for i, line in enumerate(script_lines):
            if i == 0 and line.startswith("#!/"):
                improved_script.append(line)
                improved_script.append(retry_function)
                continue
            if any(cmd in line for cmd in ["curl", "wget", "apt-get update", "yum update", "http"]):
                if line.strip().startswith("#") or line.strip().startswith("if") or "retry_command" in line:
                    improved_script.append(line)
                    continue
                if line.strip():
                    improved_script.append(f"retry_command '{line.strip()}'")
                    continue
            improved_script.append(line)
        return {
            "type": "script_improvement",
            "original_script": state.script,
            "improved_script": "\n".join(improved_script),
            "description": "Added retry mechanism for network operations"
        }
    
    async def _improve_service_management(self, state: WorkflowState) -> Dict[str, Any]:
        import re
        script_lines = state.script.split("\n")
        improved_script = []
        for i, line in enumerate(script_lines):
            if "systemctl start" in line or "service start" in line:
                match = re.search(r"(systemctl|service)\s+start\s+(\S+)", line)
                if match:
                    cmd_type = match.group(1)
                    service_name = match.group(2)
                    if i > 0 and script_lines[i-1].strip().startswith("if"):
                        improved_script.append(line)
                        continue
                    if cmd_type == "systemctl":
                        improved_script.append(f"if systemctl list-unit-files | grep -q {service_name}; then")
                        improved_script.append(f"  {line}")
                        improved_script.append("else")
                        improved_script.append(f"  echo \"Service {service_name} not found\"")
                        improved_script.append("fi")
                    else:
                        improved_script.append(f"if command -v service >/dev/null 2>&1 && service {service_name} status >/dev/null 2>&1; then")
                        improved_script.append(f"  {line}")
                        improved_script.append("else")
                        improved_script.append(f"  echo \"Service {service_name} not found\"")
                        improved_script.append("fi")
                    continue
            improved_script.append(line)
        return {
            "type": "script_improvement",
            "original_script": state.script,
            "improved_script": "\n".join(improved_script),
            "description": "Added service existence checks before operations"
        }
    
    async def _apply_improvement(self, state: WorkflowState, improvement: Dict[str, Any]) -> None:
        await self.knowledge_base.add_improvement(
            integration_type=state.integration_type,
            target_name=state.target_name,
            improvement=improvement
        )
        if improvement["type"] == "script_improvement" and "improved_script" in improvement:
            logger.info(f"Would update template for {state.integration_type}/{state.target_name} with {improvement['description']}")
            
    async def cleanup(self) -> None:
        """Clean up resources and save learning data."""
        await self._save_learning_data()
        await super().cleanup()
        logger.info("ImprovementAgent cleanup complete")
