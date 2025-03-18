"""
Workflow Agent: A Python framework for orchestrating complex multi-step workflows.
"""
import os
import logging
from pathlib import Path

# Set up package version
__version__ = "0.2.0"

# Set up logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Define top-level exports
from .agent import WorkflowAgent, WorkflowAgentFactory
from .core.state import WorkflowState
from .integrations.base import IntegrationBase
from .integrations.registry import IntegrationRegistry

__all__ = [
    "WorkflowAgent",
    "WorkflowAgentFactory",
    "WorkflowState",
    "IntegrationBase",
    "IntegrationRegistry",
    "__version__"
]