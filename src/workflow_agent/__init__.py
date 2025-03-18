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
# Using lazy imports to avoid circular dependencies
def lazy_import(name):
    import importlib
    import functools
    
    @functools.wraps(importlib.import_module)
    def lazy_module():
        return importlib.import_module(name)
    return lazy_import

# These will be imported only when accessed
WorkflowAgent = lazy_import(".agent.WorkflowAgent")
WorkflowAgentFactory = lazy_import(".agent.WorkflowAgentFactory")
IntegrationBase = lazy_import(".integrations.base.IntegrationBase")
IntegrationRegistry = lazy_import(".integrations.registry.IntegrationRegistry")

# Initialize configuration from environment variables
if "WORKFLOW_TEMPLATE_DIR" in os.environ:
    template_dir = os.environ["WORKFLOW_TEMPLATE_DIR"]
    if os.path.exists(template_dir):
        from .config.templates import reload_templates
        reload_templates()
        
        schema_dir = os.path.join(template_dir, "schemas")
        if os.path.exists(schema_dir):
            from .config.schemas import load_parameter_schemas
            load_parameter_schemas([schema_dir])

# Explicit exports
__all__ = [
    "WorkflowAgent",
    "WorkflowAgentFactory",
    "IntegrationBase",
    "IntegrationRegistry",
    "__version__"
]