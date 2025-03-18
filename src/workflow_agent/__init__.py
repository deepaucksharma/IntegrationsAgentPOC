"""
Workflow Agent: A Python framework for orchestrating multi-step workflows.
"""
import logging
import os

__version__ = "0.3.0"

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

"""
Workflow Agent Package
"""

__version__ = "0.1.0"