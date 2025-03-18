"""
Custom exceptions for the workflow agent.
"""
class WorkflowError(Exception):
    pass

class ValidationError(WorkflowError):
    pass

class ExecutionError(WorkflowError):
    pass

class DatabaseError(WorkflowError):
    pass

class ConfigurationError(WorkflowError):
    pass

class ResourceError(WorkflowError):
    pass

class SecurityError(WorkflowError):
    pass

class TimeoutError(WorkflowError):
    pass

class RollbackError(WorkflowError):
    pass