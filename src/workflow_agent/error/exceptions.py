"""
Centralized exception definitions for workflow agent.
"""

class ErrorContext:
    """Context information for errors."""
    
    def __init__(self, component: str = None, operation: str = None, **kwargs):
        self.component = component
        self.operation = operation
        self.details = kwargs

class WorkflowError(Exception):
    """Base class for all workflow errors."""
    
    def __init__(self, message: str, context: ErrorContext = None, details: dict = None):
        super().__init__(message)
        self.context = context or ErrorContext()
        self.details = details or {}
        
    def __str__(self):
        base_str = super().__str__()
        if self.context.component and self.context.operation:
            return f"{base_str} [in {self.context.component}.{self.context.operation}]"
        return base_str

class PlatformError(WorkflowError):
    """Error related to platform operations."""
    pass

class ResourceError(WorkflowError):
    """Error in resource management."""
    pass

class RegistrationError(WorkflowError):
    """Error in integration registration."""
    pass

class ConfigurationError(WorkflowError):
    """Error in configuration."""
    pass

class ValidationError(WorkflowError):
    """Error in input validation."""
    pass

class InitializationError(WorkflowError):
    """Error during component initialization."""
    pass

class ExecutionError(WorkflowError):
    """Error during script execution."""
    pass

class StateError(WorkflowError):
    """Error in workflow state."""
    pass

class RecoveryError(WorkflowError):
    """Error during recovery operations."""
    pass

class TemplateError(WorkflowError):
    """Error in template handling."""
    pass

class StorageError(WorkflowError):
    """Error in storage operations."""
    pass

class SecurityError(WorkflowError):
    """Error in security validation."""
    pass

class IntegrationError(WorkflowError):
    """Error in integration operations."""
    pass

class IntegrationConfigError(IntegrationError):
    """Configuration error in integration."""
    pass

class IntegrationValidationError(IntegrationError):
    """Validation error in integration."""
    pass

class IntegrationExecutionError(IntegrationError):
    """Execution error in integration."""
    pass

class DocumentationFetchError(WorkflowError):
    """Error fetching documentation."""
    pass

class VerificationError(WorkflowError):
    """Error during verification."""
    pass

class LLMError(WorkflowError):
    """Error in LLM interaction."""
    pass
