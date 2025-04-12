"""
DEPRECATED: This file has been removed.

This agent implementation has been moved to workflow_agent.agent.base_agent 
to eliminate redundant implementations.

All imports should be updated to use:
from workflow_agent.agent.base_agent import BaseAgent, AgentCapability, AgentConfig, AgentContext, AgentResult
"""

raise ImportError(
    "This file has been deprecated. Please import BaseAgent from workflow_agent.agent.base_agent instead."
)
