"""
Template management for script generation with consistent search and loading.
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import json
import jinja2
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape

from ..config.configuration import WorkflowConfiguration

logger = logging.getLogger(__name__)

class TemplateManager:
    """
    Manages template loading, resolution, and rendering.
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
        self._load_templates()

    def _get_template_dirs(self) -> List[Path]:
        """
        Get all template directories in order of precedence.
        
        Returns:
            List of template directory paths
        """
        dirs = []
        
        # Custom templates have highest precedence
        if self.config.custom_template_dir and self.config.custom_template_dir.exists():
            dirs.append(self.config.custom_template_dir)
            
        # Then project templates
        if self.config.template_dir and self.config.template_dir.exists():
            dirs.append(self.config.template_dir)
            
        # Common templates
        common_templates = self.config.template_dir / "common"
        if common_templates.exists():
            dirs.append(common_templates)
            
        # Default templates are last
        default_templates = Path(__file__).parent / "default_templates"
        if default_templates.exists():
            dirs.append(default_templates)
            
        # Ensure we have at least one template directory
        if not dirs:
            default_templates.mkdir(parents=True, exist_ok=True)
            dirs.append(default_templates)
            logger.warning(f"Created default template directory: {default_templates}")
            
        return dirs

    def _initialize_environment(self) -> Environment:
        """
        Initialize the Jinja2 environment.
        
        Returns:
            Configured Jinja2 environment
        """
        # Convert Path objects to strings for Jinja
        template_paths = [str(d) for d in self.template_dirs if d.exists()]
        
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
        
        return env

    def _load_templates(self) -> None:
        """Load all templates into the cache."""
        for template_dir in self.template_dirs:
            if not template_dir.exists():
                continue
                
            logger.debug(f"Loading templates from {template_dir}")
            
            for file_path in template_dir.glob("**/*.j2"):
                try:
                    rel_path = file_path.relative_to(template_dir)
                    template_key = str(rel_path).replace("\\", "/").replace(".j2", "")
                    with open(file_path, "r", encoding="utf-8") as f:
                        self.templates_cache[template_key] = f.read()
                    logger.debug(f"Loaded template: {template_key}")
                except Exception as e:
                    logger.error(f"Error loading template {file_path}: {e}")
                    
        # Set up some fallback templates if none found
        if not self.templates_cache:
            self._create_default_templates()

    def _create_default_templates(self) -> None:
        """Create default templates if none exist."""
        default_dir = Path(__file__).parent / "default_templates"
        default_dir.mkdir(parents=True, exist_ok=True)
        
        default_templates = {
            "install/default.sh.j2": """#!/usr/bin/env bash
set -e
echo "Installing {{ target_name }}"
# Default installation script
# Replace with actual commands for your integration
""",
            "uninstall/default.sh.j2": """#!/usr/bin/env bash
set -e
echo "Uninstalling {{ target_name }}"
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
        Get a template by key.
        
        Args:
            template_key: Template identifier
            
        Returns:
            Template content or None if not found
        """
        # Check for exact match
        if template_key in self.templates_cache:
            return self.templates_cache[template_key]
            
        # Try with different extensions
        for ext in [".sh", ".ps1", ".py", ""]:
            if template_key + ext in self.templates_cache:
                return self.templates_cache[template_key + ext]
                
        # Try to find a default template for this action
        if "/" in template_key:
            action = template_key.split("/")[0]
            default_key = f"{action}/default.sh"
            if default_key in self.templates_cache:
                logger.info(f"Using default template for {template_key}: {default_key}")
                return self.templates_cache[default_key]
                
        logger.warning(f"Template not found: {template_key}")
        return None

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
            logger.error(f"Template not found: {template_key}")
            return None
            
        try:
            template = self.template_env.from_string(template_str)
            return template.render(**context)
        except jinja2.exceptions.TemplateError as e:
            logger.error(f"Template rendering error for {template_key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error rendering {template_key}: {e}")
            return None

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
            template = self.template_env.from_string(template_content)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Template rendering error: {e}")
            return None

    def reload_templates(self) -> None:
        """Reload all templates from disk."""
        self.templates_cache.clear()
        self._load_templates()
        logger.info("Templates reloaded")

    def list_available_templates(self) -> Dict[str, List[str]]:
        """
        List all available templates by category.
        
        Returns:
            Dictionary of template categories and their templates
        """
        categories: Dict[str, List[str]] = {}
        
        for template_key in sorted(self.templates_cache.keys()):
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
