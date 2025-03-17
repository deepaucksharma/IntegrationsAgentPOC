import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pydantic import BaseModel, Field
import yaml
import json

logger = logging.getLogger(__name__)

class WorkflowConfiguration(BaseModel):
    """Configuration for the workflow agent."""
    user_id: str = "cli-user"
    model_name: str = "openai/gpt-3.5-turbo"
    system_prompt: str = "You are a helpful workflow agent."
    template_dir: str = "./templates"
    custom_template_dir: Optional[str] = None  # Added: for user-defined templates
    use_isolation: bool = False
    isolation_method: str = "docker"  # Added: docker, chroot, venv, none
    execution_timeout: int = 30000  # in milliseconds
    skip_verification: bool = False
    use_llm_optimization: bool = False  # Added: make LLM optimization optional
    rule_based_optimization: bool = False  # Added: alternative to LLM optimization
    use_static_analysis: bool = False  # Added: for script validation
    db_connection_string: Optional[str] = None  # Added: for database scaling
    prune_history_days: Optional[int] = None  # Added: for history management
    plugin_dirs: List[str] = Field(default_factory=lambda: ["./plugins"])  # Added: for plugin architecture
    async_execution: bool = False  # Added: for concurrent execution
    max_concurrent_tasks: int = 5  # Added: for concurrent execution
    least_privilege_execution: bool = True  # Added: for security
    sandbox_isolation: bool = False  # Added: for stronger isolation
    log_level: str = "INFO"
    
    class Config:
        """Configuration for the model."""
        extra = "allow"  # Allow extra fields for extensions

def ensure_workflow_config(config: Dict[str, Any] = None) -> WorkflowConfiguration:
    """
    Ensure a valid workflow configuration exists.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Validated WorkflowConfiguration object
    """
    try:
        if config and "configurable" in config:
            return WorkflowConfiguration(**config["configurable"])
    except Exception as e:
        logger.warning(f"Error in configuration: {e}. Using defaults.")
    return WorkflowConfiguration()

# Load templates from template directories
def load_templates() -> Dict[str, str]:
    """
    Load script templates from template directories.
    
    Checks both the default template directory and user-defined custom directory.
    
    Returns:
        Dictionary mapping template keys to template content
    """
    templates = {}
    
    # Default templates (these are hardcoded fallbacks)
    templates.update({
        "default-install": """#!/usr/bin/env bash
set -e
echo "Installing {{ target_name }} with action {{ action }}"
# Add your installation commands here.
""",
        "default-rollback": """#!/usr/bin/env bash
set -e
echo "Rolling back {{ target_name }} changes"
# Add your rollback commands here.
"""
    })
    
    # Load from template directories
    config = ensure_workflow_config()
    dirs_to_check = [config.template_dir]
    
    if config.custom_template_dir:
        dirs_to_check.append(config.custom_template_dir)
    
    for template_dir in dirs_to_check:
        dir_path = Path(template_dir)
        if not dir_path.exists():
            continue
            
        for file_path in dir_path.glob("*.sh.j2"):
            try:
                key = file_path.stem.replace(".sh", "")
                with open(file_path, "r") as f:
                    templates[key] = f.read()
                logger.debug(f"Loaded template: {key} from {file_path}")
            except Exception as e:
                logger.error(f"Error loading template {file_path}: {e}")
    
    return templates

# Dynamic loading of script templates
script_templates: Dict[str, str] = load_templates()

# Function to reload templates (for runtime updates)
def reload_templates() -> None:
    """Reload script templates from template directories."""
    global script_templates
    script_templates = load_templates()
    logger.info("Templates reloaded")

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

# Function to load schema from external files
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

# Global verification commands for supported targets/actions.
verification_commands: Dict[str, str] = {
    # Example: key "postgres-verify" can include a shell command template.
    "postgres-verify": "psql -h {{ parameters.db_host }} -p {{ parameters.db_port }} -c '\\l'",
    "mysql-verify": "mysql -h {{ parameters.db_host }} -P {{ parameters.db_port }} -e 'SHOW DATABASES;'"
}

# Function to load verification commands from external files
def load_verification_commands(verif_dir: str) -> None:
    """
    Load verification commands from external files.
    
    Args:
        verif_dir: Directory containing verification command files
    """
    global verification_commands
    
    dir_path = Path(verif_dir)
    if not dir_path.exists():
        logger.warning(f"Verification directory not found: {verif_dir}")
        return
    
    for file_path in dir_path.glob("*.{json,yaml,yml}"):
        try:
            with open(file_path, "r") as f:
                if str(file_path).endswith((".yaml", ".yml")):
                    commands = yaml.safe_load(f)
                else:
                    commands = json.loads(f.read())
                
                if commands and isinstance(commands, dict):
                    verification_commands.update(commands)
                    logger.info(f"Loaded verification commands from {file_path}")
        except Exception as e:
            logger.error(f"Error loading verification commands from {file_path}: {e}")

# List of dangerous command patterns for script validation
dangerous_patterns: List[str] = [
    r"rm\s+(-rf?\s+)?\/(?!\w)",
    r"mkfs",
    r"dd\s+if=.*\s+of=\/dev",
    r">\s*\/dev\/[hs]d[a-z]",
    r"chmod\s+777",
    r"chmod\s+-R\s+777",
    r"wget.*\s+\|\s+bash",
    r"curl.*\s+\|\s+bash",
    r":(){:\|:&};:",
    r"rm\s+-rf\s+~",
    r"wipe\s+.*\/dev",
    r"fdisk\s+\/dev.*\s+(d|n)",
    # Added more dangerous patterns
    r"chown\s+-R\s+root",
    r"killall\s+.*",
    r"rm\s+-rf\s+\*",
    r"rm\s+-rf\s+\/\w+\/\*",
    r">\s*\/etc\/passwd",
    r">\s*\/etc\/shadow",
    r"chmod\s+[0-7]*777[0-7]*\s+",
    r"shutdown\s+(now|-h|-r)",
    r"reboot\s+",
    r"init\s+[06]"
]

# Function to load dangerous patterns from external file
def load_dangerous_patterns(pattern_file: str) -> None:
    """
    Load dangerous command patterns from a file.
    
    Args:
        pattern_file: File containing patterns, one per line
    """
    global dangerous_patterns
    
    try:
        with open(pattern_file, "r") as f:
            patterns = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            if patterns:
                dangerous_patterns.extend(patterns)
                logger.info(f"Loaded {len(patterns)} dangerous patterns from {pattern_file}")
    except Exception as e:
        logger.error(f"Error loading dangerous patterns from {pattern_file}: {e}")