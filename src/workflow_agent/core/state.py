"""
Core state definitions for workflow execution using Pydantic.
"""
from pydantic import BaseModel, Field, validator
from typing import Any, Dict, List, Optional, Set
from copy import deepcopy
from datetime import datetime
from uuid import UUID, uuid4

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
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    disk_io: Dict[str, float] = Field(default_factory=dict)

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
    execution_id: Optional[str] = None
    error: Optional[str] = None
    metrics: Optional[ExecutionMetrics] = None
    output: Optional[OutputData] = None
    
    # State tracking
    state_id: UUID = Field(default_factory=uuid4)
    parent_state_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_fields: Set[str] = Field(default_factory=set)

    class Config:
        frozen = True

    def evolve(self, **changes) -> 'WorkflowState':
        """Create a new state with the specified changes."""
        # Create a copy of the current state's data
        data = self.dict(exclude={'modified_fields', 'state_id', 'parent_state_id', 'created_at'})
        
        # Update with new changes
        data.update(changes)
        
        # Track modified fields
        modified = set(changes.keys())
        
        # Create new state
        return WorkflowState(
            **data,
            parent_state_id=self.state_id,
            modified_fields=modified
        )

    def add_change(self, change: Change) -> 'WorkflowState':
        """Add a change to the state."""
        return self.evolve(changes=self.changes + [change])

    def add_warning(self, warning: str) -> 'WorkflowState':
        """Add a warning to the state."""
        return self.evolve(warnings=self.warnings + [warning])

    def add_message(self, message: str) -> 'WorkflowState':
        """Add a message to the state."""
        return self.evolve(messages=self.messages + [message])

    def set_error(self, error: str) -> 'WorkflowState':
        """Set an error in the state."""
        return self.evolve(error=error)

    def set_output(self, output: OutputData) -> 'WorkflowState':
        """Set execution output in the state."""
        return self.evolve(output=output)

    def update_metrics(self, metrics: ExecutionMetrics) -> 'WorkflowState':
        """Update execution metrics in the state."""
        return self.evolve(metrics=metrics)

    def set_script(self, script: str) -> 'WorkflowState':
        """Set the script in the state."""
        return self.evolve(script=script)

    @validator('changes', 'warnings', 'messages', pre=True)
    def ensure_immutable_lists(cls, v):
        """Ensure lists are immutable."""
        return tuple(v)

    @validator('parameters', 'template_data', 'system_context', pre=True)
    def ensure_immutable_dicts(cls, v):
        """Ensure dictionaries are immutable by creating deep copies."""
        return deepcopy(v)

    def get_change_history(self) -> List[Dict[str, Any]]:
        """Get the history of changes made to this state."""
        history = []
        current = self
        while current:
            if current.modified_fields:
                history.append({
                    'state_id': current.state_id,
                    'modified_fields': current.modified_fields,
                    'timestamp': current.created_at
                })
            current = self._get_parent_state(current.parent_state_id)
        return history

    def _get_parent_state(self, parent_id: Optional[UUID]) -> Optional['WorkflowState']:
        """Get parent state - to be implemented by state management system."""
        return None  # Placeholder - actual implementation would retrieve from state store