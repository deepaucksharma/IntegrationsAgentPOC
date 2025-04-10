"""
Base agent class for all agents in the system.
This file now imports and re-exports the consolidated base agent implementation.
"""

# Import the consolidated base agent
from ...agent.consolidated_base_agent import BaseAgent

# Re-export MessageBus for backward compatibility
from ..message_bus import MessageBus

# This allows existing code to continue importing from this location
# while actually using the consolidated implementation
