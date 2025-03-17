# src/workflow_agent/utils/logging.py
import os
import logging
from typing import Optional
from pathlib import Path

def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
) -> None:
    """
    Configure logging for the workflow agent.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file (optional)
        log_format: Log format string
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure basic logging
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Add file handler if specified
    if log_file:
        log_path = Path(log_file)
        
        # Create directory if it doesn't exist
        if not log_path.parent.exists():
            log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        
        # Add handler to root logger
        logging.getLogger().addHandler(file_handler)
    
    # Set third-party loggers to a higher level to reduce noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    
    logging.info(f"Logging configured with level {log_level}")