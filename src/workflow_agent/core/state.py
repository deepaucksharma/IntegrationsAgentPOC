"""
Core state definitions for workflow execution using Pydantic.
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class Change(BaseModel):
    """Represents a change made during workflow execution."""
    type: str
    target: str
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
    """Represents the state of a workflow execution."""
    action: str
    target_name: str
    integration_type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    template_data: Dict[str, Any] = Field(default_factory=dict)
    system_context: Dict[str, Any] = Field(default_factory=dict)
    script: Optional[str] = None
    template_key: Optional[str] = None
    isolation_method: Optional[str] = None
    transaction_id: Optional[str] = None
    execution_id: Optional[str] = None
    changes: List[Change] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    legacy_changes: List[Dict[str, Any]] = Field(default_factory=list)

    # Optional fields
    optimized: bool = False
    messages: List[str] = Field(default_factory=list)
    integration_category: Optional[str] = None
    output: Optional[OutputData] = None

    # Data-driven fields
    template_path: Optional[str] = None
    parameter_schema: Optional[Dict[str, Any]] = None
    verification_data: Optional[Dict[str, Any]] = None

    class Config:
        arbitrary_types_allowed = True

    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        """Convert to dictionary, including nested models."""
        result = super().dict(*args, **kwargs)
        if self.output:
            result["output"] = self.output.dict()
        if self.metrics:
            result["metrics"] = self.metrics
        if self.changes:
            result["changes"] = [c.dict() for c in self.changes]
        return result