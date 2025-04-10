"""
Base agent implementation for all specialized workflow agents.
This file now imports and re-exports the consolidated base agent implementation.
"""

# Import all from the consolidated implementation
from .consolidated_base_agent import (
    BaseAgent,
    AgentCapability,
    AgentConfig,
    AgentContext,
    AgentResult
)

# This allows existing code to continue using imports from this file
# while actually using the consolidated implementation
