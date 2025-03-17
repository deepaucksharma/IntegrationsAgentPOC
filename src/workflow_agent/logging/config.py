import os
import logging
import logging.handlers
from typing import Optional, Dict, Any
from pathlib import Path
import json
from datetime import datetime

class LogConfig:
    """Logging configuration manager."""
    
    def __init__(
        self,
        log_level: str = 'INFO',
        log_file: Optional[str] = None,
        log_format: Optional[str] = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        json_logging: bool = False
    ):
        """
        Initialize the logging configuration.
        
        Args:
            log_level: Logging level
            log_file: Optional log file path
            log_format: Optional log format string
            max_bytes: Maximum size of log file before rotation
            backup_count: Number of backup files to keep
            json_logging: Whether to use JSON logging format
        """
        self.log_level = getattr(logging, log_level.upper())
        self.log_file = log_file
        self.log_format = log_format or (
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.json_logging = json_logging
        
    def configure(self) -> None:
        """Configure logging with the specified settings."""
        # Create formatters
        if self.json_logging:
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(self.log_format)
            
        # Create handlers
        handlers = []
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(self.log_level)
        handlers.append(console_handler)
        
        # File handler if log file is specified
        if self.log_file:
            # Ensure log directory exists
            log_dir = os.path.dirname(self.log_file)
            if log_dir:
                Path(log_dir).mkdir(parents=True, exist_ok=True)
                
            file_handler = logging.handlers.RotatingFileHandler(
                self.log_file,
                maxBytes=self.max_bytes,
                backupCount=self.backup_count
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(self.log_level)
            handlers.append(file_handler)
            
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # Add new handlers
        for handler in handlers:
            root_logger.addHandler(handler)
            
class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON string
        """
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            
        # Add extra fields if present
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
            
        return json.dumps(log_data)
        
class LogContext:
    """Context manager for logging with extra context."""
    
    def __init__(self, logger: logging.Logger, **extra: Dict[str, Any]):
        """
        Initialize the log context.
        
        Args:
            logger: Logger instance
            **extra: Extra fields to include in log messages
        """
        self.logger = logger
        self.extra = extra
        self._original_extra = {}
        
    def __enter__(self):
        """Enter the log context."""
        # Store original extra fields
        self._original_extra = getattr(self.logger, 'extra', {})
        # Set new extra fields
        self.logger.extra = {**self._original_extra, **self.extra}
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the log context."""
        # Restore original extra fields
        self.logger.extra = self._original_extra
        
class LogFilter(logging.Filter):
    """Filter for log records based on conditions."""
    
    def __init__(
        self,
        min_level: Optional[int] = None,
        max_level: Optional[int] = None,
        modules: Optional[list] = None,
        exclude_modules: Optional[list] = None
    ):
        """
        Initialize the log filter.
        
        Args:
            min_level: Minimum log level to include
            max_level: Maximum log level to include
            modules: List of module names to include
            exclude_modules: List of module names to exclude
        """
        self.min_level = min_level
        self.max_level = max_level
        self.modules = modules or []
        self.exclude_modules = exclude_modules or []
        
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter a log record.
        
        Args:
            record: Log record to filter
            
        Returns:
            True if record should be logged, False otherwise
        """
        # Check level range
        if self.min_level and record.levelno < self.min_level:
            return False
        if self.max_level and record.levelno > self.max_level:
            return False
            
        # Check module inclusion/exclusion
        if self.modules and record.module not in self.modules:
            return False
        if self.exclude_modules and record.module in self.exclude_modules:
            return False
            
        return True 