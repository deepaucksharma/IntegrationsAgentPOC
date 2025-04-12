"""
Template utilities for rendering templates both in the framework and standalone examples.
Provides a simplified interface for template rendering operations.
"""
import os
import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template

logger = logging.getLogger(__name__)

class TemplateUtils:
    """
    Utility class for template operations that can be used by both
    framework and example scripts.
    """
    
    def __init__(self, template_dirs: Optional[List[Union[str, Path]]] = None):
        """
        Initialize template utilities.
        
        Args:
            template_dirs: List of template directories to search
        """
        self.template_dirs = self._normalize_template_dirs(template_dirs)
        self.env = Environment(loader=FileSystemLoader(self.template_dirs))
        logger.debug(f"Template utils initialized with directories: {self.template_dirs}")
    
    def _normalize_template_dirs(self, template_dirs: Optional[List[Union[str, Path]]]) -> List[str]:
        """
        Normalize template directories to strings and verify they exist.
        
        Args:
            template_dirs: List of template directories
            
        Returns:
            List of normalized template directory paths
        """
        if not template_dirs:
            # Default template directories
            template_dirs = [
                Path.cwd() / 'templates',
                Path(__file__).parent.parent.parent.parent / 'templates'
            ]
            
            # Check if we're in an installed package
            package_template_dir = Path(__file__).parent / 'templates_data'
            if package_template_dir.exists():
                template_dirs.append(package_template_dir)
                
        # Convert to strings and filter only existing directories
        normalized_dirs = []
        for dir_path in template_dirs:
            str_path = str(dir_path)
            if os.path.isdir(str_path):
                normalized_dirs.append(str_path)
            else:
                logger.warning(f"Template directory not found: {str_path}")
                
        if not normalized_dirs:
            logger.warning("No valid template directories found, using current directory")
            normalized_dirs = [str(Path.cwd())]
            
        return normalized_dirs

    def render_template(self, template_path: str, context: Dict[str, Any]) -> str:
        """
        Render a template with the given context.
        
        Args:
            template_path: Path to the template relative to template directories
            context: Context variables for template rendering
            
        Returns:
            Rendered template content
            
        Raises:
            ValueError: If template is not found
        """
        try:
            template = self.env.get_template(template_path)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Error rendering template {template_path}: {e}")
            raise ValueError(f"Failed to render template {template_path}: {e}")
    
    def render_string_template(self, template_string: str, context: Dict[str, Any]) -> str:
        """
        Render a template string with the given context.
        
        Args:
            template_string: Jinja2 template string
            context: Context variables for template rendering
            
        Returns:
            Rendered template content
            
        Raises:
            ValueError: If template rendering fails
        """
        try:
            template = Template(template_string)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Error rendering template string: {e}")
            raise ValueError(f"Failed to render template string: {e}")
    
    def find_template(self, template_name: str, search_dirs: Optional[List[str]] = None) -> Optional[str]:
        """
        Find a template in the available template directories.
        
        Args:
            template_name: Template name to find
            search_dirs: Optional additional directories to search
            
        Returns:
            Full path to template if found, None otherwise
        """
        dirs_to_search = list(self.template_dirs)
        if search_dirs:
            dirs_to_search.extend(search_dirs)
            
        for dir_path in dirs_to_search:
            full_path = os.path.join(dir_path, template_name)
            if os.path.exists(full_path):
                return full_path
                
            # Also check with .j2 extension if not already specified
            if not template_name.endswith('.j2'):
                j2_path = full_path + '.j2'
                if os.path.exists(j2_path):
                    return j2_path
                    
        return None

# Singleton instance for easy access
template_utils = TemplateUtils()

# Shortcut functions
def render_template(template_path: str, context: Dict[str, Any]) -> str:
    """
    Render a template with the given context using the singleton instance.
    
    Args:
        template_path: Path to the template relative to template directories
        context: Context variables for template rendering
        
    Returns:
        Rendered template content
    """
    return template_utils.render_template(template_path, context)

def render_string_template(template_string: str, context: Dict[str, Any]) -> str:
    """
    Render a template string with the given context using the singleton instance.
    
    Args:
        template_string: Jinja2 template string
        context: Context variables for template rendering
        
    Returns:
        Rendered template content
    """
    return template_utils.render_string_template(template_string, context)

def find_template(template_name: str, search_dirs: Optional[List[str]] = None) -> Optional[str]:
    """
    Find a template in the available template directories using the singleton instance.
    
    Args:
        template_name: Template name to find
        search_dirs: Optional additional directories to search
        
    Returns:
        Full path to template if found, None otherwise
    """
    return template_utils.find_template(template_name, search_dirs)
