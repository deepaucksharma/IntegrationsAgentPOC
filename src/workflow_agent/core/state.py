"""Core state definitions for workflow execution."""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

class ParameterSpec:
    """Specification for a parameter."""
    def __init__(
        self,
        type: str = "string",
        description: str = "",
        required: bool = False,
        default: Optional[Any] = None,
        choices: Optional[List[Any]] = None
    ):
        self.type = type
        self.description = description
        self.required = required
        self.default = default
        self.choices = choices or []

class Change:
    """Represents a system change made by a workflow action."""
    def __init__(
        self,
        type: str,
        target: str,
        details: Optional[str] = None,
        revertible: bool = True,
        revert_command: Optional[str] = None
    ):
        self.type = type
        self.target = target
        self.details = details
        self.revertible = revertible
        self.revert_command = revert_command

class ExecutionMetrics:
    """Metrics collected during script execution."""
    def __init__(
        self,
        start_time: float = 0,
        end_time: Optional[float] = None,
        execution_time: Optional[int] = None,
        cpu_usage: Optional[float] = None,
        memory_usage: Optional[int] = None
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.execution_time = execution_time
        self.cpu_usage = cpu_usage
        self.memory_usage = memory_usage

class OutputData:
    """Captured output from script execution."""
    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        exit_code: Optional[int] = None
    ):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code

class WorkflowState:
    """State model for workflow execution."""
    def __init__(
        self,
        action: str,
        target_name: str,
        integration_type: str,
        parameters: Dict[str, Any] = None,
        optimized: bool = False,
        messages: List[str] = None,
        integration_category: Optional[str] = None,
        parameter_schema: Optional[Dict[str, ParameterSpec]] = None,
        template_key: Optional[str] = None,
        script: Optional[str] = None,
        system_context: Optional[Dict[str, Any]] = None,
        changes: List[Change] = None,
        legacy_changes: List[str] = None,
        metrics: Optional[ExecutionMetrics] = None,
        output: Optional[OutputData] = None,
        error: Optional[str] = None,
        warnings: List[str] = None,
        transaction_id: Optional[str] = None,
        execution_id: Optional[int] = None,
        isolation_method: Optional[str] = "docker"
    ):
        self.action = action
        self.target_name = target_name
        self.integration_type = integration_type
        self.parameters = parameters or {}
        self.optimized = optimized
        self.messages = messages or []
        self.integration_category = integration_category
        self.parameter_schema = parameter_schema
        self.template_key = template_key
        self.script = script
        self.system_context = system_context
        self.changes = changes or []
        self.legacy_changes = legacy_changes or []
        self.metrics = metrics
        self.output = output
        self.error = error
        self.warnings = warnings or []
        self.transaction_id = transaction_id
        self.execution_id = execution_id
        self.isolation_method = isolation_method
    
    def dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "action": self.action,
            "target_name": self.target_name,
            "integration_type": self.integration_type,
            "parameters": self.parameters,
            "optimized": self.optimized,
            "messages": self.messages,
            "integration_category": self.integration_category,
            "template_key": self.template_key,
            "script": self.script,
            "error": self.error,
            "warnings": self.warnings,
            "transaction_id": self.transaction_id,
            "execution_id": self.execution_id,
            "isolation_method": self.isolation_method
        }
        if self.system_context:
            result["system_context"] = self.system_context
        if self.changes:
            result["changes"] = [
                {
                    "type": c.type,
                    "target": c.target,
                    "details": c.details,
                    "revertible": c.revertible,
                    "revert_command": c.revert_command
                }
                for c in self.changes
            ]
        if self.legacy_changes:
            result["legacy_changes"] = self.legacy_changes
        if self.metrics:
            result["metrics"] = {
                "start_time": self.metrics.start_time,
                "end_time": self.metrics.end_time,
                "execution_time": self.metrics.execution_time,
                "cpu_usage": self.metrics.cpu_usage,
                "memory_usage": self.metrics.memory_usage
            }
        if self.output:
            result["output"] = {
                "stdout": self.output.stdout,
                "stderr": self.output.stderr,
                "exit_code": self.output.exit_code
            }
        if self.parameter_schema:
            result["parameter_schema"] = {
                name: {
                    "type": spec.type,
                    "description": spec.description,
                    "required": spec.required,
                    "default": spec.default,
                    "choices": spec.choices
                }
                for name, spec in self.parameter_schema.items()
            }
        return result