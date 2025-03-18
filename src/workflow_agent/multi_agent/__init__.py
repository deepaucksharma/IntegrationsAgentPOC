"""
Multi-agent system for workflow automation.
"""
from .coordinator import CoordinatorAgent
from .knowledge import KnowledgeAgent
from .script_builder import ScriptBuilderAgent
from .execution import ExecutionAgent
from .improvement import ImprovementAgent

__all__ = [
    "CoordinatorAgent",
    "KnowledgeAgent",
    "ScriptBuilderAgent",
    "ExecutionAgent",
    "ImprovementAgent"
]