# src/workflow_agent/scripting/optimizers/__init__.py
import os
import logging
from typing import Optional, Dict, Callable, Awaitable, List, Any

logger = logging.getLogger(__name__)

# Dict to store registered optimizers
OPTIMIZERS: Dict[str, Callable] = {}

def register_optimizer(name: str, optimizer_func: Callable):
    """
    Register a script optimizer function.
    
    Args:
        name: Name for the optimizer
        optimizer_func: Function that optimizes scripts
    """
    OPTIMIZERS[name] = optimizer_func
    logger.debug(f"Registered script optimizer: {name}")

def get_optimizer(name: str) -> Optional[Callable]:
    """
    Get a registered optimizer by name.
    
    Args:
        name: Name of the optimizer
        
    Returns:
        Optimizer function or None if not found
    """
    return OPTIMIZERS.get(name)

# Import and register built-in optimizers
from .llm import llm_optimize
from .shellcheck import shellcheck_optimize
from .rule_based import optimize_script

# Register built-in optimizers
register_optimizer("llm", llm_optimize)
register_optimizer("shellcheck", shellcheck_optimize)
register_optimizer("rule-based", optimize_script)

__all__ = ["register_optimizer", "get_optimizer"]