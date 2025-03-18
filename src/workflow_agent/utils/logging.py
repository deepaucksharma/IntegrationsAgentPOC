# src/workflow_agent/utils/logging.py
import os
import logging
import logging.handlers
import sys
import json
from typing import Optional, Dict, Any
from datetime import datetime
import traceback

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None, json_format: bool = False):
    """
    Set up logging for the workflow agent.
    
    Args:
        log_level: Logging level
        log_file: Optional log file path
        json_format: Whether to use JSON format for logs
    """
    # Reset existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set log level
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(level)
    
    # Create formatter
    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Add file handler if requested
    if log_file:
        try:
            # Create directory if it doesn't exist
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # Add rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.error(f"Failed to set up log file: {e}")
    
    # Suppress overly verbose loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

class JsonFormatter(logging.Formatter):
    """Format logs as JSON for structured logging."""
    
    def format(self, record):
        """Format log record as JSON."""
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            log_record["traceback"] = traceback.format_exception(*record.exc_info)
        
        # Add extra attributes
        for key, value in record.__dict__.items():
            if key not in {
                "args", "asctime", "created", "exc_info", "exc_text", 
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "module", "msecs", "message", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName"
            }:
                log_record[key] = value
        
        return json.dumps(log_record)

def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Get a logger with the specified name and level.
    
    Args:
        name: Logger name
        level: Optional logging level override
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    
    if level:
        level_value = getattr(logging, level.upper(), None)
        if level_value:
            logger.setLevel(level_value)
    
    return logger

class LogContext:
    """Context manager for adding context to logs."""
    
    def __init__(self, logger_name: str, **kwargs):
        """
        Initialize the log context.
        
        Args:
            logger_name: Logger name
            **kwargs: Context variables to add to logs
        """
        self.logger = logging.getLogger(logger_name)
        self.context = kwargs
        self.adapter = None
    
    def __enter__(self):
        """Enter the context."""
        self.adapter = logging.LoggerAdapter(self.logger, self.context)
        return self.adapter
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context."""
        self.adapter = None