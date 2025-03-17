import logging
from typing import Any, Callable, Optional, List
from contextlib import contextmanager
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

class TransactionManager:
    """Manages database transactions with rollback support."""
    
    def __init__(self, session: Session):
        """
        Initialize the transaction manager.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self._operations: List[Callable] = []
        self._rollback_operations: List[Callable] = []
        
    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        try:
            yield self
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            self.rollback()
            raise
        finally:
            self._operations.clear()
            self._rollback_operations.clear()
            
    def add_operation(self, operation: Callable, rollback: Optional[Callable] = None):
        """
        Add an operation to the transaction.
        
        Args:
            operation: Operation to execute
            rollback: Optional rollback operation
        """
        self._operations.append(operation)
        if rollback:
            self._rollback_operations.append(rollback)
            
    def commit(self) -> None:
        """Commit the transaction."""
        try:
            # Execute all operations
            for operation in self._operations:
                operation()
                
            # Commit the session
            self.session.commit()
            
        except SQLAlchemyError as e:
            logger.error(f"Database error during commit: {e}")
            self.rollback()
            raise
        except Exception as e:
            logger.error(f"Error during commit: {e}")
            self.rollback()
            raise
            
    def rollback(self) -> None:
        """Rollback the transaction."""
        try:
            # Execute rollback operations in reverse order
            for operation in reversed(self._rollback_operations):
                try:
                    operation()
                except Exception as e:
                    logger.error(f"Error during rollback operation: {e}")
                    
            # Rollback the session
            self.session.rollback()
            
        except SQLAlchemyError as e:
            logger.error(f"Database error during rollback: {e}")
            raise
        except Exception as e:
            logger.error(f"Error during rollback: {e}")
            raise
            
    def execute_with_retry(
        self,
        operation: Callable,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Any:
        """
        Execute an operation with retry logic.
        
        Args:
            operation: Operation to execute
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
            
        Returns:
            Operation result
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return operation()
            except SQLAlchemyError as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Database error (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    self.session.rollback()
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Max retries exceeded: {e}")
                    raise
                    
        raise last_error
        
    def savepoint(self) -> 'Savepoint':
        """
        Create a savepoint in the current transaction.
        
        Returns:
            Savepoint object
        """
        return Savepoint(self)
        
class Savepoint:
    """Represents a savepoint in a transaction."""
    
    def __init__(self, transaction_manager: TransactionManager):
        """
        Initialize the savepoint.
        
        Args:
            transaction_manager: Parent transaction manager
        """
        self.transaction_manager = transaction_manager
        self._operations: List[Callable] = []
        self._rollback_operations: List[Callable] = []
        
    def add_operation(self, operation: Callable, rollback: Optional[Callable] = None):
        """
        Add an operation to the savepoint.
        
        Args:
            operation: Operation to execute
            rollback: Optional rollback operation
        """
        self._operations.append(operation)
        if rollback:
            self._rollback_operations.append(rollback)
            
    def commit(self) -> None:
        """Commit the savepoint."""
        # Add operations to parent transaction
        self.transaction_manager._operations.extend(self._operations)
        self.transaction_manager._rollback_operations.extend(self._rollback_operations)
        
    def rollback(self) -> None:
        """Rollback the savepoint."""
        # Execute rollback operations in reverse order
        for operation in reversed(self._rollback_operations):
            try:
                operation()
            except Exception as e:
                logger.error(f"Error during savepoint rollback: {e}")
                
class TransactionContext:
    """Context manager for database transactions."""
    
    def __init__(
        self,
        session: Session,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize the transaction context.
        
        Args:
            session: SQLAlchemy session
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
        """
        self.session = session
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
    def __enter__(self) -> TransactionManager:
        """Enter the transaction context."""
        return TransactionManager(self.session)
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the transaction context."""
        pass 