"""
Centralized error handling utilities for consistent error handling across the application.
"""
import logging
import traceback
import inspect
import sys
from typing import Callable, Any, Dict, List, Optional, Type, TypeVar, Union
from functools import wraps

from ..error.exceptions import WorkflowError, ErrorContext, ExecutionError
from ..core.state import WorkflowState

logger = logging.getLogger(__name__)

T = TypeVar('T')
ReturnType = TypeVar('ReturnType')
AsyncReturnType = TypeVar('AsyncReturnType')

class ErrorHandler:
    """Centralized error handling with standardized patterns."""
    
    @staticmethod
    def handle_safely(func: Callable[..., ReturnType], *args, **kwargs) -> Optional[ReturnType]:
        """
        Execute function safely, catching and logging exceptions.
        
        Args:
            func: Function to execute safely
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result or None if error
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            caller_frame = inspect.currentframe().f_back
            caller_info = ""
            if caller_frame:
                caller_info = f" (called from {caller_frame.f_code.co_name} in {caller_frame.f_code.co_filename}:{caller_frame.f_lineno})"
            
            logger.error(f"Error in {func.__name__}{caller_info}: {e}")
            
            # Additional debug info for detailed logging
            exc_type, exc_obj, exc_tb = sys.exc_info()
            stack_trace = traceback.format_exc()
            logger.debug(f"Exception type: {exc_type.__name__}")
            logger.debug(f"Stack trace: {stack_trace}")
            
            return None
    
    @staticmethod
    async def handle_async_safely(func: Callable[..., AsyncReturnType], *args, **kwargs) -> Optional[AsyncReturnType]:
        """
        Execute async function safely, catching and logging exceptions.
        
        Args:
            func: Async function to execute safely
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Awaitable function result or None if error
        """
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            caller_frame = inspect.currentframe().f_back
            caller_info = ""
            if caller_frame:
                caller_info = f" (called from {caller_frame.f_code.co_name} in {caller_frame.f_code.co_filename}:{caller_frame.f_lineno})"
            
            logger.error(f"Error in async {func.__name__}{caller_info}: {e}")
            
            # Additional debug info for detailed logging
            exc_type, exc_obj, exc_tb = sys.exc_info()
            stack_trace = traceback.format_exc()
            logger.debug(f"Exception type: {exc_type.__name__}")
            logger.debug(f"Stack trace: {stack_trace}")
            
            return None
    
    @staticmethod
    def classify_error(error: Exception) -> str:
        """
        Classify error into categories.
        
        Args:
            error: Exception to classify
            
        Returns:
            Error classification (retriable, auth, validation, system)
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        # Network and timeout errors are typically retriable
        if any(name in error_type for name in ["Timeout", "Connection", "Network", "IO"]):
            return "retriable"
            
        # Authentication and permission errors
        if any(name in error_type for name in ["Auth", "Permission", "Credential", "Access"]):
            return "auth"
            
        # Validation errors
        if any(name in error_type for name in ["Validation", "Format", "Value", "Type", "Argument"]):
            return "validation"
            
        # Check common patterns in error messages
        if any(pattern in error_msg for pattern in 
               ["timeout", "connection refused", "try again", "too many requests", 
                "service unavailable", "temporarily unavailable"]):
            return "retriable"
            
        if any(pattern in error_msg for pattern in 
               ["permission", "not authorized", "forbidden", "auth", "token", "credential"]):
            return "auth"
            
        if any(pattern in error_msg for pattern in 
               ["invalid", "not valid", "validation", "expected", "must be"]):
            return "validation"
            
        # Default to system error
        return "system"
    
    @staticmethod
    def is_retriable(error: Exception) -> bool:
        """
        Determine if an error should be retried.
        
        Args:
            error: Exception to check
            
        Returns:
            True if error is retriable, False otherwise
        """
        return ErrorHandler.classify_error(error) == "retriable"
    
    @staticmethod
    def to_workflow_error(error: Exception, component: str = None, operation: str = None) -> WorkflowError:
        """
        Convert generic exception to WorkflowError.
        
        Args:
            error: Exception to convert
            component: Component where error occurred
            operation: Operation where error occurred
            
        Returns:
            WorkflowError with context
        """
        if isinstance(error, WorkflowError):
            if component or operation:
                # Update context if provided
                context = error.context or ErrorContext()
                if component:
                    context.component = component
                if operation:
                    context.operation = operation
                
                # Create new error with updated context
                return type(error)(str(error), context, error.details)
            return error
        
        # Create new WorkflowError
        context = ErrorContext(component=component, operation=operation)
        
        # Create specific error type based on classification
        error_class = classification_to_error_type(error)
        return error_class(str(error), context)
    
    @staticmethod
    def update_state_with_error(state: WorkflowState, error: Exception, component: str = None, operation: str = None) -> WorkflowState:
        """
        Update state with error information.
        
        Args:
            state: Current workflow state
            error: Exception that occurred
            component: Component where error occurred
            operation: Operation where error occurred
            
        Returns:
            Updated workflow state with error
        """
        # Convert to WorkflowError for consistent formatting
        workflow_error = ErrorHandler.to_workflow_error(error, component, operation)
        
        # Create error message
        if workflow_error.context.component and workflow_error.context.operation:
            error_msg = f"{workflow_error.context.component}.{workflow_error.context.operation}: {str(workflow_error)}"
        else:
            error_msg = str(workflow_error)
        
        # Set error in state
        return state.set_error(error_msg)

def safe_operation(error_msg: str = "Operation failed", component: str = None):
    """
    Decorator for functions to standardize error handling.
    
    Args:
        error_msg: Base error message
        component: Component name for error context
        
    Returns:
        Decorated function with error handling
    """
    def decorator(func: Callable[..., ReturnType]) -> Callable[..., ReturnType]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> ReturnType:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                operation = func.__name__
                logger.error(f"{error_msg}: {e}", exc_info=True)
                
                # Convert to WorkflowError
                workflow_error = ErrorHandler.to_workflow_error(e, component, operation)
                
                # Re-raise as WorkflowError
                raise workflow_error
        return wrapper
    return decorator

def async_safe_operation(error_msg: str = "Operation failed", component: str = None):
    """
    Decorator for async functions to standardize error handling.
    
    Args:
        error_msg: Base error message
        component: Component name for error context
        
    Returns:
        Decorated async function with error handling
    """
    def decorator(func: Callable[..., AsyncReturnType]) -> Callable[..., AsyncReturnType]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> AsyncReturnType:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                operation = func.__name__
                logger.error(f"{error_msg}: {e}", exc_info=True)
                
                # Convert to WorkflowError
                workflow_error = ErrorHandler.to_workflow_error(e, component, operation)
                
                # Re-raise as WorkflowError
                raise workflow_error
        return wrapper
    return decorator

def state_safe_operation(error_msg: str = "Operation failed", component: str = None):
    """
    Decorator for state-returning functions to standardize error handling.
    Catches exceptions and converts them to state with errors.
    
    Args:
        error_msg: Base error message
        component: Component name for error context
        
    Returns:
        Decorated function with consistent error handling
    """
    def decorator(func: Callable[..., WorkflowState]) -> Callable[..., WorkflowState]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> WorkflowState:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                operation = func.__name__
                full_error = f"{error_msg}: {str(e)}"
                logger.error(full_error, exc_info=True)
                
                # Extract state from first argument if it's a WorkflowState
                state = args[0] if args and isinstance(args[0], WorkflowState) else None
                
                if state:
                    return ErrorHandler.update_state_with_error(state, e, component, operation)
                
                # If no state argument, re-raise the exception
                raise ErrorHandler.to_workflow_error(e, component, operation)
                
        return wrapper
    return decorator

def async_state_safe_operation(error_msg: str = "Operation failed", component: str = None):
    """
    Decorator for async state-returning functions to standardize error handling.
    
    Args:
        error_msg: Base error message
        component: Component name for error context
        
    Returns:
        Decorated async function with consistent error handling
    """
    def decorator(func: Callable[..., AsyncReturnType]) -> Callable[..., AsyncReturnType]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> AsyncReturnType:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                operation = func.__name__
                full_error = f"{error_msg}: {str(e)}"
                logger.error(full_error, exc_info=True)
                
                # Extract state from first argument if it's a WorkflowState
                state = args[0] if args and isinstance(args[0], WorkflowState) else None
                
                if state:
                    return ErrorHandler.update_state_with_error(state, e, component, operation)
                
                # If no state argument, re-raise the exception
                raise ErrorHandler.to_workflow_error(e, component, operation)
                
        return wrapper
    return decorator

def classification_to_error_type(error: Exception) -> Type[WorkflowError]:
    """
    Map error classification to specific WorkflowError type.
    
    Args:
        error: Exception to map
        
    Returns:
        WorkflowError subclass
    """
    from ..error.exceptions import (
        ExecutionError, ValidationError, ConfigurationError,
        StateError, TemplateError, SecurityError, IntegrationError
    )
    
    error_type = type(error).__name__
    error_class = WorkflowError  # Default
    
    if "Execution" in error_type or "Process" in error_type or "Script" in error_type:
        error_class = ExecutionError
    elif "Validation" in error_type or "Format" in error_type or "Value" in error_type:
        error_class = ValidationError
    elif "Config" in error_type or "Setting" in error_type:
        error_class = ConfigurationError
    elif "State" in error_type:
        error_class = StateError
    elif "Template" in error_type or "Render" in error_type:
        error_class = TemplateError
    elif "Security" in error_type or "Permission" in error_type or "Auth" in error_type:
        error_class = SecurityError
    elif "Integration" in error_type:
        error_class = IntegrationError
    
    return error_class
