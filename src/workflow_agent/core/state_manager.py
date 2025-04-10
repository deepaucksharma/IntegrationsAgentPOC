"""
State management system with event-based observer pattern.
"""
import logging
import asyncio
from typing import Dict, Any, Optional, List, Set, Protocol, runtime_checkable, Callable
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
from pydantic import BaseModel

from .state import WorkflowState, WorkflowStatus, WorkflowStage
from ..error.exceptions import StateError
from ..error.handler import ErrorHandler, handle_safely_async, retry

logger = logging.getLogger(__name__)

class StateEvent(BaseModel):
    """Base event for state changes with metadata."""
    event_type: str
    workflow_id: str
    timestamp: datetime = datetime.now()
    event_id: UUID = uuid4()
    
    class Config:
        frozen = True

class StateCreatedEvent(StateEvent):
    """Event fired when a new workflow state is created."""
    event_type: str = "state_created"
    state: Dict[str, Any]  # Serialized state

class StateTransitionEvent(StateEvent):
    """Event fired when a workflow transitions between states."""
    event_type: str = "state_transition"
    from_status: Optional[WorkflowStatus] = None
    to_status: WorkflowStatus
    from_stage: Optional[WorkflowStage] = None
    to_stage: Optional[WorkflowStage] = None

class ErrorEvent(StateEvent):
    """Event fired when an error occurs in the workflow."""
    event_type: str = "error"
    error_message: str
    error_type: str
    error_context: Dict[str, Any] = {}

class CompletionEvent(StateEvent):
    """Event fired when a workflow completes."""
    event_type: str = "completion"
    success: bool
    duration: float  # in seconds
    summary: Dict[str, Any] = {}

@runtime_checkable
class StateObserver(Protocol):
    """Protocol for state observers that can react to state events."""
    
    async def on_event(self, event: StateEvent) -> None:
        """
        Called when a state event occurs.
        
        Args:
            event: The state event
        """
        ...

class StateStorage(ABC):
    """Abstract interface for state storage."""
    
    @abstractmethod
    async def save_state(self, state: WorkflowState) -> bool:
        """
        Save a workflow state.
        
        Args:
            state: The state to save
            
        Returns:
            True if saved successfully
        """
        pass
    
    @abstractmethod
    async def load_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """
        Load a workflow state.
        
        Args:
            workflow_id: The workflow ID
            
        Returns:
            The workflow state, or None if not found
        """
        pass
    
    @abstractmethod
    async def list_workflows(self, status: Optional[WorkflowStatus] = None) -> List[str]:
        """
        List workflow IDs.
        
        Args:
            status: Optional status filter
            
        Returns:
            List of workflow IDs
        """
        pass
    
    @abstractmethod
    async def save_event(self, event: StateEvent) -> bool:
        """
        Save a state event.
        
        Args:
            event: The event to save
            
        Returns:
            True if saved successfully
        """
        pass
    
    @abstractmethod
    async def get_events(self, workflow_id: str) -> List[StateEvent]:
        """
        Get all events for a workflow.
        
        Args:
            workflow_id: The workflow ID
            
        Returns:
            List of events
        """
        pass

class InMemoryStateStorage(StateStorage):
    """In-memory implementation of state storage."""
    
    def __init__(self):
        """Initialize the storage."""
        self.states: Dict[str, WorkflowState] = {}
        self.events: Dict[str, List[StateEvent]] = {}
    
    async def save_state(self, state: WorkflowState) -> bool:
        """Save a workflow state."""
        if not state.transaction_id:
            logger.error("Cannot save state without transaction_id")
            return False
            
        self.states[state.transaction_id] = state
        return True
    
    async def load_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """Load a workflow state."""
        return self.states.get(workflow_id)
    
    async def list_workflows(self, status: Optional[WorkflowStatus] = None) -> List[str]:
        """List workflow IDs."""
        if status:
            return [wf_id for wf_id, state in self.states.items() if state.status == status]
        return list(self.states.keys())
    
    async def save_event(self, event: StateEvent) -> bool:
        """Save a state event."""
        if event.workflow_id not in self.events:
            self.events[event.workflow_id] = []
            
        self.events[event.workflow_id].append(event)
        return True
    
    async def get_events(self, workflow_id: str) -> List[StateEvent]:
        """Get all events for a workflow."""
        return self.events.get(workflow_id, [])

class StateManager:
    """
    Manages workflow state with immutability, event sourcing, and observer pattern.
    Handles state transitions, notifications, and persistence.
    """
    
    def __init__(self, storage: Optional[StateStorage] = None):
        """
        Initialize the state manager.
        
        Args:
            storage: Optional storage implementation
        """
        self.storage = storage or InMemoryStateStorage()
        self.observers: Dict[str, Set[StateObserver]] = {
            "state_created": set(),
            "state_transition": set(),
            "error": set(),
            "completion": set(),
            "all": set()  # Observers that receive all events
        }
        self.active_states: Dict[str, WorkflowState] = {}
        self._lock = asyncio.Lock()
    
    def register_observer(self, observer: StateObserver, event_types: Optional[List[str]] = None) -> None:
        """
        Register an observer for specific event types.
        
        Args:
            observer: The observer to register
            event_types: Optional list of event types to observe
                         If None, observes all events
        """
        if event_types is None:
            self.observers["all"].add(observer)
            logger.debug(f"Registered observer {observer.__class__.__name__} for all events")
        else:
            for event_type in event_types:
                if event_type not in self.observers:
                    self.observers[event_type] = set()
                self.observers[event_type].add(observer)
                logger.debug(f"Registered observer {observer.__class__.__name__} for {event_type} events")
    
    def unregister_observer(self, observer: StateObserver) -> None:
        """
        Unregister an observer from all event types.
        
        Args:
            observer: The observer to unregister
        """
        for observers in self.observers.values():
            if observer in observers:
                observers.remove(observer)
                
        logger.debug(f"Unregistered observer {observer.__class__.__name__}")
    
    @handle_safely_async
    async def notify_observers(self, event: StateEvent) -> None:
        """
        Notify observers of an event.
        
        Args:
            event: The event to notify about
        """
        observers_to_notify = set()
        
        # Add observers for this event type
        if event.event_type in self.observers:
            observers_to_notify.update(self.observers[event.event_type])
            
        # Add observers for all events
        observers_to_notify.update(self.observers["all"])
        
        # Notify observers
        notification_tasks = []
        for observer in observers_to_notify:
            notification_tasks.append(self._notify_observer(observer, event))
            
        if notification_tasks:
            await asyncio.gather(*notification_tasks, return_exceptions=True)
            
        # Save event to storage
        await self.storage.save_event(event)
    
    @handle_safely_async
    async def _notify_observer(self, observer: StateObserver, event: StateEvent) -> None:
        """Notify a single observer of an event."""
        try:
            await observer.on_event(event)
        except Exception as e:
            logger.error(f"Error notifying observer {observer.__class__.__name__}: {e}")
    
    @retry(max_retries=3)
    async def create_workflow(self, state: WorkflowState) -> str:
        """
        Create a new workflow state.
        
        Args:
            state: Initial workflow state
            
        Returns:
            Workflow ID
            
        Raises:
            StateError: If state creation fails
        """
        workflow_id = state.transaction_id
        if not workflow_id:
            raise StateError("Cannot create workflow without transaction_id")
            
        async with self._lock:
            # Check if workflow already exists
            if workflow_id in self.active_states:
                raise StateError(f"Workflow {workflow_id} already exists")
                
            # Store state
            self.active_states[workflow_id] = state
            
            # Save to storage
            save_success = await self.storage.save_state(state)
            
            if not save_success:
                raise StateError(f"Failed to save state for workflow {workflow_id}")
                
        # Create event
        event = StateCreatedEvent(
            workflow_id=workflow_id,
            state=state.model_dump()
        )
        
        # Notify observers
        await self.notify_observers(event)
        
        logger.info(f"Created workflow {workflow_id}")
        return workflow_id
    
    @retry(max_retries=3)
    async def update_state(self, workflow_id: str, new_state: WorkflowState) -> WorkflowState:
        """
        Update a workflow state.
        
        Args:
            workflow_id: Workflow ID
            new_state: New workflow state
            
        Returns:
            Updated workflow state
            
        Raises:
            StateError: If state update fails
        """
        if not workflow_id:
            raise StateError("Cannot update workflow without ID")
            
        old_state = None
        
        async with self._lock:
            # Get current state
            old_state = self.active_states.get(workflow_id)
            
            if not old_state:
                # Try loading from storage
                old_state = await self.storage.load_state(workflow_id)
                
                if not old_state:
                    raise StateError(f"Workflow {workflow_id} not found")
                    
                # Cache in active states
                self.active_states[workflow_id] = old_state
            
            # Store new state
            self.active_states[workflow_id] = new_state
            
            # Save to storage
            save_success = await self.storage.save_state(new_state)
            
            if not save_success:
                raise StateError(f"Failed to save state for workflow {workflow_id}")
                
        # Create transition event if status changed
        if old_state.status != new_state.status or old_state.current_stage != new_state.current_stage:
            event = StateTransitionEvent(
                workflow_id=workflow_id,
                from_status=old_state.status,
                to_status=new_state.status,
                from_stage=old_state.current_stage,
                to_stage=new_state.current_stage
            )
            
            # Notify observers
            await self.notify_observers(event)
            
        # Create error event if error was added
        if not old_state.error and new_state.error:
            event = ErrorEvent(
                workflow_id=workflow_id,
                error_message=new_state.error,
                error_type="workflow_error"
            )
            
            # Notify observers
            await self.notify_observers(event)
            
        # Create completion event if workflow completed or failed
        if old_state.status not in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED] and \
           new_state.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
            
            # Calculate duration
            start_time = new_state.metrics.start_time
            end_time = new_state.metrics.end_time or datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            event = CompletionEvent(
                workflow_id=workflow_id,
                success=new_state.status == WorkflowStatus.COMPLETED,
                duration=duration,
                summary={
                    "status": new_state.status,
                    "changes": len(new_state.changes),
                    "error": new_state.error
                }
            )
            
            # Notify observers
            await self.notify_observers(event)
            
        logger.info(f"Updated workflow {workflow_id} state: {old_state.status} -> {new_state.status}")
        return new_state
    
    async def get_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """
        Get current workflow state.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Current workflow state or None if not found
        """
        async with self._lock:
            # Check in-memory cache first
            if workflow_id in self.active_states:
                return self.active_states[workflow_id]
                
            # Try loading from storage
            state = await self.storage.load_state(workflow_id)
            
            if state:
                # Cache for future use
                self.active_states[workflow_id] = state
                
            return state
    
    async def apply_change(
        self, 
        workflow_id: str, 
        change_func: Callable[[WorkflowState], WorkflowState]
    ) -> WorkflowState:
        """
        Apply a change function to workflow state.
        
        Args:
            workflow_id: Workflow ID
            change_func: Function that takes a state and returns a new state
            
        Returns:
            Updated workflow state
            
        Raises:
            StateError: If state change fails
        """
        async with self._lock:
            # Get current state
            state = await self.get_state(workflow_id)
            
            if not state:
                raise StateError(f"Workflow {workflow_id} not found")
                
            # Apply change
            new_state = change_func(state)
            
            # Update state
            return await self.update_state(workflow_id, new_state)
    
    async def list_active_workflows(self) -> List[str]:
        """
        List active workflow IDs.
        
        Returns:
            List of active workflow IDs
        """
        active_statuses = [
            WorkflowStatus.PENDING,
            WorkflowStatus.RUNNING,
            WorkflowStatus.VALIDATING,
            WorkflowStatus.GENERATING,
            WorkflowStatus.EXECUTING,
            WorkflowStatus.VERIFYING,
            WorkflowStatus.PAUSED,
            WorkflowStatus.WAITING,
            WorkflowStatus.RETRYING
        ]
        
        active_workflows = set()
        
        # Add known active workflows from memory
        for workflow_id, state in self.active_states.items():
            if state.status in active_statuses:
                active_workflows.add(workflow_id)
                
        # Check storage for each status
        for status in active_statuses:
            workflows = await self.storage.list_workflows(status)
            active_workflows.update(workflows)
            
        return list(active_workflows)
    
    async def get_workflow_events(self, workflow_id: str) -> List[StateEvent]:
        """
        Get all events for a workflow.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            List of events in chronological order
        """
        return await self.storage.get_events(workflow_id)
    
    async def clear_inactive_workflows(self, max_age_hours: int = 24) -> int:
        """
        Clear inactive workflows from memory cache.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of workflows cleared
        """
        inactive_statuses = [
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.REVERTED
        ]
        
        workflows_to_clear = []
        now = datetime.now()
        
        async with self._lock:
            for workflow_id, state in self.active_states.items():
                if state.status in inactive_statuses:
                    # Calculate age
                    age = now - state.last_updated
                    
                    if age.total_seconds() > max_age_hours * 3600:
                        workflows_to_clear.append(workflow_id)
                        
            # Clear workflows
            for workflow_id in workflows_to_clear:
                self.active_states.pop(workflow_id, None)
                
        logger.info(f"Cleared {len(workflows_to_clear)} inactive workflows from memory")
        return len(workflows_to_clear)
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        # Clear observers
        self.observers.clear()
        
        # Clear active states
        self.active_states.clear()
