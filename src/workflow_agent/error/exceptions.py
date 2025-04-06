"""
Exception classes for workflow agent.
"""

class WorkflowError(Exception):
    """Base exception for workflow errors."""
    pass

class ConfigurationError(WorkflowError):
    """Exception for configuration errors."""
    pass

class InitializationError(WorkflowError):
    """Exception for initialization errors."""
    pass

class ExecutionError(WorkflowError):
    """Exception for execution errors."""
    pass

class StateError(WorkflowError):
    """Exception for state errors."""
    pass

class ScriptError(WorkflowError):
    """Exception for script generation or execution errors."""
    pass
