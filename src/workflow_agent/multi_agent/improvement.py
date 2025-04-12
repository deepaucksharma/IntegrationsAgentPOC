"""
ImprovementAgent: Responsible for analyzing failures and improving templates.
Implements the ImprovementAgentInterface from the multi-agent system.
"""
import logging
import re
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
import os
import asyncio
import tempfile

from .interfaces import ImprovementAgentInterface
from ..core.message_bus import MessageBus
from ..core.state import WorkflowState
from ..storage.knowledge_base import KnowledgeBase
from ..error.handler import handle_safely_async

logger = logging.getLogger(__name__)

class ImprovementAgent(ImprovementAgentInterface):
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
            
    # Implement ImprovementAgentInterface required methods
    @handle_safely_async
    async def analyze_performance(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze system performance and identify areas for improvement.
        
        Args:
            metrics: Performance metrics to analyze
            
        Returns:
            Analysis results
        """
        logger.info(f"Analyzing performance metrics")
        
        # Extract key metrics
        integration_type = metrics.get("integration_type", "unknown")
        target_name = metrics.get("target_name", "unknown")
        action = metrics.get("action", "unknown")
        execution_time = metrics.get("execution_time", 0)
        error_count = metrics.get("error_count", 0)
        warning_count = metrics.get("warning_count", 0)
        success_rate = metrics.get("success_rate", 0)
        
        # Create integration key for learning data
        integration_key = f"{integration_type}_{target_name}_{action}"
        
        # Get historical data if available
        historical_data = {}
        if integration_key in self.learning_data:
            historical_data = self.learning_data[integration_key]
            
        # Analyze performance against historical data
        analysis = {
            "integration_type": integration_type,
            "target_name": target_name,
            "action": action,
            "execution_time": execution_time,
            "historical_comparisons": {}
        }
        
        # Add performance insights
        if historical_data:
            analysis["historical_comparisons"] = {
                "success_rate_change": self._calculate_success_rate_change(historical_data, success_rate),
                "average_execution_time": self._calculate_avg_execution_time(historical_data),
                "execution_time_trend": self._determine_execution_time_trend(historical_data, execution_time),
                "common_failures": self._identify_common_failures(historical_data)
            }
            
        # Identify areas for improvement
        analysis["improvement_areas"] = []
        
        # High error rate indicates reliability issues
        if error_count > 0 or success_rate < 0.9:
            analysis["improvement_areas"].append({
                "area": "reliability",
                "severity": "high" if success_rate < 0.7 else "medium",
                "description": "Success rate is below target threshold"
            })
            
        # Long execution time indicates performance issues
        if execution_time > 30 and (historical_data.get("avg_execution_time", 0) == 0 or 
                                   execution_time > historical_data.get("avg_execution_time", 0) * 1.5):
            analysis["improvement_areas"].append({
                "area": "performance",
                "severity": "medium", 
                "description": "Execution time is significantly higher than expected"
            })
            
        # Warnings indicate potential issues
        if warning_count > 0:
            analysis["improvement_areas"].append({
                "area": "robustness",
                "severity": "low",
                "description": f"{warning_count} warnings were generated during execution"
            })
            
        return analysis
        
    @handle_safely_async
    async def generate_improvements(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate specific improvement suggestions based on analysis.
        
        Args:
            analysis: Performance analysis
            
        Returns:
            List of improvement suggestions
        """
        logger.info(f"Generating improvements based on analysis")
        
        improvement_suggestions = []
        integration_type = analysis.get("integration_type", "unknown")
        target_name = analysis.get("target_name", "unknown")
        action = analysis.get("action", "unknown")
        
        # Get improvement areas from the analysis
        improvement_areas = analysis.get("improvement_areas", [])
        historical_comparisons = analysis.get("historical_comparisons", {})
        
        # Generate improvements based on identified areas
        for area in improvement_areas:
            area_name = area.get("area")
            severity = area.get("severity")
            
            if area_name == "reliability":
                # Generate reliability improvements
                if historical_comparisons.get("common_failures"):
                    common_failures = historical_comparisons["common_failures"]
                    
                    for failure in common_failures:
                        root_cause = failure.get("root_cause")
                        # Generate improvement based on root cause
                        if root_cause == "file_not_found":
                            improvement_suggestions.append({
                                "type": "reliability",
                                "area": "file_handling",
                                "description": "Add file existence checks before operations",
                                "implementation": "Wrap file operations in existence checks to prevent failures",
                                "severity": severity
                            })
                        elif root_cause == "permission_denied":
                            improvement_suggestions.append({
                                "type": "reliability",
                                "area": "permissions",
                                "description": "Add permission checks and privilege escalation",
                                "implementation": "Check for permissions before operations and use sudo when needed",
                                "severity": severity
                            })
                        elif root_cause == "network_error":
                            improvement_suggestions.append({
                                "type": "reliability",
                                "area": "network",
                                "description": "Add retry mechanism for network operations",
                                "implementation": "Implement exponential backoff retry for network calls",
                                "severity": severity
                            })
                        elif "not_found" in root_cause:
                            improvement_suggestions.append({
                                "type": "reliability",
                                "area": "dependencies",
                                "description": "Add dependency detection and installation",
                                "implementation": "Check for required tools/packages and install if missing",
                                "severity": severity
                            })
            
            elif area_name == "performance":
                # Generate performance improvements
                improvement_suggestions.append({
                    "type": "performance",
                    "area": "execution_optimization",
                    "description": "Optimize script execution time",
                    "implementation": "Use parallel execution where possible and remove unnecessary operations",
                    "severity": severity
                })
                
            elif area_name == "robustness":
                # Generate robustness improvements
                improvement_suggestions.append({
                    "type": "robustness",
                    "area": "error_handling",
                    "description": "Improve error handling and reporting",
                    "implementation": "Add more comprehensive error handling and better error messages",
                    "severity": severity
                })
                
        # If no specific improvements could be generated, add a general one
        if not improvement_suggestions:
            improvement_suggestions.append({
                "type": "general",
                "area": "maintainability",
                "description": "Improve script structure and readability",
                "implementation": "Add better comments, variable naming, and modularize code",
                "severity": "low"
            })
            
        return improvement_suggestions
    
    @handle_safely_async
    async def learn_from_execution(self, execution_data: Dict[str, Any]) -> bool:
        """
        Learn from execution data to improve future performance.
        
        Args:
            execution_data: Data from a completed execution
            
        Returns:
            True if learning was successful
        """
        logger.info(f"Learning from execution data")
        
        # Extract key information
        integration_type = execution_data.get("integration_type", "unknown")
        target_name = execution_data.get("target_name", "unknown")
        action = execution_data.get("action", "unknown")
        success = execution_data.get("success", False)
        error = execution_data.get("error")
        output = execution_data.get("output", {})
        
        # Create integration key
        integration_key = f"{integration_type}_{target_name}_{action}"
        
        # Initialize learning data for this integration if needed
        if integration_key not in self.learning_data:
            self.learning_data[integration_key] = {
                "failures": [],
                "successes": 0,
                "improvements": [],
                "execution_times": []
            }
        
        # Record execution time if available
        if "metrics" in execution_data and "duration" in execution_data["metrics"]:
            self.learning_data[integration_key]["execution_times"].append(
                execution_data["metrics"]["duration"]
            )
        
        # Update learning data based on success or failure
        if success:
            self.learning_data[integration_key]["successes"] += 1
        else:
            # Record failure with root cause analysis
            root_cause = "unknown_error"
            if error:
                state = None
                try:
                    # Create a WorkflowState if possible for root cause analysis
                    state_dict = {
                        "error": error,
                        "output": output,
                        "integration_type": integration_type,
                        "target_name": target_name,
                        "action": action
                    }
                    state = WorkflowState(**state_dict)
                    root_cause = await self._identify_root_cause(state, error)
                except Exception as e:
                    logger.error(f"Error creating state for root cause analysis: {e}")
                    
            # Record the failure
            self.learning_data[integration_key]["failures"].append({
                "error": error,
                "root_cause": root_cause,
                "timestamp": execution_data.get("timestamp"),
                "system_context": execution_data.get("system_context", {})
            })
            
            # Attempt to generate an improvement if state was created
            if state and root_cause != "unknown_error":
                try:
                    improvement = await self._generate_improvement(state, root_cause)
                    if improvement:
                        self.learning_data[integration_key]["improvements"].append({
                            "root_cause": root_cause,
                            "improvement": improvement,
                            "timestamp": execution_data.get("timestamp")
                        })
                        await self._apply_improvement(state, improvement)
                except Exception as e:
                    logger.error(f"Error generating improvement: {e}")
        
        # Save learning data to disk
        await self._save_learning_data()
        return True
    
    # Helper methods for analysis
    def _calculate_success_rate_change(self, historical_data: Dict[str, Any], current_rate: float) -> Dict[str, Any]:
        """Calculate the change in success rate compared to historical data."""
        total_executions = historical_data.get("successes", 0) + len(historical_data.get("failures", []))
        if total_executions == 0:
            return {"current": current_rate, "historical": 0, "change": 0}
            
        historical_rate = historical_data.get("successes", 0) / total_executions
        change = current_rate - historical_rate
        
        return {
            "current": current_rate,
            "historical": historical_rate,
            "change": change,
            "trend": "improving" if change > 0 else "declining" if change < 0 else "stable"
        }
        
    def _calculate_avg_execution_time(self, historical_data: Dict[str, Any]) -> float:
        """Calculate the average execution time from historical data."""
        times = historical_data.get("execution_times", [])
        if not times:
            return 0
        return sum(times) / len(times)
        
    def _determine_execution_time_trend(self, historical_data: Dict[str, Any], current_time: float) -> Dict[str, Any]:
        """Determine the trend in execution time."""
        times = historical_data.get("execution_times", [])
        if not times:
            return {"trend": "unknown", "current": current_time, "historical_avg": 0}
            
        avg_time = sum(times) / len(times)
        # Get the average of the last 3 executions if available
        recent_avg = sum(times[-3:]) / len(times[-3:]) if len(times) >= 3 else avg_time
        
        trend = "improving" if current_time < recent_avg else "declining" if current_time > recent_avg * 1.1 else "stable"
        
        return {
            "trend": trend,
            "current": current_time,
            "historical_avg": avg_time,
            "recent_avg": recent_avg
        }
        
    def _identify_common_failures(self, historical_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify common failure patterns from historical data."""
        failures = historical_data.get("failures", [])
        if not failures:
            return []
            
        # Count occurrences of each root cause
        root_causes = {}
        for failure in failures:
            root_cause = failure.get("root_cause", "unknown_error")
            if root_cause not in root_causes:
                root_causes[root_cause] = 0
            root_causes[root_cause] += 1
            
        # Convert to list and sort by frequency
        common_failures = [
            {"root_cause": cause, "count": count, "percentage": count / len(failures) * 100}
            for cause, count in root_causes.items()
        ]
        
        return sorted(common_failures, key=lambda x: x["count"], reverse=True)
    
    async def cleanup(self) -> None:
        """Clean up resources and save learning data."""
        await self._save_learning_data()
        await super().cleanup()
        logger.info("ImprovementAgent cleanup complete")
