"""
Core state definitions for workflow execution using Pydantic.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Optional, Set
from copy import deepcopy
from datetime import datetime
from uuid import UUID, uuid4
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class Change(BaseModel):
    """Represents a change made during workflow execution."""
    type: str
    target: str
    revertible: bool = True
    revert_command: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    change_id: UUID = Field(default_factory=uuid4)

    class Config:
        frozen = True

class ExecutionMetrics(BaseModel):
    """Metrics collected during workflow execution."""
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    disk_io: Dict[str, int] = Field(default_factory=dict)

    class Config:
        frozen = True

class OutputData(BaseModel):
    """Represents output from script execution."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        frozen = True
        
class WorkflowStatus(str, Enum):
    """Status of a workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERTED = "reverted"

class WorkflowState(BaseModel):
    """Represents the immutable state of a workflow execution."""
    # Required fields
    action: str
    target_name: str
    integration_type: str
    
    # Optional fields with defaults
    parameters: Dict[str, Any] = Field(default_factory=dict)
    template_data: Dict[str, Any] = Field(default_factory=dict)
    system_context: Dict[str, Any] = Field(default_factory=dict)
    changes: List[Change] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    messages: List[str] = Field(default_factory=list)
    
    # Optional fields
    script: Optional[str] = None
    template_key: Optional[str] = None
    isolation_method: Optional[str] = None
    transaction_id: Optional[str] = None
    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    error: Optional[str] = None
    metrics: ExecutionMetrics = Field(default_factory=ExecutionMetrics)
    output: Optional[OutputData] = None
    status: WorkflowStatus = WorkflowStatus.PENDING
    
    # State tracking
    state_id: UUID = Field(default_factory=uuid4)
    parent_state_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        frozen = True
        
    @property
    def has_error(self) -> bool:
        """Check if the state has an error."""
        return self.error is not None

    def evolve(self, **changes) -> 'WorkflowState':
        """Create a new state with the specified changes."""
        # Create a copy of the current state's data
        data = self.model_dump()
        
        # Remove fields we want to recalculate
        for field in ['state_id', 'parent_state_id', 'created_at']:
            if field in data:
                del data[field]
        
        # Update with new changes
        data.update(changes)
        
        # Create new state with current state as parent
        return WorkflowState(
            **data,
            parent_state_id=self.state_id
        )

    def add_change(self, change: Change) -> 'WorkflowState':
        """Add a change to the state."""
        return self.evolve(changes=list(self.changes) + [change])

    def add_warning(self, warning: str) -> 'WorkflowState':
        """Add a warning to the state."""
        return self.evolve(warnings=list(self.warnings) + [warning])

    def add_message(self, message: str) -> 'WorkflowState':
        """Add a message to the state."""
        return self.evolve(messages=list(self.messages) + [message])

    def set_error(self, error: str) -> 'WorkflowState':
        """Set an error in the state."""
        return self.evolve(error=error, status=WorkflowStatus.FAILED)

    def set_output(self, output: OutputData) -> 'WorkflowState':
        """Set execution output in the state."""
        return self.evolve(output=output)

    def update_metrics(self, metrics: ExecutionMetrics) -> 'WorkflowState':
        """Update execution metrics in the state."""
        return self.evolve(metrics=metrics)

    def set_script(self, script: str) -> 'WorkflowState':
        """Set the script in the state."""
        return self.evolve(script=script)
        
    def mark_running(self) -> 'WorkflowState':
        """Mark the state as running."""
        return self.evolve(status=WorkflowStatus.RUNNING)
        
    def mark_completed(self) -> 'WorkflowState':
        """Mark the state as completed."""
        return self.evolve(status=WorkflowStatus.COMPLETED)
        
    def mark_reverted(self) -> 'WorkflowState':
        """Mark the state as reverted."""
        return self.evolve(status=WorkflowStatus.REVERTED)

    @field_validator('changes', mode='before')
    @classmethod
    def ensure_change_objects(cls, v):
        """Ensure changes are proper Change objects."""
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, dict):
                    result.append(Change(**item))
                else:
                    result.append(item)
            return result
        return v

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return self.model_dump()
