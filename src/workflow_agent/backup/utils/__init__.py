"""Utility functions for integrations."""
from typing import Dict, Any, Optional, List
import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """Load a YAML file."""
    try:
        with open(file_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading YAML file {file_path}: {e}")
        return {}

def get_integration_definition(integration_dir: Path) -> Dict[str, Any]:
    """Get integration definition from YAML file."""
    definition_file = integration_dir / "definition.yaml"
    return load_yaml_file(definition_file)

def get_parameter_schema(integration_dir: Path) -> Dict[str, Any]:
    """Get parameter schema from YAML file."""
    schema_file = integration_dir / "parameters.yaml"
    return load_yaml_file(schema_file)

def get_verification_data(integration_dir: Path) -> Dict[str, Any]:
    """Get verification data from YAML file."""
    verify_file = integration_dir / "verify.yaml"
    return load_yaml_file(verify_file)

def get_template_data(integration_dir: Path, template_key: str) -> Dict[str, Any]:
    """Get template data from YAML file."""
    template_file = integration_dir / "templates" / f"{template_key}.yaml"
    return load_yaml_file(template_file)

def get_supported_targets(integration_dir: Path) -> List[str]:
    """Get list of supported targets."""
    try:
        return [d.name for d in integration_dir.iterdir() if d.is_dir()]
    except Exception as e:
        logger.error(f"Error getting supported targets from {integration_dir}: {e}")
        return []

def get_integration_info(integration_dir: Path) -> Dict[str, Any]:
    """Get integration information."""
    definition = get_integration_definition(integration_dir)
    return {
        "name": definition.get("name", "unknown"),
        "version": definition.get("version", "1.0.0"),
        "description": definition.get("description", ""),
        "category": definition.get("category", "custom"),
        "supported_targets": get_supported_targets(integration_dir)
    } 