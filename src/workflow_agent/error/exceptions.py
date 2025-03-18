"""Custom exceptions for the workflow agent."""

class WorkflowError(Exception):
    """Base exception for all workflow-related errors."""
    pass

class ValidationError(WorkflowError):
    """Raised when validation fails."""
    pass

class ExecutionError(WorkflowError):
    """Raised when execution fails."""
    pass

class DatabaseError(WorkflowError):
    """Raised when database operations fail."""
    pass

class ConfigurationError(WorkflowError):
    """Raised when configuration is invalid."""
    pass

class ResourceError(WorkflowError):
    """Raised when resource operations fail."""
    pass

class SecurityError(WorkflowError):
    """Raised when security checks fail."""
    pass

class TimeoutError(WorkflowError):
    """Raised when operations timeout."""
    pass

class RollbackError(WorkflowError):
    """Raised when rollback operations fail."""
    pass