"""
Standardized error handling utilities for consistent error flows.
"""
import logging
import traceback
from typing import Callable, Dict, Any, Optional, Type, TypeVar, Union
from functools import wraps

from ..core.state import WorkflowState
from ..error.exceptions import WorkflowError

logger = logging.getLogger(__name__)

T = TypeVar('T')
StateFunc = Callable[..., WorkflowState]
AsyncStateFunc = Callable[..., "Awaitable[WorkflowState]"]

def handle_errors(error_msg: str = "Operation failed"):
    """
    Decorator for state-returning functions to standardize error handling.
    Catches exceptions and converts them to state with errors.
    
    Args:
        error_msg: Base error message
        
    Returns:
        Decorated function with consistent error handling
    """
    def decorator(func: StateFunc) -> StateFunc:
        @wraps(func)
        def wrapper(*args, **kwargs) -> WorkflowState:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Extract state from first argument if it's a WorkflowState
                state = args[0] if args and isinstance(args[0], WorkflowState) else None
                
                full_error = f"{error_msg}: {str(e)}"
                logger.error(full_error, exc_info=True)
                
                if state:
                    return state.set_error(full_error)
                
                # If no state argument, re-raise the exception
                raise
                
        return wrapper
    return decorator

async def handle_async_errors(func, error_msg, *args, **kwargs) -> WorkflowState:
    """
    Helper function for async functions that return WorkflowState.
    
    Args:
        func: Async function to execute
        error_msg: Error message to use if function fails
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        WorkflowState from function or with error
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        # Extract state from first argument if it's a WorkflowState
        state = args[0] if args and isinstance(args[0], WorkflowState) else None
        
        full_error = f"{error_msg}: {str(e)}"
        logger.error(full_error, exc_info=True)
        
        if state:
            return state.set_error(full_error)
        
        # If no state argument, re-raise the exception
        raise

def async_handle_errors(error_msg: str = "Operation failed"):
    """
    Decorator for async state-returning functions to standardize error handling.
    
    Args:
        error_msg: Base error message
        
    Returns:
        Decorated async function with consistent error handling
    """
    def decorator(func: AsyncStateFunc) -> AsyncStateFunc:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> WorkflowState:
            return await handle_async_errors(func, error_msg, *args, **kwargs)
        return wrapper
    return decorator
    
def is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error should be considered retryable.
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is retryable, False otherwise
    """
    # Network and temporary resource errors are retryable
    retryable_error_types = {
        "ConnectionError",
        "TimeoutError", 
        "RequestError",
        "NetworkError",
        "TemporaryResourceError",
        "ResourceExhaustedError"
    }
    
    # Permanent errors should not be retried
    non_retryable_error_types = {
        "ConfigurationError",
        "SecurityError",
        "ValidationError",
        "PermissionError",
        "FileNotFoundError",
        "AuthenticationError",
        "NotFoundError"
    }
    
    error_type = type(error).__name__
    
    # Check explicit categories first
    if error_type in retryable_error_types:
        return True
    
    if error_type in non_retryable_error_types:
        return False
    
    # Check for common patterns in error messages
    retryable_patterns = [
        "timeout",
        "connection refused",
        "network error",
        "temporarily unavailable",
        "resource temporarily unavailable",
        "service unavailable",
        "try again later",
        "too many requests"
    ]
    
    error_msg = str(error).lower()
    return any(pattern in error_msg for pattern in retryable_patterns)
