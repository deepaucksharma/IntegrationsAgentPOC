import logging
from typing import Dict, Any, Optional, List
from ...config.schemas import get_schema, validate_parameters
from ...core.state import WorkflowState

logger = logging.getLogger(__name__)

async def validate_parameters(state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validate workflow parameters.
    
    Args:
        state: Current workflow state
        config: Optional configuration
        
    Returns:
        Dict with validation results or error
    """
    try:
        if not state.parameters:
            state.parameters = {}
        
        if not isinstance(state.parameters, dict):
            return {"error": "Invalid parameters: expected a dictionary."}
        
        # Get integration category if defined
        category = getattr(state, 'integration_category', None)
        
        # Get parameter schema
        schema = get_schema(category, state.target_name)
        
        # If no schema found, check for default schema for the integration type
        if not schema and state.integration_type:
            schema = get_schema(None, state.integration_type)
        
        # If still no schema, use empty schema
        if not schema:
            logger.warning(f"No parameter schema found for {state.target_name}")
            return {}
        
        # Check for required parameters
        missing = []
        for name, spec in schema.items():
            if spec.required and name not in state.parameters:
                missing.append(name)
        
        if missing:
            return {"error": f"Missing required parameters: {', '.join(missing)}"}
        
        # Validate parameter types and constraints
        warnings = []
        for name, value in state.parameters.items():
            if name in schema:
                spec = schema[name]
                
                # Type validation
                if spec.type == "integer" and not isinstance(value, int):
                    try:
                        state.parameters[name] = int(value)
                    except (ValueError, TypeError):
                        return {"error": f"Parameter '{name}' should be an integer."}
                
                elif spec.type == "number" and not isinstance(value, (int, float)):
                    try:
                        state.parameters[name] = float(value)
                    except (ValueError, TypeError):
                        return {"error": f"Parameter '{name}' should be a number."}
                
                elif spec.type == "boolean" and not isinstance(value, bool):
                    if isinstance(value, str):
                        if value.lower() in ("true", "yes", "1", "y"):
                            state.parameters[name] = True
                        elif value.lower() in ("false", "no", "0", "n"):
                            state.parameters[name] = False
                        else:
                            return {"error": f"Parameter '{name}' should be a boolean."}
                    else:
                        try:
                            state.parameters[name] = bool(value)
                        except (ValueError, TypeError):
                            return {"error": f"Parameter '{name}' should be a boolean."}
                
                # Constraint validation
                if spec.choices and value not in spec.choices:
                    return {"error": f"Parameter '{name}' should be one of: {', '.join(str(c) for c in spec.choices)}"}
                
                if spec.min_value is not None and value < spec.min_value:
                    return {"error": f"Parameter '{name}' should be at least {spec.min_value}."}
                
                if spec.max_value is not None and value > spec.max_value:
                    return {"error": f"Parameter '{name}' should be at most {spec.max_value}."}
                
                if spec.pattern and isinstance(value, str):
                    import re
                    if not re.match(spec.pattern, value):
                        return {"error": f"Parameter '{name}' does not match required pattern."}
                
                if spec.min_length is not None and isinstance(value, (str, list, dict)) and len(value) < spec.min_length:
                    return {"error": f"Parameter '{name}' should have at least {spec.min_length} characters."}
                
                if spec.max_length is not None and isinstance(value, (str, list, dict)) and len(value) > spec.max_length:
                    return {"error": f"Parameter '{name}' should have at most {spec.max_length} characters."}
                
                # Dependency validation
                if spec.depends_on:
                    for dep in spec.depends_on:
                        if dep not in state.parameters:
                            warnings.append(f"Parameter '{name}' usually requires '{dep}' to be set.")
                
                # Conflict validation
                if spec.conflicts_with:
                    for conflict in spec.conflicts_with:
                        if conflict in state.parameters:
                            warnings.append(f"Parameters '{name}' and '{conflict}' are typically not used together.")
        
        # Store schema in state for future reference
        state.parameter_schema = schema
        
        logger.info("Parameter validation passed successfully")
        
        if warnings:
            return {"warnings": warnings}
        return {}
    
    except Exception as e:
        logger.exception(f"Error validating parameters: {e}")
        return {"error": f"Parameter validation error: {str(e)}"}