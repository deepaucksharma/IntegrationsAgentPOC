"""
Enhanced logging utilities with structured formatting.
"""
import logging
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union
import logging.handlers

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def __init__(self, **kwargs):
        """Initialize with optional fields."""
        self.additional_fields = kwargs
        super().__init__()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        
        # Add execution context if available
        if hasattr(record, "workflow_id"):
            log_data["workflow_id"] = record.workflow_id
        if hasattr(record, "execution_id"):
            log_data["execution_id"] = record.execution_id
        if hasattr(record, "integration_type"):
            log_data["integration_type"] = record.integration_type
        if hasattr(record, "action"):
            log_data["action"] = record.action
            
        # Add exception info if available
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
            
        # Add additional fields
        log_data.update(self.additional_fields)
        
        # Add any extra attributes
        if hasattr(record, "data"):
            log_data["data"] = record.data
            
        return json.dumps(log_data)

class WorkflowLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds workflow context to log records."""
    
    def process(self, msg, kwargs):
        """Add context to log records."""
        kwargs.setdefault("extra", {}).update(self.extra)
        return msg, kwargs

def configure_logging(config: Dict[str, Any]) -> None:
    """
    Configure logging with structured formatting.
    
    Args:
        config: Configuration dictionary
    """
    log_level = getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO)
    log_file = config.get("log_file", "workflow_agent.log")
    use_json = config.get("structured_logging", True)
    log_to_console = config.get("log_to_console", True)
    max_bytes = config.get("log_max_bytes", 10 * 1024 * 1024)  # 10 MB
    backup_count = config.get("log_backup_count", 5)
    
    # Create log directory if needed
    log_path = Path(log_file)
    if log_path.parent != Path("."):
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create handlers
    handlers = []
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, 
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    handlers.append(file_handler)
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        handlers.append(console_handler)
    
    # Set formatters
    if use_json:
        json_formatter = JsonFormatter(
            application="workflow_agent",
            version=config.get("version", "1.0.0"),
            environment=config.get("environment", "development")
        )
        for handler in handlers:
            handler.setFormatter(json_formatter)
    else:
        standard_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        )
        for handler in handlers:
            handler.setFormatter(standard_formatter)
    
    # Add handlers to root logger
    for handler in handlers:
        root_logger.addHandler(handler)
    
    # Log configuration info
    logging.info(f"Logging configured with level: {config.get('log_level', 'INFO')}")
    logging.debug(f"Log file: {log_file}")

def get_logger(name: str, **context) -> logging.Logger:
    """
    Get a logger with context.
    
    Args:
        name: Logger name
        **context: Additional context fields
        
    Returns:
        Logger with context
    """
    logger = logging.getLogger(name)
    
    if context:
        return WorkflowLoggerAdapter(logger, context)
    
    return logger

def get_workflow_logger(
    name: str,
    workflow_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    integration_type: Optional[str] = None,
    action: Optional[str] = None,
    **context
) -> logging.Logger:
    """
    Get a logger with workflow context.
    
    Args:
        name: Logger name
        workflow_id: Workflow ID
        execution_id: Execution ID
        integration_type: Integration type
        action: Action being performed
        **context: Additional context fields
        
    Returns:
        Logger with workflow context
    """
    extra = {}
    
    if workflow_id:
        extra["workflow_id"] = workflow_id
    if execution_id:
        extra["execution_id"] = execution_id
    if integration_type:
        extra["integration_type"] = integration_type
    if action:
        extra["action"] = action
        
    extra.update(context)
    
    return WorkflowLoggerAdapter(logging.getLogger(name), extra)
