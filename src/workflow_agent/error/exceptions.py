"""
Custom exceptions for the workflow agent.
"""
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class ErrorCode(Enum):
    """Error codes for workflow operations."""
    CONFIGURATION_ERROR = "CONFIG_001"
    VALIDATION_ERROR = "VALID_001"
    EXECUTION_ERROR = "EXEC_001"
    DATABASE_ERROR = "DB_001"
    RESOURCE_ERROR = "RES_001"
    SECURITY_ERROR = "SEC_001"
    TIMEOUT_ERROR = "TIME_001"
    ROLLBACK_ERROR = "ROLL_001"
    PLATFORM_ERROR = "PLAT_001"
    STATE_ERROR = "STATE_001"
    INITIALIZATION_ERROR = "INIT_001"
    NETWORK_ERROR = "NET_001"
    TEMPLATE_ERROR = "TMPL_001"
    SCRIPT_ERROR = "SCRPT_001"
    DOCUMENTATION_ERROR = "DOC_001"

@dataclass
class ErrorContext:
    """Context information for errors."""
    timestamp: datetime = datetime.utcnow()
    component: str = ""
    operation: str = ""
    details: Dict[str, Any] = None
    traceback: Optional[str] = None

class WorkflowError(Exception):
    """Base exception for workflow errors."""
    
    def __init__(self, message: str, error_code: str = "WORKFLOW_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format."""
        return {
            "error": self.message,
            "error_code": self.error_code,
            "timestamp": self.context.timestamp.isoformat(),
            "component": self.context.component,
            "operation": self.context.operation,
            "details": self.context.details,
            "traceback": self.context.traceback
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowError':
        """Create error instance from dictionary."""
        context = ErrorContext(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            component=data["component"],
            operation=data["operation"],
            details=data["details"],
            traceback=data["traceback"]
        )
        return cls(
            message=data["error"],
            error_code=data["error_code"],
            details=data["details"]
        )

class ValidationError(WorkflowError):
    """Raised when validation fails."""
    def __init__(self, message: str, context: Optional[ErrorContext] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.VALIDATION_ERROR.value, details)

class ExecutionError(WorkflowError):
    """Raised when script execution fails."""
    def __init__(self, message: str, context: Optional[ErrorContext] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.EXECUTION_ERROR.value, details)

class ConfigurationError(WorkflowError):
    """Raised when configuration is invalid."""
    def __init__(self, message: str, context: Optional[ErrorContext] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.CONFIGURATION_ERROR.value, details)

class ResourceError(WorkflowError):
    """Raised when resource management fails."""
    def __init__(self, message: str, context: Optional[ErrorContext] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.RESOURCE_ERROR.value, details)

class SecurityError(WorkflowError):
    """Raised when security checks fail."""
    def __init__(self, message: str, context: Optional[ErrorContext] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.SECURITY_ERROR.value, details)

class TimeoutError(WorkflowError):
    """Raised when operations timeout."""
    def __init__(self, message: str, context: Optional[ErrorContext] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.TIMEOUT_ERROR.value, details)

class RollbackError(WorkflowError):
    """Raised when rollback operations fail."""
    def __init__(self, message: str, context: Optional[ErrorContext] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.ROLLBACK_ERROR.value, details)

class PlatformError(WorkflowError):
    """Raised when platform-specific operations fail."""
    def __init__(self, message: str, context: Optional[ErrorContext] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.PLATFORM_ERROR.value, details)

class StateError(WorkflowError):
    """Raised when state operations fail."""
    def __init__(self, message: str, context: Optional[ErrorContext] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.STATE_ERROR.value, details)

class DatabaseError(WorkflowError):
    """Raised when database operations fail."""
    def __init__(self, message: str, context: Optional[ErrorContext] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.DATABASE_ERROR.value, details)

class TemplateError(WorkflowError):
    """Raised when template operations fail."""
    def __init__(self, message: str, context: Optional[ErrorContext] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.TEMPLATE_ERROR.value, details)

class ScriptError(WorkflowError):
    """Raised when script generation or validation fails."""
    def __init__(self, message: str, context: Optional[ErrorContext] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.SCRIPT_ERROR.value, details)

class DocumentationFetchError(WorkflowError):
    """Raised when documentation fetching or parsing operations fail."""
    def __init__(self, message: str, context: Optional[ErrorContext] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.DOCUMENTATION_ERROR.value, details)

class InitializationError(WorkflowError):
    """Exception raised when initialization fails."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code=ErrorCode.INITIALIZATION_ERROR.value, details=details)