"""
Core state definitions for workflow execution using Pydantic.
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class Change(BaseModel):
    """Represents a system change made by a workflow action."""
    type: str
    target: str
    details: Optional[str] = None
    revertible: bool = True
    revert_command: Optional[str] = None

class ExecutionMetrics(BaseModel):
    """Metrics collected during script execution."""
    start_time: float = 0
    end_time: Optional[float] = None
    execution_time: Optional[int] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[int] = None

class OutputData(BaseModel):
    """Captured output from script execution."""
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None

class WorkflowState(BaseModel):
    """State model for workflow execution."""
    action: str
    target_name: str
    integration_type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)

    # Optional fields
    optimized: bool = False
    messages: List[str] = Field(default_factory=list)
    integration_category: Optional[str] = None
    template_key: Optional[str] = None
    script: Optional[str] = None
    system_context: Optional[Dict[str, Any]] = None
    changes: List[Change] = Field(default_factory=list)
    legacy_changes: List[str] = Field(default_factory=list)
    metrics: Optional[ExecutionMetrics] = None
    output: Optional[OutputData] = None
    error: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    transaction_id: Optional[str] = None
    execution_id: Optional[int] = None
    isolation_method: Optional[str] = "docker"

    # Data-driven fields
    template_path: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None
    parameter_schema: Optional[Dict[str, Any]] = None
    verification_data: Optional[Dict[str, Any]] = None

    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        """Convert to dictionary, including nested models."""
        result = super().dict(*args, **kwargs)
        if self.output:
            result["output"] = self.output.dict()
        if self.metrics:
            result["metrics"] = self.metrics.dict()
        if self.changes:
            result["changes"] = [c.dict() for c in self.changes]
        return result