import logging
from typing import Optional, Callable, Awaitable, Tuple, Dict

logger = logging.getLogger(__name__)

# Type for isolation executor functions
IsolationExecutor = Callable[[str, int, bool], Awaitable[Tuple[bool, str, str, int, Optional[str]]]]

# Registry of isolation methods
ISOLATION_METHODS: Dict[str, IsolationExecutor] = {}

def register_isolation_method(name: str, executor: IsolationExecutor) -> None:
    """
    Register an isolation method.
    
    Args:
        name: Name of the isolation method
        executor: Function that executes scripts in isolation
    """
    ISOLATION_METHODS[name] = executor
    logger.debug(f"Registered isolation method: {name}")

def get_isolation_method(name: str) -> Optional[IsolationExecutor]:
    """
    Get an isolation method by name.
    
    Args:
        name: Name of the isolation method
        
    Returns:
        Isolation executor function or None if not found
    """
    return ISOLATION_METHODS.get(name)

# Import and register built-in isolation methods
from .direct import run_script_direct
from .docker import run_script_docker
from .chroot import run_script_chroot
from .venv import run_script_venv
from .sandbox import run_script_sandbox

# Register built-in isolation methods
register_isolation_method("direct", run_script_direct)
register_isolation_method("docker", run_script_docker)
register_isolation_method("chroot", run_script_chroot)
register_isolation_method("venv", run_script_venv)
register_isolation_method("sandbox", run_script_sandbox)

__all__ = [
    "register_isolation_method",
    "get_isolation_method",
    "run_script_direct",
    "run_script_docker",
    "run_script_chroot",
    "run_script_venv",
    "run_script_sandbox"
]