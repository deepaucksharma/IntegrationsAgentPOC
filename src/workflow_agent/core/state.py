from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

class ParameterSpec(BaseModel):
    type: str
    description: Optional[str] = None
    required: bool = False
    default: Optional[Any] = None
    
    class Config:
        """Configuration for the model."""
        extra = "allow"  # Allow extra fields for extensibility

class ParameterSchema(BaseModel):
    __root__: Dict[str, ParameterSpec]

class ExecutionMetrics(BaseModel):
    """Metrics collected during script execution."""
    start_time: float = 0
    end_time: Optional[float] = None
    execution_time: Optional[int] = None  # in milliseconds
    cpu_usage: Optional[float] = None  # percentage
    memory_usage: Optional[int] = None  # in bytes
    io_read: Optional[int] = None  # in bytes
    io_write: Optional[int] = None  # in bytes
    network_tx: Optional[int] = None  # in bytes
    network_rx: Optional[int] = None  # in bytes

class OutputData(BaseModel):
    """Captured output from script execution."""
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    
    class Config:
        """Configuration for the model."""
        arbitrary_types_allowed = True

class Change(BaseModel):
    """Represents a system change made by a workflow action."""
    type: str  # install, remove, modify, configure
    target: str  # What was changed
    details: Optional[str] = None  # Additional details
    revertible: bool = True  # Whether this change can be reverted
    revert_command: Optional[str] = None  # Command to revert this specific change

class WorkflowState(BaseModel):
    # Required fields from input
    action: str
    target_name: str
    integration_type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    optimized: bool = False
    messages: List[str] = Field(default_factory=list)

    # Optional fields that nodes may update
    parameter_schema: Optional[Dict[str, ParameterSpec]] = None
    template_key: Optional[str] = None
    script: Optional[str] = None
    script_source: Optional[str] = None  # e.g. template, optimization, custom
    system_context: Optional[Dict[str, Any]] = None
    history: Optional[List[Any]] = None
    changes: List[Change] = Field(default_factory=list)
    legacy_changes: List[str] = Field(default_factory=list)  # For backward compatibility
    metrics: Optional[ExecutionMetrics] = None
    output: Optional[OutputData] = None
    error: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    verification_output: Optional[Dict[str, Any]] = None
    transaction_id: Optional[str] = None  # For tracking atomic operations
    execution_id: Optional[int] = None  # Reference to history record
    custom_verification: Optional[str] = None  # Custom verification command
    isolation_method: Optional[str] = "docker"  # Isolation method to use
    plugin_data: Dict[str, Any] = Field(default_factory=dict)  # Data from plugins

    class Config:
        """Configuration for the model."""
        arbitrary_types_allowed = True
        extra = "allow"  # Allow extra fields for future extensions