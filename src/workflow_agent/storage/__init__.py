# src/workflow_agent/storage/__init__.py
from .history import HistoryManager
from .models import ExecutionRecord

__all__ = [
    'HistoryManager',
    'ExecutionRecord',
    'get_execution_history',
    'get_execution_statistics',
    'clear_history'
]

async def get_execution_history(target: str, action: str, limit: int = 10, user_id: str = None):
    """Get execution history for a specific target and action."""
    manager = HistoryManager()
    await manager.initialize()
    try:
        return await manager.get_execution_history(target, action, limit, user_id)
    finally:
        await manager.close()

async def get_execution_statistics(target: str, action: str, user_id: str = None):
    """Get statistics for a specific target and action."""
    manager = HistoryManager()
    await manager.initialize()
    try:
        return await manager.get_execution_statistics(target, action, user_id)
    finally:
        await manager.close()

async def clear_history(target: str = None, action: str = None, days: int = None, user_id: str = None):
    """Clear execution history."""
    manager = HistoryManager()
    await manager.initialize()
    try:
        return await manager.clear_history(target, action, days, user_id)
    finally:
        await manager.close()