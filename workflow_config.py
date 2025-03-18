import os
from typing import Dict, Any
from pydantic import root_validator
from log import logger

class WorkflowConfig:
    @root_validator(pre=True)
    def resolve_workspace_paths(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve ${WORKSPACE_ROOT} in paths."""
        workspace_root = os.environ.get("WORKSPACE_ROOT", os.getcwd())
        
        processed = {}
        
        for key, value in values.items():
            if isinstance(value, str) and "${WORKSPACE_ROOT}" in value:
                processed[key] = value.replace("${WORKSPACE_ROOT}", workspace_root)
            elif isinstance(value, list):
                processed[key] = [
                    item.replace("${WORKSPACE_ROOT}", workspace_root) 
                    if isinstance(item, str) and "${WORKSPACE_ROOT}" in item
                    else item
                    for item in value
                ]
            else:
                processed[key] = value
                
        return processed

    @root_validator
    def validate_paths_exist(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that specified paths exist and are accessible."""
        paths_to_check = {
            "template_dir": values.get("template_dir"),
            "custom_template_dir": values.get("custom_template_dir"),
            "docs_cache_dir": values.get("docs_cache_dir")
        }
        
        for path_name, path in paths_to_check.items():
            if path is not None:
                if not path.exists():
                    try:
                        path.mkdir(parents=True, exist_ok=True)
                        logger.info(f"Created directory for {path_name}: {path}")
                    except Exception as e:
                        raise ConfigurationError(f"Failed to create {path_name} directory: {e}")
                
                if not os.access(path, os.R_OK | os.W_OK):
                    raise ConfigurationError(f"Insufficient permissions for {path_name}: {path}")

        return values

    @root_validator
    def validate_security_settings(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate security-related configuration settings."""
        if values.get("skip_verification") and not values.get("least_privilege_execution"):
            logger.warning("Security risk: Skip verification enabled without least privilege execution")
            
        if values.get("isolation_method") == "none" and values.get("use_isolation"):
            raise ConfigurationError("Conflicting settings: isolation_method is 'none' but use_isolation is True")
            
        if values.get("execution_timeout") > 3600:
            logger.warning("Security risk: Long execution timeout may lead to resource exhaustion")
            
        return values

    def validate_command(self, command: str) -> bool:
        """
        Validate a command string against known dangerous patterns.
        Returns True if command is safe, False otherwise.
        """
        import re
        for pattern in dangerous_patterns:
            if re.search(pattern, command):
                logger.warning(f"Potentially dangerous command pattern detected: {pattern}")
                return False
        return True 