import os
import logging
import json
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field

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

# Global parameter schemas for supported targets/actions
parameter_schemas: Dict[str, Dict[str, ParameterSpec]] = {
    "postgres": {
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
            required=True
        ),
        "db_user": ParameterSpec(
            type="string",
            description="PostgreSQL database user",
            required=True
        ),
        "db_password": ParameterSpec(
            type="string",
            description="PostgreSQL database password",
            required=True
        )
    },
    "mysql": {
        "db_host": ParameterSpec(
            type="string",
            description="MySQL database host",
            required=True,
            default="localhost"
        ),
        "db_port": ParameterSpec(
            type="integer",
            description="MySQL database port",
            required=True,
            default=3306,
            min_value=1,
            max_value=65535
        ),
        "db_name": ParameterSpec(
            type="string",
            description="MySQL database name",
            required=True
        ),
        "db_user": ParameterSpec(
            type="string",
            description="MySQL database user",
            required=True
        ),
        "db_password": ParameterSpec(
            type="string",
            description="MySQL database password",
            required=True
        )
    },
    "redis": {
        "host": ParameterSpec(
            type="string",
            description="Redis host",
            required=True,
            default="localhost"
        ),
        "port": ParameterSpec(
            type="integer",
            description="Redis port",
            required=True,
            default=6379,
            min_value=1,
            max_value=65535
        ),
        "password": ParameterSpec(
            type="string",
            description="Redis password",
            required=False
        )
    },
    "nginx": {
        "port": ParameterSpec(
            type="integer",
            description="Nginx port",
            required=True,
            default=80,
            min_value=1,
            max_value=65535
        ),
        "ssl": ParameterSpec(
            type="boolean",
            description="Enable SSL",
            required=False,
            default=False
        ),
        "ssl_cert": ParameterSpec(
            type="string",
            description="SSL certificate path",
            required=False
        ),
        "ssl_key": ParameterSpec(
            type="string",
            description="SSL key path",
            required=False
        )
    },
    "aws": {
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
            description="License Key",
            required=True
        )
    },
    "azure": {
        "tenant_id": ParameterSpec(
            type="string",
            description="Azure Tenant ID",
            required=True
        ),
        "client_id": ParameterSpec(
            type="string",
            description="Azure Client ID",
            required=True
        ),
        "client_secret": ParameterSpec(
            type="string",
            description="Azure Client Secret",
            required=True
        ),
        "license_key": ParameterSpec(
            type="string",
            description="License Key",
            required=True
        )
    },
    "gcp": {
        "project_id": ParameterSpec(
            type="string",
            description="GCP Project ID",
            required=True
        ),
        "credentials": ParameterSpec(
            type="string",
            description="GCP Credentials JSON",
            required=True
        ),
        "license_key": ParameterSpec(
            type="string",
            description="License Key",
            required=True
        )
    },
    "apm": {
        "language": ParameterSpec(
            type="string",
            description="Language/Framework (python, nodejs, java, etc.)",
            required=True
        ),
        "app_name": ParameterSpec(
            type="string",
            description="Application Name",
            required=True
        ),
        "license_key": ParameterSpec(
            type="string",
            description="License Key",
            required=True
        )
    },
    "browser": {
        "app_id": ParameterSpec(
            type="string",
            description="Application ID",
            required=True
        ),
        "license_key": ParameterSpec(
            type="string",
            description="License Key",
            required=True
        )
    },
    # Add more target schemas as needed.
    "default": {}
}

def load_parameter_schemas(schema_dir: str) -> None:
    """
    Load parameter schemas from external files.
    
    Args:
        schema_dir: Directory containing schema files
    """
    dir_path = Path(schema_dir)
    if not dir_path.exists():
        logger.warning(f"Schema directory not found: {schema_dir}")
        return
    
    for file_path in dir_path.glob("*.{json,yaml,yml}"):
        try:
            with open(file_path, "r") as f:
                if str(file_path).endswith((".yaml", ".yml")):
                    schemas = yaml.safe_load(f)
                else:
                    schemas = json.loads(f.read())
                
                if schemas and isinstance(schemas, dict):
                    for target, schema in schemas.items():
                        if target not in parameter_schemas:
                            parameter_schemas[target] = {}
                        for param_name, param_spec in schema.items():
                            parameter_schemas[target][param_name] = ParameterSpec(**param_spec)
                    logger.info(f"Loaded parameter schemas for {target}")
        except Exception as e:
            logger.error(f"Error loading parameter schemas from {file_path}: {e}")