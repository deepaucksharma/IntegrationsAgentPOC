import logging
import json
from typing import Dict, Any, Optional, List
from ..state import WorkflowState
from ..configuration import ensure_workflow_config

logger = logging.getLogger(__name__)

async def validate_parameters(
    state: WorkflowState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Validates that the parameters provided are in the correct format and that
    all required parameters (as defined in the parameter_schema) are present.
    
    Args:
        state: Current workflow state
        config: Optional configuration
        
    Returns:
        Dict with updates to workflow state or error message
        
    Error Handling:
      - Returns an error if parameters are missing or not in dictionary format
      - If a parameter schema is provided, checks for required fields
      - Validates parameter types based on schema
    """
    if not state.parameters:
        state.parameters = {}
    
    if not isinstance(state.parameters, dict):
        error_msg = "Invalid parameters: expected a dictionary."
        logger.error(error_msg)
        return {"error": error_msg}
    
    # Validate parameter types and presence if schema is provided
    warnings = []
    if state.parameter_schema:
        # Check for missing required parameters
        missing = []
        for key, spec in state.parameter_schema.items():
            if getattr(spec, "required", False) and key not in state.parameters:
                missing.append(key)
        
        if missing:
            error_msg = f"Missing required parameters: {', '.join(missing)}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Validate parameter types
        for key, value in state.parameters.items():
            if key in state.parameter_schema:
                spec = state.parameter_schema[key]
                expected_type = getattr(spec, "type", "string").lower()
                
                # Check type
                if expected_type == "number":
                    try:
                        if isinstance(value, str):
                            state.parameters[key] = float(value)
                    except ValueError:
                        warnings.append(f"Parameter '{key}' should be a number, got '{value}'. Using as string.")
                elif expected_type == "boolean":
                    if isinstance(value, str):
                        if value.lower() in ["true", "yes", "1", "y"]:
                            state.parameters[key] = True
                        elif value.lower() in ["false", "no", "0", "n"]:
                            state.parameters[key] = False
                        else:
                            warnings.append(f"Parameter '{key}' should be a boolean, got '{value}'. Using as string.")
                elif expected_type == "object" and isinstance(value, str):
                    try:
                        state.parameters[key] = json.loads(value)
                    except json.JSONDecodeError:
                        warnings.append(f"Parameter '{key}' should be a JSON object, got '{value}'. Using as string.")
    
    # Check for sensitive data in parameters (e.g., passwords, keys)
    for key, value in state.parameters.items():
        if isinstance(value, str) and key.lower() in ["password", "secret", "key", "token", "credential"]:
            if len(value) > 4:  # Simple check to avoid warning on placeholder values
                warnings.append(f"Parameter '{key}' contains sensitive data. Ensure it's handled securely.")
    
    logger.info("Parameter validation passed successfully")
    
    if warnings:
        return {"warnings": warnings}
    return {}