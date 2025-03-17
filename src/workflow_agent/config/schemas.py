import os
import logging
import json
import yaml
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Global parameter schemas for supported targets.
parameter_schemas: Dict[str, Dict[str, Any]] = {
    "postgres": {
        "db_host":  type("Spec", (), {"type": "string", "description": "Database host", "required": True, "default": "localhost"}),
        "db_port":  type("Spec", (), {"type": "number", "description": "Database port", "required": True, "default": 5432})
    },
    "mysql": {
        "db_host":  type("Spec", (), {"type": "string", "description": "Database host", "required": True, "default": "localhost"}),
        "db_port":  type("Spec", (), {"type": "number", "description": "Database port", "required": True, "default": 3306})
    },
    "aws": {
        "aws_access_key": type("Spec", (), {"type": "string", "description": "AWS Access Key", "required": True}),
        "aws_secret_key": type("Spec", (), {"type": "string", "description": "AWS Secret Key", "required": True}),
        "license_key":    type("Spec", (), {"type": "string", "description": "License Key", "required": True})
    },
    "azure": {
        "tenant_id":     type("Spec", (), {"type": "string", "description": "Azure Tenant ID", "required": True}),
        "client_id":     type("Spec", (), {"type": "string", "description": "Azure Client ID", "required": True}),
        "client_secret": type("Spec", (), {"type": "string", "description": "Azure Client Secret", "required": True}),
        "license_key":   type("Spec", (), {"type": "string", "description": "License Key", "required": True})
    },
    "gcp": {
        "project_id":  type("Spec", (), {"type": "string", "description": "GCP Project ID", "required": True}),
        "credentials": type("Spec", (), {"type": "string", "description": "GCP Credentials JSON", "required": True}),
        "license_key": type("Spec", (), {"type": "string", "description": "License Key", "required": True})
    },
    "apm": {
        "language":    type("Spec", (), {"type": "string", "description": "Language/Framework (python, nodejs, java, etc.)", "required": True}),
        "app_name":    type("Spec", (), {"type": "string", "description": "Application Name", "required": True}),
        "license_key": type("Spec", (), {"type": "string", "description": "License Key", "required": True})
    },
    "browser": {
        "app_id":      type("Spec", (), {"type": "string", "description": "Application ID", "required": True}),
        "license_key": type("Spec", (), {"type": "string", "description": "License Key", "required": True})
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
    global parameter_schemas
    
    dir_path = Path(schema_dir)
    if not dir_path.exists():
        logger.warning(f"Schema directory not found: {schema_dir}")
        return
    
    for file_path in dir_path.glob("*.{json,yaml,yml}"):
        try:
            with open(file_path, "r") as f:
                if str(file_path).endswith((".yaml", ".yml")):
                    schema = yaml.safe_load(f)
                else:
                    schema = json.loads(f.read())
                
                target_name = file_path.stem
                if schema and isinstance(schema, dict):
                    # Convert dictionary to parameter spec objects
                    spec_dict = {}
                    for key, details in schema.items():
                        spec_dict[key] = type("Spec", (), {
                            "type": details.get("type", "string"),
                            "description": details.get("description", ""),
                            "required": details.get("required", False),
                            "default": details.get("default", None)
                        })
                    parameter_schemas[target_name] = spec_dict
                    logger.info(f"Loaded parameter schema for {target_name}")
        except Exception as e:
            logger.error(f"Error loading schema from {file_path}: {e}")