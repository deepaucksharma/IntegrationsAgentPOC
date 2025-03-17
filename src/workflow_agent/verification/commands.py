import logging
from typing import Dict, Any, Optional, List
from jinja2 import Template
from ..core.state import WorkflowState
from ..config.configuration import verification_commands

logger = logging.getLogger(__name__)

def get_verification_command(state: WorkflowState) -> Optional[str]:
    """
    Get verification command for the current state.
    
    Args:
        state: Current workflow state
        
    Returns:
        Verification command or None if not found
    """
    # Try various keys to find a verification command
    command_keys = []
    
    # Add category-specific key if available
    if hasattr(state, "integration_category") and state.integration_category:
        command_keys.append(f"{state.integration_category}/{state.target_name}-verify")
    
    # Add direct target key
    command_keys.append(f"{state.target_name}-verify")
    
    # Add integration-type key
    command_keys.append(f"{state.integration_type}-verify")
    
    # Add default key
    command_keys.append("default-verify")
    
    # Try each key
    for key in command_keys:
        if key in verification_commands:
            logger.debug(f"Found verification command for key: {key}")
            return verification_commands[key]
    
    # Try to generate a reasonable default based on target type
    command = _generate_default_verification(state)
    if command:
        logger.debug(f"Generated default verification command for {state.target_name}")
        return command
    
    logger.warning(f"No verification command found for {state.target_name}")
    return None

def _generate_default_verification(state: WorkflowState) -> Optional[str]:
    """
    Generate a default verification command based on target type.
    
    Args:
        state: Current workflow state
        
    Returns:
        Generated verification command or None
    """
    target = state.target_name.lower()
    
    # For database servers
    if "postgres" in target:
        return "pg_isready -h {{ parameters.db_host }} -p {{ parameters.db_port }} && echo 'PostgreSQL is ready'"
    elif "mysql" in target:
        return "mysqladmin -h {{ parameters.db_host }} -P {{ parameters.db_port }} ping && echo 'MySQL is ready'"
    elif "redis" in target:
        return "redis-cli -h {{ parameters.host }} -p {{ parameters.port }} ping && echo 'Redis is ready'"
    elif "mongodb" in target:
        return "mongosh --host {{ parameters.db_host }} --port {{ parameters.db_port }} --eval 'db.runCommand({ ping: 1 })' && echo 'MongoDB is ready'"
    
    # For web servers
    elif "nginx" in target:
        return "systemctl is-active nginx && curl -s http://localhost:{{ parameters.port | default(80) }}/ -o /dev/null -w '%{http_code}' | grep -q '200' && echo 'Nginx is ready'"
    elif "apache" in target or "httpd" in target:
        return "systemctl is-active httpd apache2 && curl -s http://localhost:{{ parameters.port | default(80) }}/ -o /dev/null -w '%{http_code}' | grep -q '200' && echo 'Apache is ready'"
    
    # For monitoring agents
    elif "newrelic" in target:
        return "systemctl is-active newrelic-infra && grep -q 'Connected to New Relic platform' /var/log/newrelic-infra/newrelic-infra.log && echo 'New Relic agent is connected'"
    
    # For cloud services
    elif "aws" in target:
        return "aws sts get-caller-identity && echo 'AWS credentials are valid'"
    elif "azure" in target:
        return "az account show && echo 'Azure credentials are valid'"
    elif "gcp" in target:
        return "gcloud auth list && echo 'GCP credentials are valid'"
    
    # Default fallback for service-based integrations
    return f"systemctl is-active {target} && echo '{target} service is active'"