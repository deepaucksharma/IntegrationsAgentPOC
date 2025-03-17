import os
import logging
from pathlib import Path
from .agent import WorkflowAgent, WorkflowAgentFactory
from .core.state import WorkflowState, ParameterSchema, ParameterSpec, Change, ExecutionMetrics, OutputData
from .config.configuration import (
    WorkflowConfiguration, 
    ensure_workflow_config,
    dangerous_patterns,
    verification_commands
)
from .config.templates import script_templates, reload_templates
from .config.schemas import parameter_schemas, load_parameter_schemas
from .workflow import WorkflowGraph, WorkflowExecutor
from .integrations.base import IntegrationBase
from .integrations.registry import IntegrationRegistry
from .utils.logging import setup_logging

# Set up package version
__version__ = "0.2.0"

# Set up default logging configuration
setup_logging()

# Initialize configuration from environment variables
if "WORKFLOW_TEMPLATE_DIR" in os.environ:
    template_dir = os.environ["WORKFLOW_TEMPLATE_DIR"]
    if os.path.exists(template_dir):
        # Load templates
        reload_templates()
        
        # Load parameter schemas
        schema_dir = os.path.join(template_dir, "schemas")
        if os.path.exists(schema_dir):
            load_parameter_schemas(schema_dir)
        
        # Load verification commands
        verification_dir = os.path.join(template_dir, "verifications")
        if os.path.exists(verification_dir):
            from .config.configuration import load_verification_commands
            load_verification_commands(verification_dir)
        
        # Load dangerous patterns
        patterns_file = os.path.join(template_dir, "dangerous_patterns.txt")
        if os.path.exists(patterns_file):
            from .config.configuration import load_dangerous_patterns
            load_dangerous_patterns(patterns_file)

__all__ = [
    "WorkflowAgent",
    "WorkflowAgentFactory",
    "WorkflowState",
    "ParameterSchema",
    "ParameterSpec",
    "Change",
    "ExecutionMetrics", 
    "OutputData",
    "WorkflowConfiguration",
    "ensure_workflow_config",
    "script_templates",
    "parameter_schemas",
    "verification_commands",
    "reload_templates",
    "WorkflowGraph",
    "WorkflowExecutor",
    "IntegrationBase",
    "IntegrationRegistry",
    "__version__"
]