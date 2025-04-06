"""
Template management for script generation with consistent search and loading.
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
import json
import datetime
import jinja2
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape

from ..config.configuration import WorkflowConfiguration
from ..error.exceptions import TemplateError
from ..utils.error_handling import handle_errors

logger = logging.getLogger(__name__)

class TemplateManager:
    """
    Manages template loading, resolution, and rendering with clear precedence rules.
    Maintains a consistent template search path and resolution order.
    """
    
    def __init__(self, config: WorkflowConfiguration):
        """
        Initialize the template manager with configuration.
        
        Args:
            config: WorkflowConfiguration with template paths
        """
        self.config = config
        self.template_dirs = self._get_template_dirs()
        self.template_env = self._initialize_environment()
        self.templates_cache: Dict[str, str] = {}
        
        # Define clear precedence order for template resolution
        self.precedence_order = [
            "custom",     # Custom templates (highest precedence)
            "project",    # Project-specific templates
            "integration", # Integration-specific templates
            "common",     # Common shared templates
            "default"     # Default fallback templates (lowest precedence)
        ]
        
        self._load_templates()
        
    def _get_template_dirs(self) -> Dict[str, Path]:
        """
        Get all template directories in order of precedence.
        
        Returns:
            Dictionary of template category to directory path
        """
        dirs = {}
        
        # Custom templates have highest precedence
        if self.config.custom_template_dir and self.config.custom_template_dir.exists():
            dirs["custom"] = self.config.custom_template_dir
            
        # Then project templates
        project_template_dir = self.config.template_dir
        if project_template_dir and project_template_dir.exists():
            dirs["project"] = project_template_dir
            
        # Integration-specific templates
        integration_template_dir = project_template_dir / "integrations" if project_template_dir else None
        if integration_template_dir and integration_template_dir.exists():
            dirs["integration"] = integration_template_dir
            
        # Common templates
        common_templates = project_template_dir / "common" if project_template_dir else None
        if common_templates and common_templates.exists():
            dirs["common"] = common_templates
            
        # Default templates are last
        default_templates = Path(__file__).parent / "default_templates"
        if not default_templates.exists():
            default_templates.mkdir(parents=True, exist_ok=True)
            
        dirs["default"] = default_templates
        
        # Log the directories found
        for category, path in dirs.items():
            logger.debug(f"Template directory for '{category}': {path}")
            
        return dirs

    def _initialize_environment(self) -> Environment:
        """
        Initialize the Jinja2 environment.
        
        Returns:
            Configured Jinja2 environment
        """
        # Convert Path objects to strings for Jinja
        template_paths = [str(d) for d in self.template_dirs.values() if d.exists()]
        
        if not template_paths:
            logger.warning("No template directories found, creating default")
            default_dir = Path(__file__).parent / "default_templates"
            default_dir.mkdir(parents=True, exist_ok=True)
            template_paths = [str(default_dir)]
            
        logger.info(f"Template search path: {template_paths}")
        
        env = Environment(
            loader=FileSystemLoader(template_paths),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        env.filters["to_json"] = lambda v: json.dumps(v)
        env.filters["to_yaml"] = self._to_yaml
        env.filters["basename"] = lambda p: os.path.basename(p) if p else ""
        env.filters["dirname"] = lambda p: os.path.dirname(p) if p else ""
        
        return env
    
    def _to_yaml(self, value: Any) -> str:
        """
        Convert value to YAML format.
        
        Args:
            value: Value to convert
            
        Returns:
            YAML string representation
        """
        try:
            import yaml
            return yaml.dump(value, default_flow_style=False)
        except ImportError:
            logger.warning("PyYAML not available, using JSON format")
            return json.dumps(value, indent=2)

    def _load_templates(self) -> None:
        """Load all templates into the cache with clear categorization."""
        # Reset cache
        self.templates_cache = {}
        
        # Track loaded templates with their source
        template_sources = {}
        
        # Process directories in precedence order
        for category in self.precedence_order:
            if category not in self.template_dirs:
                continue
                
            template_dir = self.template_dirs[category]
            if not template_dir.exists():
                continue
                
            logger.debug(f"Loading templates from {template_dir} (category: {category})")
            
            for file_path in template_dir.glob("**/*.j2"):
                try:
                    rel_path = file_path.relative_to(template_dir)
                    template_key = str(rel_path).replace("\\", "/").replace(".j2", "")
                    
                    # Read template content
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Store template in cache, potentially overriding lower precedence templates
                    self.templates_cache[template_key] = content
                    
                    # Track where this template came from
                    template_sources[template_key] = category
                    
                    logger.debug(f"Loaded template: {template_key} from {category}")
                except Exception as e:
                    logger.error(f"Error loading template {file_path}: {e}")
        
        # Log summary of templates by category
        template_counts = {}
        for template_key, source in template_sources.items():
            template_counts[source] = template_counts.get(source, 0) + 1
            
        for category, count in template_counts.items():
            logger.info(f"Loaded {count} templates from {category} directory")
            
        # Set up fallback templates if none found
        if not self.templates_cache:
            logger.warning("No templates found, creating default templates")
            self._create_default_templates()
            
        logger.info(f"Template loading completed. Total templates: {len(self.templates_cache)}")

    def _create_default_templates(self) -> None:
        """Create default templates if none exist."""
        default_dir = self.template_dirs.get("default")
        if not default_dir:
            default_dir = Path(__file__).parent / "default_templates"
            default_dir.mkdir(parents=True, exist_ok=True)
            self.template_dirs["default"] = default_dir
        
        default_templates = {
            "install/default.sh.j2": """#!/usr/bin/env bash
set -e
echo "Installing {{ target_name }}"
echo "CHANGE:PACKAGE_INSTALLED:{{ target_name }}"
# Default installation script
# Replace with actual commands for your integration
""",
            "uninstall/default.sh.j2": """#!/usr/bin/env bash
set -e
echo "Uninstalling {{ target_name }}"
echo "CHANGE:PACKAGE_REMOVED:{{ target_name }}"
# Default uninstallation script
# Replace with actual commands for your integration
""",
            "verify/default.sh.j2": """#!/usr/bin/env bash
set -e
echo "Verifying {{ target_name }}"
# Default verification script
# Replace with actual commands for your integration
"""
        }
        
        for template_path, content in default_templates.items():
            full_path = default_dir / template_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.templates_cache[template_path.replace(".j2", "")] = content
            
        logger.info(f"Created default templates in {default_dir}")

    def get_template(self, template_key: str) -> Optional[str]:
        """
        Get a template by key with improved resolution logic.
        
        Args:
            template_key: Template identifier (e.g. "install/integration_name")
            
        Returns:
            Template content or None if not found
        """
        # Step 1: Check for exact match
        if template_key in self.templates_cache:
            logger.debug(f"Found exact template match for: {template_key}")
            return self.templates_cache[template_key]
        
        # Step 2: Try with different extensions
        for ext in [".sh", ".ps1", ".py"]:
            if template_key + ext in self.templates_cache:
                template_with_ext = template_key + ext
                logger.debug(f"Found template with extension: {template_with_ext}")
                return self.templates_cache[template_with_ext]
        
        # Step 3: Try to find a default template for this action
        if "/" in template_key:
            # Extract action and integration from template key
            parts = template_key.split("/")
            action = parts[0]
            
            # Try action/default.sh
            default_key = f"{action}/default.sh"
            if default_key in self.templates_cache:
                logger.info(f"Using default template for {template_key}: {default_key}")
                return self.templates_cache[default_key]
            
            # Try action/default.ps1 for Windows
            default_ps_key = f"{action}/default.ps1"
            if default_ps_key in self.templates_cache:
                logger.info(f"Using default PowerShell template for {template_key}: {default_ps_key}")
                return self.templates_cache[default_ps_key]
        
        # Log clear message about template resolution failure
        logger.warning(f"Template not found: {template_key} (tried extensions and defaults)")
        return None

    @handle_errors("Template rendering failed")
    def render_template(
        self, 
        template_key: str, 
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Render a template with context.
        
        Args:
            template_key: Template identifier
            context: Template context data
            
        Returns:
            Rendered template or None if error
        """
        template_str = self.get_template(template_key)
        if not template_str:
            error_msg = f"Template not found: {template_key}"
            logger.error(error_msg)
            raise TemplateError(error_msg)
            
        try:
            # Add standard context variables for all templates
            full_context = {
                "env": os.environ,
                "now": datetime.datetime.now(),
                **context
            }
            
            template = self.template_env.from_string(template_str)
            return template.render(**full_context)
        except jinja2.exceptions.TemplateError as e:
            error_msg = f"Template rendering error for {template_key}: {e}"
            logger.error(error_msg)
            raise TemplateError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error rendering {template_key}: {e}"
            logger.error(error_msg)
            raise TemplateError(error_msg) from e

    @handle_errors("Template string rendering failed")
    def render_string_template(
        self, 
        template_content: str, 
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Render a template string with context.
        
        Args:
            template_content: Raw template content
            context: Template context data
            
        Returns:
            Rendered template or None if error
        """
        try:
            # Add standard context variables for all templates
            full_context = {
                "env": os.environ,
                "now": datetime.datetime.now(),
                **context
            }
            
            template = self.template_env.from_string(template_content)
            return template.render(**full_context)
        except Exception as e:
            error_msg = f"Template rendering error: {e}"
            logger.error(error_msg)
            raise TemplateError(error_msg) from e

    def reload_templates(self) -> None:
        """Reload all templates from disk."""
        self._load_templates()
        logger.info("Templates reloaded")

    def resolve_template_path(self, integration_type: str, action: str, target_name: Optional[str] = None) -> str:
        """
        Resolve a template path with clear precedence rules.
        
        Args:
            integration_type: Type of integration (e.g., "custom", "infra_agent")
            action: Action to perform (e.g., "install", "verify", "uninstall")
            target_name: Optional target name for more specific templates
            
        Returns:
            Template key to use
        """
        # Define resolution order from most specific to least specific:
        # 1. action/integration_type/target_name
        # 2. action/integration_type/default
        # 3. action/integration_type
        # 4. action/default
        
        template_paths = []
        
        if target_name:
            # Most specific: action/integration_type/target_name
            template_paths.append(f"{action}/{integration_type}/{target_name}")
            
        # Integration specific: action/integration_type
        template_paths.append(f"{action}/{integration_type}")
        
        # Integration type's default: action/integration_type/default
        template_paths.append(f"{action}/{integration_type}/default")
        
        # Generic action default: action/default
        template_paths.append(f"{action}/default")
        
        # Try each path in order
        for path in template_paths:
            if self.get_template(path):
                logger.debug(f"Resolved template: {path}")
                return path
                
        # If no template found, return the default path (it will return None when used)
        return f"{action}/default"

    def list_available_templates(self) -> Dict[str, List[str]]:
        """
        List all available templates by category.
        
        Returns:
            Dictionary of template categories and their templates
        """
        categories: Dict[str, List[str]] = {}
        
        for template_key in sorted(self.templates_cache.keys()):
            # Extract category from template key
            parts = template_key.split("/")
            if len(parts) > 1:
                category = parts[0]
                if category not in categories:
                    categories[category] = []
                categories[category].append(template_key)
            else:
                if "other" not in categories:
                    categories["other"] = []
                categories["other"].append(template_key)
                
        return categories
    
    def get_template_documentation(self, template_key: str) -> Dict[str, Any]:
        """
        Extract documentation from a template.
        
        Args:
            template_key: Template identifier
            
        Returns:
            Dictionary with template documentation
        """
        template_str = self.get_template(template_key)
        if not template_str:
            return {"error": f"Template not found: {template_key}"}
            
        # Extract header comments
        lines = template_str.split("\n")
        header_comments = []
        for line in lines:
            line = line.strip()
            # Skip empty lines at the beginning
            if not line and not header_comments:
                continue
            # Extract comment
            if line.startswith("#") or line.startswith("//") or line.startswith("<!--"):
                header_comments.append(line)
            else:
                # Stop at first non-comment line
                break
                
        # Extract parameters from Jinja2 template
        import re
        params = []
        param_pattern = r"{{\s*([a-zA-Z0-9_]+)\s*}}"
        for match in re.finditer(param_pattern, template_str):
            param = match.group(1)
            if param not in params and param not in ["env", "now"]:
                params.append(param)
                
        return {
            "template_key": template_key,
            "description": "\n".join(header_comments),
            "parameters": params
        }
