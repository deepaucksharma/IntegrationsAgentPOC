"""Logging utilities for workflow agent."""
import logging
import logging.handlers
import os
import sys
import json
from typing import Optional
from datetime import datetime
import traceback

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None, json_format: bool = False):
    """Set up logging for the workflow agent."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(level)
    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    if log_file:
        try:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,
                backupCount=5
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.error(f"Failed to set up log file: {e}")

class JsonFormatter(logging.Formatter):
    """Format logs as JSON for structured logging."""
    def format(self, record):
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
        return json.dumps(log_record)

def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if level:
        level_value = getattr(logging, level.upper(), None)
        if level_value:
            logger.setLevel(level_value)
    return logger