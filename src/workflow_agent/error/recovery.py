import logging
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
from dataclasses import dataclass
from datetime import datetime
import traceback
import time
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class RecoveryAction:
    """Definition of a recovery action."""
    name: str
    action: Callable
    max_retries: int
    retry_delay: float
    backoff_factor: float
    exceptions: List[Type[Exception]]
    
@dataclass
class RecoveryContext:
    """Context for error recovery."""
    error: Exception
    attempt: int
    max_retries: int
    retry_delay: float
    backoff_factor: float
    start_time: datetime
    last_error: Optional[Exception] = None
    last_error_time: Optional[datetime] = None
    
class RecoveryManager:
    """Manages error recovery strategies."""
    
    def __init__(self):
        """Initialize the recovery manager."""
        self._recovery_actions: Dict[str, RecoveryAction] = {}
        
    def register_recovery(
        self,
        name: str,
        action: Callable,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_factor: float = 2.0,
        exceptions: Optional[List[Type[Exception]]] = None
    ) -> None:
        """
        Register a recovery action.
        
        Args:
            name: Name of the recovery action
            action: Recovery action function
            max_retries: Maximum number of retries
            retry_delay: Initial delay between retries
            backoff_factor: Factor to increase delay between retries
            exceptions: List of exceptions to handle
        """
        self._recovery_actions[name] = RecoveryAction(
            name=name,
            action=action,
            max_retries=max_retries,
            retry_delay=retry_delay,
            backoff_factor=backoff_factor,
            exceptions=exceptions or [Exception]
        )
        
    def with_recovery(
        self,
        name: str,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        Execute a function with recovery.
        
        Args:
            name: Name of the recovery action to use
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If recovery fails
        """
        if name not in self._recovery_actions:
            raise KeyError(f"Recovery action {name} not registered")
            
        recovery = self._recovery_actions[name]
        context = RecoveryContext(
            error=None,
            attempt=0,
            max_retries=recovery.max_retries,
            retry_delay=recovery.retry_delay,
            backoff_factor=recovery.backoff_factor,
            start_time=datetime.utcnow()
        )
        
        while context.attempt <= recovery.max_retries:
            try:
                return func(*args, **kwargs)
            except tuple(recovery.exceptions) as e:
                context.attempt += 1
                context.last_error = e
                context.last_error_time = datetime.utcnow()
                
                if context.attempt > recovery.max_retries:
                    logger.error(
                        f"Max retries exceeded for {name}: {e}\n"
                        f"Traceback: {traceback.format_exc()}"
                    )
                    raise
                    
                # Calculate delay with exponential backoff
                delay = context.retry_delay * (
                    context.backoff_factor ** (context.attempt - 1)
                )
                
                logger.warning(
                    f"Attempt {context.attempt}/{recovery.max_retries} failed for {name}: {e}\n"
                    f"Retrying in {delay:.2f} seconds..."
                )
                
                # Execute recovery action
                try:
                    recovery.action(context)
                except Exception as recovery_error:
                    logger.error(
                        f"Recovery action failed for {name}: {recovery_error}\n"
                        f"Traceback: {traceback.format_exc()}"
                    )
                    
                time.sleep(delay)
                
    def with_recovery_many(
        self,
        name: str,
        funcs: List[Callable[..., Any]],
        *args,
        **kwargs
    ) -> List[Any]:
        """
        Execute multiple functions with recovery.
        
        Args:
            name: Name of the recovery action to use
            funcs: List of functions to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            List of function results
        """
        results = []
        for func in funcs:
            try:
                result = self.with_recovery(name, func, *args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Function execution failed: {e}")
                results.append(None)
        return results
        
    def clear(self) -> None:
        """Clear all registered recovery actions."""
        self._recovery_actions.clear()
        
# Global recovery manager instance
recovery_manager = RecoveryManager()

def with_recovery(
    name: str,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Optional[List[Type[Exception]]] = None
):
    """
    Decorator to add recovery to a function.
    
    Args:
        name: Name of the recovery action
        max_retries: Maximum number of retries
        retry_delay: Initial delay between retries
        backoff_factor: Factor to increase delay between retries
        exceptions: List of exceptions to handle
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return recovery_manager.with_recovery(
                name,
                func,
                *args,
                **kwargs
            )
        return wrapper
    return decorator 