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
    """Represents a change made during workflow execution with enhanced tracking."""
    type: str
    target: str
    revertible: bool = True
    revert_command: Optional[str] = None
    backup_file: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    change_id: UUID = Field(default_factory=uuid4)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    verified: bool = False
    rollback_attempted: bool = False
    rollback_success: Optional[bool] = None
    
    class Config:
        frozen = True
        
    def mark_verified(self) -> 'Change':
        """Mark this change as verified."""
        return Change(
            type=self.type,
            target=self.target,
            revertible=self.revertible,
            revert_command=self.revert_command,
            backup_file=self.backup_file,
            timestamp=self.timestamp,
            change_id=self.change_id,
            metadata=self.metadata,
            verified=True,
            rollback_attempted=self.rollback_attempted,
            rollback_success=self.rollback_success
        )
        
    def mark_rollback_attempted(self, success: bool) -> 'Change':
        """Mark this change as having had rollback attempted."""
        return Change(
            type=self.type,
            target=self.target,
            revertible=self.revertible,
            revert_command=self.revert_command,
            backup_file=self.backup_file,
            timestamp=self.timestamp,
            change_id=self.change_id,
            metadata=self.metadata,
            verified=self.verified,
            rollback_attempted=True,
            rollback_success=success
        )

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
    """Status of a workflow execution with enhanced states for recovery."""
    PENDING = "pending"
    RUNNING = "running"
    VALIDATING = "validating"
    GENERATING = "generating"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    PAUSED = "paused"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERTING = "reverting"
    REVERTED = "reverted"
    PARTIALLY_COMPLETED = "partially_completed"
    PARTIALLY_REVERTED = "partially_reverted"
    RETRYING = "retrying"

class WorkflowStage(str, Enum):
    """Stage of a workflow execution for checkpointing and recovery."""
    INITIALIZATION = "initialization"
    VALIDATION = "validation"
    GENERATION = "generation"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    COMPLETION = "completion"
    ROLLBACK = "rollback"
    RECOVERY = "recovery"

class WorkflowState(BaseModel):
    """Represents the immutable state of a workflow execution with enhanced recovery support."""
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
    transaction_id: Optional[str] = Field(default_factory=lambda: f"wf-{str(uuid4())[:8]}")
    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    error: Optional[str] = None
    metrics: ExecutionMetrics = Field(default_factory=ExecutionMetrics)
    output: Optional[OutputData] = None
    status: WorkflowStatus = WorkflowStatus.PENDING
    
    # Enhanced recovery and checkpoint tracking
    current_stage: WorkflowStage = WorkflowStage.INITIALIZATION
    checkpoints: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    backup_files: List[str] = Field(default_factory=list)
    verification_results: Dict[str, Any] = Field(default_factory=dict)
    rollback_script: Optional[str] = None
    recovery_strategy: Optional[str] = None
    
    # State tracking
    state_id: UUID = Field(default_factory=uuid4)
    parent_state_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)

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
        
    def create_checkpoint(self, stage: WorkflowStage) -> 'WorkflowState':
        """Create a checkpoint at the current stage."""
        checkpoints = dict(self.checkpoints)
        checkpoints[stage.value] = {
            "timestamp": datetime.now().isoformat(),
            "changes_count": len(self.changes),
            "status": self.status
        }
        return self.evolve(
            current_stage=stage,
            checkpoints=checkpoints,
            last_updated=datetime.now()
        )
        
    def set_stage(self, stage: WorkflowStage) -> 'WorkflowState':
        """Set the current workflow stage."""
        return self.evolve(
            current_stage=stage,
            last_updated=datetime.now()
        )
        
    def mark_retry(self) -> 'WorkflowState':
        """Increment retry count and mark as retrying."""
        return self.evolve(
            retry_count=self.retry_count + 1,
            status=WorkflowStatus.RETRYING,
            last_updated=datetime.now()
        )
        
    def can_retry(self) -> bool:
        """Check if the workflow can be retried."""
        return self.retry_count < self.max_retries
        
    def add_backup_file(self, backup_path: str) -> 'WorkflowState':
        """Add a backup file to track for cleanup."""
        return self.evolve(
            backup_files=list(self.backup_files) + [backup_path]
        )
        
    def set_verification_result(self, key: str, result: Any) -> 'WorkflowState':
        """Set a verification result."""
        verification_results = dict(self.verification_results)
        verification_results[key] = result
        return self.evolve(verification_results=verification_results)
        
    def set_rollback_script(self, script: str) -> 'WorkflowState':
        """Set the rollback script."""
        return self.evolve(rollback_script=script)
        
    def set_recovery_strategy(self, strategy: str) -> 'WorkflowState':
        """Set the recovery strategy."""
        return self.evolve(recovery_strategy=strategy)
        
    def mark_partially_completed(self) -> 'WorkflowState':
        """Mark the workflow as partially completed."""
        return self.evolve(status=WorkflowStatus.PARTIALLY_COMPLETED)
        
    def mark_partially_reverted(self) -> 'WorkflowState':
        """Mark the workflow as partially reverted."""
        return self.evolve(status=WorkflowStatus.PARTIALLY_REVERTED)
        
    def mark_validating(self) -> 'WorkflowState':
        """Mark the workflow as validating."""
        return self.evolve(status=WorkflowStatus.VALIDATING)
        
    def mark_generating(self) -> 'WorkflowState':
        """Mark the workflow as generating."""
        return self.evolve(status=WorkflowStatus.GENERATING)
        
    def mark_executing(self) -> 'WorkflowState':
        """Mark the workflow as executing."""
        return self.evolve(status=WorkflowStatus.EXECUTING)
        
    def mark_verifying(self) -> 'WorkflowState':
        """Mark the workflow as verifying."""
        return self.evolve(status=WorkflowStatus.VERIFYING)
        
    def mark_paused(self) -> 'WorkflowState':
        """Mark the workflow as paused."""
        return self.evolve(status=WorkflowStatus.PAUSED)
        
    def mark_waiting(self) -> 'WorkflowState':
        """Mark the workflow as waiting."""
        return self.evolve(status=WorkflowStatus.WAITING)
        
    def mark_reverting(self) -> 'WorkflowState':
        """Mark the workflow as reverting."""
        return self.evolve(status=WorkflowStatus.REVERTING)

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
