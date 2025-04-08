"""
Error handling utilities for standardized error management.
"""
import logging
import traceback
import functools
from typing import Dict, Any, Optional, Callable, TypeVar, Awaitable, Union, Type, List
import asyncio
import time

from .exceptions import (
    WorkflowError, 
    NetworkError, 
    AuthenticationError, 
    ValidationError,
    TimeoutError,
    ResourceError
)

logger = logging.getLogger(__name__)

# Type variables for function signatures
T = TypeVar('T')
R = TypeVar('R')

class ErrorCategory:
    """Error categories for classification."""
    NETWORK = "network"  # Network and connectivity issues
    AUTH = "auth"        # Authentication and permission issues
    VALIDATION = "validation"  # Input validation issues
    TIMEOUT = "timeout"  # Timeouts and performance issues
    RESOURCE = "resource"  # Resource availability issues
    WORKFLOW = "workflow"  # General workflow issues
    SYSTEM = "system"    # System and unexpected issues
    
class ErrorHandler:
    """Centralized error handling with standardized patterns."""
    
    @staticmethod
    def classify_error(error: Exception) -> str:
        """
        Classify error into categories.
        
        Args:
            error: Exception to classify
            
        Returns:
            Error category string
        """
        if isinstance(error, (NetworkError, ConnectionError, OSError)):
            return ErrorCategory.NETWORK
        elif isinstance(error, (AuthenticationError, PermissionError)):
            return ErrorCategory.AUTH
        elif isinstance(error, (ValidationError, ValueError, TypeError, KeyError)):
            return ErrorCategory.VALIDATION
        elif isinstance(error, (TimeoutError, asyncio.TimeoutError)):
            return ErrorCategory.TIMEOUT
        elif isinstance(error, ResourceError):
            return ErrorCategory.RESOURCE
        elif isinstance(error, WorkflowError):
            return ErrorCategory.WORKFLOW
        else:
            return ErrorCategory.SYSTEM
            
    @staticmethod
    def is_retriable(error: Exception) -> bool:
        """
        Determine if an error is retriable.
        
        Args:
            error: Exception to check
            
        Returns:
            True if error is retriable, False otherwise
        """
        category = ErrorHandler.classify_error(error)
        return category in [
            ErrorCategory.NETWORK, 
            ErrorCategory.TIMEOUT,
            ErrorCategory.RESOURCE
        ]
    
    @staticmethod
    def handle_safely(
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> Union[T, None]:
        """
        Execute function safely, catching and logging exceptions.
        
        Args:
            func: Function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            
        Returns:
            Function result or None on error
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            logger.debug(f"Error details: {traceback.format_exc()}")
            return None
    
    @staticmethod
    async def handle_safely_async(
        func: Callable[..., Awaitable[T]],
        *args,
        **kwargs
    ) -> Union[T, None]:
        """
        Execute async function safely, catching and logging exceptions.
        
        Args:
            func: Async function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            
        Returns:
            Function result or None on error
        """
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            logger.debug(f"Error details: {traceback.format_exc()}")
            return None
    
    @staticmethod
    def with_retry(
        max_retries: int = 3,
        delay: float = 1.0,
        backoff_factor: float = 2.0,
        retriable_exceptions: Optional[List[Type[Exception]]] = None
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """
        Decorator for retrying functions on failure.
        
        Args:
            max_retries: Maximum number of retries
            delay: Initial delay in seconds
            backoff_factor: Factor to increase delay by on each retry
            retriable_exceptions: List of retriable exception types
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> T:
                last_exception = None
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        # Check if exception is retriable
                        is_retriable = (
                            retriable_exceptions and isinstance(e, tuple(retriable_exceptions))
                        ) or (
                            not retriable_exceptions and ErrorHandler.is_retriable(e)
                        )
                        
                        if not is_retriable or attempt >= max_retries:
                            # Not retriable or reached max retries
                            raise
                            
                        # Calculate delay with exponential backoff
                        retry_delay = delay * (backoff_factor ** attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                            f"Retrying in {retry_delay:.2f} seconds..."
                        )
                        
                        # Wait before retry
                        time.sleep(retry_delay)
                
                # This should never happen if we raise on max retries
                # But just in case, we'll re-raise the last exception
                if last_exception:
                    raise last_exception
                return None  # Unreachable but makes type checker happy
            
            return wrapper
        
        return decorator
    
    @staticmethod
    def with_async_retry(
        max_retries: int = 3,
        delay: float = 1.0,
        backoff_factor: float = 2.0,
        retriable_exceptions: Optional[List[Type[Exception]]] = None
    ) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
        """
        Decorator for retrying async functions on failure.
        
        Args:
            max_retries: Maximum number of retries
            delay: Initial delay in seconds
            backoff_factor: Factor to increase delay by on each retry
            retriable_exceptions: List of retriable exception types
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
            @functools.wraps(func)
            async def wrapper(*args, **kwargs) -> T:
                last_exception = None
                for attempt in range(max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        # Check if exception is retriable
                        is_retriable = (
                            retriable_exceptions and isinstance(e, tuple(retriable_exceptions))
                        ) or (
                            not retriable_exceptions and ErrorHandler.is_retriable(e)
                        )
                        
                        if not is_retriable or attempt >= max_retries:
                            # Not retriable or reached max retries
                            raise
                            
                        # Calculate delay with exponential backoff
                        retry_delay = delay * (backoff_factor ** attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                            f"Retrying in {retry_delay:.2f} seconds..."
                        )
                        
                        # Wait before retry
                        await asyncio.sleep(retry_delay)
                
                # This should never happen if we raise on max retries
                # But just in case, we'll re-raise the last exception
                if last_exception:
                    raise last_exception
                return None  # Unreachable but makes type checker happy
            
            return wrapper
        
        return decorator
    
    @staticmethod
    def format_exception(exc: Exception) -> Dict[str, Any]:
        """
        Format exception as a dictionary with standard fields.
        
        Args:
            exc: Exception to format
            
        Returns:
            Dictionary with exception details
        """
        return {
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
            "error_category": ErrorHandler.classify_error(exc),
            "is_retriable": ErrorHandler.is_retriable(exc),
            "traceback": traceback.format_exception(type(exc), exc, exc.__traceback__),
            "timestamp": time.time()
        }
    
    @staticmethod
    def with_timing(logger_name: Optional[str] = None) -> Callable:
        """
        Decorator to log execution time of a function.
        
        Args:
            logger_name: Name of logger to use, defaults to module logger
            
        Returns:
            Decorator function
        """
        def decorator(func):
            log = logging.getLogger(logger_name or logger.name)
            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    elapsed = time.time() - start_time
                    log.debug(f"{func.__name__} completed in {elapsed:.3f} seconds")
                    return result
                except Exception as e:
                    elapsed = time.time() - start_time
                    log.warning(f"{func.__name__} failed after {elapsed:.3f} seconds: {e}")
                    raise
            
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    elapsed = time.time() - start_time
                    log.debug(f"{func.__name__} completed in {elapsed:.3f} seconds")
                    return result
                except Exception as e:
                    elapsed = time.time() - start_time
                    log.warning(f"{func.__name__} failed after {elapsed:.3f} seconds: {e}")
                    raise
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return wrapper
        
        return decorator

# Alias for backward compatibility and convenience
handle_safely = ErrorHandler.handle_safely
handle_safely_async = ErrorHandler.handle_safely_async
retry = ErrorHandler.with_retry
async_retry = ErrorHandler.with_async_retry
