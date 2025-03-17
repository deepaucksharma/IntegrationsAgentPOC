import os
import logging
import json
import yaml
from typing import Dict, Any, Optional, List, Type
from pathlib import Path
from pydantic import BaseModel, Field, ValidationError, create_model
from ..error.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

class ParameterSpec(BaseModel):
    """Specification for a parameter."""
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Optional[Any] = None
    choices: Optional[list] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    depends_on: Optional[List[str]] = None
    conflicts_with: Optional[List[str]] = None
    example: Optional[Any] = None

    class Config:
        """Configuration for the model."""
        extra = "allow"  # Allow extra fields for extensibility

class CategorySchema(BaseModel):
    """Schema for a category of integrations."""
    name: str
    description: str
    parameters: Dict[str, ParameterSpec] = Field(default_factory=dict)

# Global parameter schemas by category and integration
parameter_schemas: Dict[str, Dict[str, Dict[str, ParameterSpec]]] = {}

# Cache for dynamically created pydantic models
_schema_model_cache: Dict[str, Type[BaseModel]] = {}

def initialize_schemas() -> Dict[str, Dict[str, Dict[str, ParameterSpec]]]:
    """Initialize schema structure with empty categories."""
    global parameter_schemas
    parameter_schemas = {
        "aws": {},
        "azure": {},
        "gcp": {},
        "database": {},
        "webserver": {},
        "monitoring": {},
        "container": {},
        "network": {},
        "security": {},
        "custom": {},
    }
    return parameter_schemas

def load_default_schemas() -> None:
    """Load built-in default schemas."""
    # Database schemas
    add_schema("database", "postgres", {
        "db_host": ParameterSpec(
            type="string",
            description="PostgreSQL database host",
            required=True,
            default="localhost"
        ),
        "db_port": ParameterSpec(
            type="integer",
            description="PostgreSQL database port",
            required=True,
            default=5432,
            min_value=1,
            max_value=65535
        ),
        "db_name": ParameterSpec(
            type="string",
            description="PostgreSQL database name",
            required=False
        ),
        "db_user": ParameterSpec(
            type="string",
            description="PostgreSQL database user",
            required=False
        ),
        "db_password": ParameterSpec(
            type="string",
            description="PostgreSQL database password",
            required=False
        ),
        "license_key": ParameterSpec(
            type="string",
            description="New Relic license key",
            required=True
        )
    })

    # AWS schemas
    add_schema("aws", "default", {
        "aws_access_key": ParameterSpec(
            type="string",
            description="AWS Access Key",
            required=True
        ),
        "aws_secret_key": ParameterSpec(
            type="string",
            description="AWS Secret Key",
            required=True
        ),
        "license_key": ParameterSpec(
            type="string",
            description="New Relic License Key",
            required=True
        ),
        "aws_region": ParameterSpec(
            type="string",
            description="AWS Region",
            required=False,
            default="us-east-1",
            choices=["us-east-1", "us-east-2", "us-west-1", "us-west-2", "eu-west-1", "eu-central-1", "ap-northeast-1", "ap-southeast-1", "ap-southeast-2"]
        ),
    })

def find_schema_dirs(base_dir: str) -> List[Path]:
    """
    Find all schema directories in the base directory.
    
    Args:
        base_dir: Base directory to search
        
    Returns:
        List of paths to schema directories
    """
    schema_dirs = []
    base_path = Path(base_dir)
    
    # Check for root schemas directory
    root_schema_dir = base_path / "schemas"
    if root_schema_dir.exists() and root_schema_dir.is_dir():
        schema_dirs.append(root_schema_dir)
    
    # Check for category schema directories
    for category in parameter_schemas.keys():
        category_schema_dir = base_path / category / "schemas"
        if category_schema_dir.exists() and category_schema_dir.is_dir():
            schema_dirs.append(category_schema_dir)
    
    return schema_dirs

def load_parameter_schemas(schema_dirs: List[str]) -> None:
    """
    Load parameter schemas from specified directories.
    
    Args:
        schema_dirs: List of directories containing schema files
    """
    # Initialize with default schema structure
    initialize_schemas()
    
    # Load defaults
    load_default_schemas()
    
    # Process each schema directory
    for schema_dir in schema_dirs:
        dir_path = Path(schema_dir)
        if not dir_path.exists():
            logger.warning(f"Schema directory not found: {schema_dir}")
            continue
        
        # Check if this is a category schema directory
        category = None
        parent_dir = dir_path.parent
        if parent_dir.name in parameter_schemas:
            category = parent_dir.name
        
        # Process all schema files
        for file_path in dir_path.glob("**/*.{json,yaml,yml}"):
            try:
                with open(file_path, "r") as f:
                    file_extension = file_path.suffix.lower()
                    if file_extension in (".yaml", ".yml"):
                        schemas = yaml.safe_load(f)
                    else:
                        schemas = json.loads(f.read())
                
                # Skip if no schemas found
                if not schemas or not isinstance(schemas, dict):
                    continue
                
                # Determine schema category and target
                schema_category = category
                schema_target = file_path.stem
                
                # Handle different schema file formats
                if "category" in schemas and "targets" in schemas:
                    # Format: {category: "name", targets: {target1: {...}, target2: {...}}}
                    schema_category = schemas["category"]
                    for target, schema in schemas["targets"].items():
                        _load_schema(schema_category, target, schema)
                elif "parameters" in schemas:
                    # Format: {parameters: {...}}
                    _load_schema(schema_category, schema_target, schemas["parameters"])
                else:
                    # Format: {target1: {...}, target2: {...}} or {param1: {...}, param2: {...}}
                    if any(isinstance(v, dict) and "type" in v for v in schemas.values()):
                        # This is a parameters dict
                        _load_schema(schema_category, schema_target, schemas)
                    else:
                        # This is a targets dict
                        for target, schema in schemas.items():
                            if isinstance(schema, dict):
                                _load_schema(schema_category, target, schema)
                
                logger.debug(f"Loaded schema(s) from {file_path}")
            except Exception as e:
                logger.error(f"Error loading schema from {file_path}: {e}")

def _load_schema(category: Optional[str], target: str, schema_dict: Dict[str, Any]) -> None:
    """
    Load a schema for a target in a category.
    
    Args:
        category: Schema category or None for uncategorized
        target: Target name
        schema_dict: Schema dictionary
    """
    # Default to custom category if none specified
    if not category:
        category = "custom"
    
    # Ensure category exists
    if category not in parameter_schemas:
        parameter_schemas[category] = {}
    
    # Process schema parameters
    params = {}
    for param_name, param_spec in schema_dict.items():
        if isinstance(param_spec, dict):
            try:
                params[param_name] = ParameterSpec(**param_spec)
            except ValidationError as e:
                logger.warning(f"Invalid parameter spec for {param_name}: {e}")
    
    # Store in global schemas
    parameter_schemas[category][target] = params
    logger.debug(f"Loaded schema for {category}/{target} with {len(params)} parameters")

def add_schema(category: str, target: str, params: Dict[str, ParameterSpec]) -> None:
    """
    Add or update a schema for a target in a category.
    
    Args:
        category: Schema category
        target: Target name
        params: Dictionary of parameter specs
    """
    # Ensure category exists
    if category not in parameter_schemas:
        parameter_schemas[category] = {}
    
    # Store params
    parameter_schemas[category][target] = params
    logger.debug(f"Added schema for {category}/{target} with {len(params)} parameters")

def get_schema(category: Optional[str], target: str) -> Dict[str, ParameterSpec]:
    """
    Get schema for a target, optionally in a specific category.
    
    Args:
        category: Optional category to look in
        target: Target name
        
    Returns:
        Dictionary of parameter specs for the target
    """
    # Check specific category if provided
    if category and category in parameter_schemas:
        if target in parameter_schemas[category]:
            return parameter_schemas[category][target]
    
    # Otherwise check all categories
    for cat, targets in parameter_schemas.items():
        if target in targets:
            return targets[target]
    
    # Return empty dict if no schema found
    return {}

def get_schema_model(category: Optional[str], target: str) -> Type[BaseModel]:
    """
    Get a Pydantic model for parameter validation based on schema.
    
    Args:
        category: Optional category to look in
        target: Target name
        
    Returns:
        Pydantic model class for the schema
    """
    # Generate cache key
    cache_key = f"{category or 'any'}:{target}"
    
    # Return cached model if available
    if cache_key in _schema_model_cache:
        return _schema_model_cache[cache_key]
    
    # Get schema parameters
    params = get_schema(category, target)
    
    # Prepare field definitions for model
    fields = {}
    for name, spec in params.items():
        # Convert ParameterSpec to Pydantic field
        field_type = str
        if spec.type == "integer":
            field_type = int
        elif spec.type == "number":
            field_type = float
        elif spec.type == "boolean":
            field_type = bool
        
        # Create field with appropriate type and constraints
        field_info = Field(
            default=spec.default,
            description=spec.description
        )
        
        fields[name] = (field_type, field_info)
    
    # Create model dynamically
    model_name = f"{target.capitalize()}Parameters"
    model = create_model(model_name, **fields)
    
    # Cache and return
    _schema_model_cache[cache_key] = model
    return model

def validate_parameters(category: Optional[str], target: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate parameters against schema.
    
    Args:
        category: Optional category to look in
        target: Target name
        parameters: Parameters to validate
        
    Returns:
        Validated parameters or raises ValidationError
    """
    # Get schema model
    model = get_schema_model(category, target)
    
    # Validate parameters
    validated = model(**parameters)
    
    # Return as dict
    return validated.dict()

def get_categories() -> List[str]:
    """
    Get list of available schema categories.
    
    Returns:
        List of category names
    """
    return list(parameter_schemas.keys())

def get_targets(category: Optional[str] = None) -> List[str]:
    """
    Get list of available targets, optionally filtered by category.
    
    Args:
        category: Optional category to filter by
        
    Returns:
        List of target names
    """
    if category and category in parameter_schemas:
        return list(parameter_schemas[category].keys())
    
    targets = []
    for cat_targets in parameter_schemas.values():
        targets.extend(cat_targets.keys())
    
    return list(set(targets))  # Remove duplicates

def clear_schema_cache() -> None:
    """Clear the schema model cache."""
    _schema_model_cache.clear()