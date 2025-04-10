"""
Adapter for new template system that maintains compatibility with old TemplateManager.
"""
import logging
import os
import platform
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from ..config.configuration import WorkflowConfiguration
from ..error.exceptions import TemplateError
from ..error.handler import ErrorHandler, handle_safely
from .manager import TemplateManager
from .pipeline import TemplatePipeline, create_default_pipeline, Jinja2Renderer, CacheResolver, FileSystemResolver 
from .registry.template_registry import TemplateRegistry

logger = logging.getLogger(__name__)

class TemplateSystemAdapter(TemplateManager):
    """
    Adapter that wraps the new template system components but exposes the interface 
    of the old TemplateManager for backward compatibility.
    """
    
    def __init__(self, config: WorkflowConfiguration):
        """
        Initialize the template adapter with configuration.
        
        Args:
            config: WorkflowConfiguration with template paths
        """
        # Initialize the parent class to maintain compatibility
        super().__init__(config)
        
        # Set up the new template system components
        self._setup_new_template_system()
        
    def _setup_new_template_system(self) -> None:
        """Set up the new template system components."""
        try:
            # Set up template registry
            search_paths = [str(path) for path in self.template_dirs.values() if path.exists()]
            self.registry = TemplateRegistry(search_paths)
            self.registry.scan_templates()
            
            # Set up template pipeline
            self.pipeline = create_default_pipeline(search_paths, self.registry)
            
            # Add a cache resolver to the pipeline for better performance
            # that will cache templates from the old system
            self.cache_resolver = CacheResolver()
            self.pipeline.add_resolver(self.cache_resolver)
            
            # Migrate cache from old system to new system
            for template_key, content in self.templates_cache.items():
                self.cache_resolver.add_template(template_key, content)
                
            logger.info("New template system initialized and synchronized with old cache")
            
        except Exception as e:
            logger.error(f"Error setting up new template system: {e}")
            logger.warning("Continuing with legacy template system only")
            
    @handle_safely
    def render_template(
        self, 
        template_key: str, 
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Render a template with context, using the new system if available.
        
        Args:
            template_key: Template identifier
            context: Template context data
            
        Returns:
            Rendered template or None if error
        """
        # First, try using the new system if it's available
        if hasattr(self, 'pipeline'):
            try:
                import asyncio
                
                # The pipeline is async, so we need to run it in a loop
                loop = asyncio.new_event_loop()
                try:
                    rendered = loop.run_until_complete(
                        self.pipeline.process(template_key, context, validate=True)
                    )
                    return rendered
                finally:
                    loop.close()
                    
            except Exception as e:
                logger.debug(f"New template system failed for {template_key}: {e}")
                logger.debug("Falling back to legacy template system")
                # Fall back to the old system
        
        # Use the old system as fallback
        return super().render_template(template_key, context)
        
    @handle_safely
    def render_string_template(
        self, 
        template_content: str, 
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Render a template string with context, using the new system if available.
        
        Args:
            template_content: Raw template content
            context: Template context data
            
        Returns:
            Rendered template or None if error
        """
        # Try using the new system's renderer if available
        if hasattr(self, 'pipeline') and self.pipeline.renderers:
            try:
                renderer = next((r for r in self.pipeline.renderers if isinstance(r, Jinja2Renderer)), None)
                
                if renderer:
                    import asyncio
                    
                    # The renderer is async
                    loop = asyncio.new_event_loop()
                    try:
                        rendered = loop.run_until_complete(
                            renderer.render(template_content, context)
                        )
                        return rendered
                    finally:
                        loop.close()
                        
            except Exception as e:
                logger.debug(f"New template system renderer failed: {e}")
                logger.debug("Falling back to legacy template renderer")
                # Fall back to the old renderer
        
        # Use the old system as fallback
        return super().render_string_template(template_content, context)
        
    def reload_templates(self) -> None:
        """Reload all templates from disk using both old and new systems."""
        # Reload with the old system
        super().reload_templates()
        
        # Reload with the new system if available
        if hasattr(self, 'registry'):
            try:
                self.registry.scan_templates()
                logger.debug("Template registry reloaded")
                
                # Synchronize cache from old to new system
                self.cache_resolver = CacheResolver()
                for template_key, content in self.templates_cache.items():
                    self.cache_resolver.add_template(template_key, content)
                    
                # Add the cache resolver to the pipeline
                if hasattr(self, 'pipeline'):
                    # Remove existing cache resolver if any
                    self.pipeline.resolvers = [r for r in self.pipeline.resolvers if not isinstance(r, CacheResolver)]
                    # Add the new one
                    self.pipeline.add_resolver(self.cache_resolver)
                    
            except Exception as e:
                logger.error(f"Error reloading template registry: {e}")
                
    def get_template(self, template_key: str) -> Optional[str]:
        """
        Get a template by key with improved resolution logic, using both systems.
        
        Args:
            template_key: Template identifier (e.g. "install/integration_name")
            
        Returns:
            Template content or None if not found
        """
        # First try the old system which has all our custom resolution logic
        template_content = super().get_template(template_key)
        
        # If old system found it, return it
        if template_content is not None:
            return template_content
            
        # Otherwise, try the new system's registry
        if hasattr(self, 'registry'):
            try:
                registry_content = self.registry.get_template_content(template_key)
                if registry_content is not None:
                    # Cache it in the old system for future use
                    self.templates_cache[template_key] = registry_content
                    return registry_content
            except Exception as e:
                logger.debug(f"Error getting template from registry: {e}")
                
        # Not found in either system
        return None
