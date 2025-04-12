"""
Agent base classes and common functionality.
This module now redirects to the main agent implementation in workflow_agent.agent.
"""
from ...agent.base_agent import BaseAgent, AgentCapability, AgentConfig, AgentContext, AgentResult

__all__ = ["BaseAgent", "AgentCapability", "AgentConfig", "AgentContext", "AgentResult"]
