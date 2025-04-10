"""
Centralized error handling framework for the workflow agent.
"""
import logging
import traceback
import sys
import functools
from typing import Callable, Any, Dict, List, Optional, Tuple, Type, TypeVar, Union, cast
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

# Type variable for function return types
T = TypeVar('T')

class ErrorCategory(str, Enum):
    """Error categories for classification."""
    SYSTEM = "system"
    INPUT = "input"
    CONFIGURATION = "configuration"
    EXECUTION = "execution"
    NETWORK = "network"
    PERMISSIONS = "permissions"
    RESOURCE = "resource"
    TIMEOUT = "timeout"
    SERVICE = "service"
    VALIDATION = "validation"
    UNKNOWN = "unknown"

class ErrorSeverity(str, Enum):
    """Error severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class ErrorClassification:
    """Classification data for errors."""
    
    def __init__(
        self,
        category: ErrorCategory,
        severity: ErrorSeverity,
        retryable: bool = False,
        user_facing: bool = True,
        expected: bool = True
    ):
        self.category = category
        self.severity = severity
        self.retryable = retryable
        self.user_facing = user_facing
        self.expected = expected

class ErrorHandler:
    """Centralized error handling with standardized patterns."""
    
    # Registry of error classifications
    _error_registry: Dict[Type[Exception], ErrorClassification] = {}
    
    @classmethod
    def register_error(
        cls,
        exception_class: Type[Exception],
        category: ErrorCategory,
        severity: ErrorSeverity,
        retryable: bool = False,
        user_facing: bool = True,
        expected: bool = True
    ) -> None:
        """
        Register an error classification.
        
        Args:
            exception_class: Exception class to register
            category: Error category
            severity: Error severity
            retryable: Whether the error is retryable
            user_facing: Whether the error should be shown to users
            expected: Whether the error is expected in normal operation
        """
        cls._error_registry[exception_class] = ErrorClassification(
            category=category,
            severity=severity,
            retryable=retryable,
            user_facing=user_facing,
            expected=expected
        )
        
    @classmethod
    def get_classification(cls, exception: Exception) -> ErrorClassification:
        """
        Get the classification for an exception.
        
        Args:
            exception: Exception to classify
            
        Returns:
            Error classification
        """
        # Look for exact match
        if type(exception) in cls._error_registry:
            return cls._error_registry[type(exception)]
            
        # Look for parent class matches
        for exc_class, classification in cls._error_registry.items():
            if isinstance(exception, exc_class):
                return classification
                
        # Default classification
        return ErrorClassification(
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.MEDIUM,
            retryable=False,
            user_facing=True,
            expected=False
        )
    
    @classmethod
    def is_retryable(cls, exception: Exception) -> bool:
        """
        Check if an error is retryable.
        
        Args:
            exception: Exception to check
            
        Returns:
            True if the error is retryable, False otherwise
        """
        classification = cls.get_classification(exception)
        return classification.retryable
    
    @classmethod
    def is_user_facing(cls, exception: Exception) -> bool:
        """
        Check if an error should be shown to users.
        
        Args:
            exception: Exception to check
            
        Returns:
            True if the error should be shown to users, False otherwise
        """
        classification = cls.get_classification(exception)
        return classification.user_facing
    
    @classmethod
    def is_expected(cls, exception: Exception) -> bool:
        """
        Check if an error is expected in normal operation.
        
        Args:
            exception: Exception to check
            
        Returns:
            True if the error is expected, False otherwise
        """
        classification = cls.get_classification(exception)
        return classification.expected
    
    @staticmethod
    def handle_safely(func: Callable[..., T], *args: Any, **kwargs: Any) -> Union[T, None]:
        """
        Execute function safely, catching and logging exceptions.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result or None if an exception was raised
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            traceback.print_exc()
            return None
    
    @staticmethod
    def wrap(func: Callable[..., T]) -> Callable[..., Union[T, None]]:
        """
        Decorator to wrap a function with safe error handling.
        
        Args:
            func: Function to wrap
            
        Returns:
            Wrapped function
        """
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Union[T, None]:
            return ErrorHandler.handle_safely(func, *args, **kwargs)
        return wrapper
    
    @staticmethod
    def wrap_async(func: Callable[..., Any]) -> Callable[..., Any]:
        """
        Decorator to wrap an async function with safe error handling.
        
        Args:
            func: Async function to wrap
            
        Returns:
            Wrapped async function
        """
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in async {func.__name__}: {e}")
                traceback.print_exc()
                return None
        return wrapper
    
    @staticmethod
    def format_exception(exception: Exception) -> str:
        """
        Format an exception with traceback for logging.
        
        Args:
            exception: Exception to format
            
        Returns:
            Formatted exception string
        """
        return ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    
    @staticmethod
    def format_error_message(exception: Exception, include_traceback: bool = False) -> str:
        """
        Format an error message for display.
        
        Args:
            exception: Exception to format
            include_traceback: Whether to include traceback
            
        Returns:
            Formatted error message
        """
        if include_traceback:
            return ErrorHandler.format_exception(exception)
        else:
            return f"{type(exception).__name__}: {str(exception)}"
