import logging
from typing import Dict, Any, Optional
from jinja2 import Template
from ..config.configuration import verification_commands

logger = logging.getLogger(__name__)

def get_verification_command(
    target_name: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Get a verification command for a target.
    
    Args:
        target_name: Name of the target
        parameters: Parameters for template rendering
        
    Returns:
        Verification command or None if not found
    """
    # Look for specific verification command
    verify_key = f"{target_name}-verify"
    verify_cmd_template = verification_commands.get(verify_key)
    
    if not verify_cmd_template:
        logger.debug(f"No verification command found for {target_name}")
        return None
    
    try:
        # Render the template with parameters
        tpl = Template(verify_cmd_template)
        params = parameters or {}
        verify_cmd = tpl.render(parameters=params)
        return verify_cmd
    except Exception as e:
        logger.error(f"Error rendering verification command template: {e}")
        return None