"""
Template pipeline for processing templates through multiple stages.
"""
import logging
import os
import re
from typing import Dict, Any, Optional, List, Union, Callable, Protocol, runtime_checkable
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime
import json

from pydantic import BaseModel

from ..error.exceptions import TemplateError
from ..error.handler import ErrorHandler, handle_safely_async

logger = logging.getLogger(__name__)

class ValidationResult(BaseModel):
    """Result of template validation."""
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []

@runtime_checkable
class TemplateResolver(Protocol):
    """Protocol for template resolution."""
    
    async def resolve(self, template_key: str) -> Optional[str]:
        """
        Resolve a template key to content.
        
        Args:
            template_key: Template key
            
        Returns:
            Template content or None if not resolved
        """
        ...

@runtime_checkable
class TemplateRenderer(Protocol):
    """Protocol for template rendering."""
    
    async def render(self, template_content: str, context: Dict[str, Any]) -> str:
        """
        Render a template with context.
        
        Args:
            template_content: Template content
            context: Rendering context
            
        Returns:
            Rendered content
        """
        ...

@runtime_checkable
class TemplateValidator(Protocol):
    """Protocol for template validation."""
    
    async def validate(self, template_content: str) -> ValidationResult:
        """
        Validate template content.
        
        Args:
            template_content: Template content
            
        Returns:
            Validation result
        """
        ...

class FileSystemResolver:
    """Resolves templates from the file system."""
    
    def __init__(self, search_paths: List[str]):
        """
        Initialize the resolver.
        
        Args:
            search_paths: List of directories to search
        """
        self.search_paths = search_paths
        
    async def resolve(self, template_key: str) -> Optional[str]:
        """
        Resolve a template from the file system.
        
        Args:
            template_key: Template key
            
        Returns:
            Template content or None if not found
        """
        # Try exact key
        for path in self.search_paths:
            template_path = os.path.join(path, template_key)
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    return f.read()
                    
            # Try with .j2 extension
            template_path_j2 = template_path + '.j2'
            if os.path.exists(template_path_j2):
                with open(template_path_j2, 'r', encoding='utf-8') as f:
                    return f.read()
                    
        return None

class RegistryResolver:
    """Resolves templates from a template registry."""
    
    def __init__(self, registry):
        """
        Initialize the resolver.
        
        Args:
            registry: Template registry
        """
        self.registry = registry
        
    async def resolve(self, template_key: str) -> Optional[str]:
        """
        Resolve a template from the registry.
        
        Args:
            template_key: Template key
            
        Returns:
            Template content or None if not found
        """
        # Use registry to get template
        return self.registry.get_template_content(template_key)

class CacheResolver:
    """Resolves templates from an in-memory cache."""
    
    def __init__(self):
        """Initialize the resolver."""
        self.cache: Dict[str, str] = {}
        
    def add_template(self, template_key: str, content: str) -> None:
        """
        Add a template to the cache.
        
        Args:
            template_key: Template key
            content: Template content
        """
        self.cache[template_key] = content
        
    async def resolve(self, template_key: str) -> Optional[str]:
        """
        Resolve a template from the cache.
        
        Args:
            template_key: Template key
            
        Returns:
            Template content or None if not found
        """
        return self.cache.get(template_key)

class Jinja2Renderer:
    """Renders templates using Jinja2."""
    
    def __init__(self):
        """Initialize the renderer."""
        try:
            import jinja2
            self.env = jinja2.Environment(
                keep_trailing_newline=True,
                trim_blocks=True,
                lstrip_blocks=True
            )
            
            # Add custom filters
            self.env.filters["to_json"] = lambda v: json.dumps(v)
            self.env.filters["basename"] = lambda p: os.path.basename(p) if p else ""
            self.env.filters["dirname"] = lambda p: os.path.dirname(p) if p else ""
            
        except ImportError:
            logger.error("Jinja2 not available")
            raise TemplateError("Jinja2 not available")
            
    async def render(self, template_content: str, context: Dict[str, Any]) -> str:
        """
        Render a template with context using Jinja2.
        
        Args:
            template_content: Template content
            context: Rendering context
            
        Returns:
            Rendered content
        """
        try:
            # Add standard context variables
            full_context = {
                "env": os.environ,
                "now": datetime.now(),
                **context
            }
            
            template = self.env.from_string(template_content)
            return template.render(**full_context)
            
        except Exception as e:
            logger.error(f"Template rendering error: {e}")
            raise TemplateError(f"Template rendering error: {e}")

class SyntaxValidator:
    """Validates template syntax."""
    
    def __init__(self):
        """Initialize the validator."""
        try:
            import jinja2
            self.env = jinja2.Environment()
        except ImportError:
            logger.error("Jinja2 not available")
            raise TemplateError("Jinja2 not available")
            
    async def validate(self, template_content: str) -> ValidationResult:
        """
        Validate template syntax.
        
        Args:
            template_content: Template content
            
        Returns:
            Validation result
        """
        errors = []
        warnings = []
        
        # Check for syntax errors
        try:
            self.env.parse(template_content)
        except Exception as e:
            errors.append(f"Syntax error: {e}")
            
        # Check for common mistakes
        if "{{" in template_content and "}}" not in template_content:
            warnings.append("Possible unclosed variable tag: {{ without }}")
            
        if "{%" in template_content and "%}" not in template_content:
            warnings.append("Possible unclosed statement tag: {% without %}")
            
        # More validation can be added here
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

class ScriptValidator:
    """Validates script templates."""
    
    async def validate(self, template_content: str) -> ValidationResult:
        """
        Validate script template.
        
        Args:
            template_content: Template content
            
        Returns:
            Validation result
        """
        errors = []
        warnings = []
        
        # Check for shebang in shell scripts
        if "#!/" not in template_content and \
           (template_content.strip().endswith(".sh") or 
            "bash" in template_content.lower() or 
            "sh " in template_content.lower()):
            warnings.append("Shell script should start with a shebang line (e.g., #!/bin/bash)")
            
        # Check for PowerShell script headers
        if template_content.strip().endswith(".ps1") and "<#" not in template_content:
            warnings.append("PowerShell script should have a comment block header")
            
        # Check for error handling
        if "set -e" not in template_content and "#!/bin/bash" in template_content:
            warnings.append("Bash script should include 'set -e' for error handling")
            
        # More script-specific validation can be added here
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

class TemplatePipeline:
    """
    Pipeline for processing templates through multiple stages:
    resolution, rendering, and validation.
    """
    
    def __init__(
        self,
        resolvers: Optional[List[TemplateResolver]] = None,
        renderers: Optional[List[TemplateRenderer]] = None,
        validators: Optional[List[TemplateValidator]] = None
    ):
        """
        Initialize the template pipeline.
        
        Args:
            resolvers: List of template resolvers
            renderers: List of template renderers
            validators: List of template validators
        """
        self.resolvers = resolvers or []
        self.renderers = renderers or []
        self.validators = validators or []
        
    def add_resolver(self, resolver: TemplateResolver) -> None:
        """
        Add a template resolver to the pipeline.
        
        Args:
            resolver: Template resolver
        """
        self.resolvers.append(resolver)
        logger.debug(f"Added template resolver: {resolver.__class__.__name__}")
        
    def add_renderer(self, renderer: TemplateRenderer) -> None:
        """
        Add a template renderer to the pipeline.
        
        Args:
            renderer: Template renderer
        """
        self.renderers.append(renderer)
        logger.debug(f"Added template renderer: {renderer.__class__.__name__}")
        
    def add_validator(self, validator: TemplateValidator) -> None:
        """
        Add a template validator to the pipeline.
        
        Args:
            validator: Template validator
        """
        self.validators.append(validator)
        logger.debug(f"Added template validator: {validator.__class__.__name__}")
        
    async def process(
        self,
        template_key: str,
        context: Dict[str, Any],
        validate: bool = True
    ) -> str:
        """
        Process a template through the pipeline.
        
        Args:
            template_key: Template key
            context: Template context
            validate: Whether to validate the template
            
        Returns:
            Processed template content
            
        Raises:
            TemplateError: If template processing fails
        """
        # Resolution phase
        template_content = await self._resolve(template_key)
        if not template_content:
            raise TemplateError(f"Template not found: {template_key}")
            
        # Validation phase (pre-render)
        if validate:
            await self._validate(template_content)
            
        # Rendering phase
        rendered_content = await self._render(template_content, context)
        
        # Additional post-render validation could be added here
        
        return rendered_content
        
    async def _resolve(self, template_key: str) -> Optional[str]:
        """
        Resolve a template using all resolvers.
        
        Args:
            template_key: Template key
            
        Returns:
            Template content or None if not resolved
        """
        for resolver in self.resolvers:
            try:
                content = await resolver.resolve(template_key)
                if content:
                    logger.debug(f"Resolved template {template_key} using {resolver.__class__.__name__}")
                    return content
            except Exception as e:
                logger.warning(f"Error resolving template {template_key} with {resolver.__class__.__name__}: {e}")
                
        return None
        
    async def _render(self, template_content: str, context: Dict[str, Any]) -> str:
        """
        Render a template using all renderers.
        
        Args:
            template_content: Template content
            context: Template context
            
        Returns:
            Rendered content
            
        Raises:
            TemplateError: If rendering fails
        """
        content = template_content
        
        for renderer in self.renderers:
            try:
                content = await renderer.render(content, context)
            except Exception as e:
                logger.error(f"Error rendering template with {renderer.__class__.__name__}: {e}")
                raise TemplateError(f"Template rendering error: {e}")
                
        return content
        
    async def _validate(self, template_content: str) -> None:
        """
        Validate a template using all validators.
        
        Args:
            template_content: Template content
            
        Raises:
            TemplateError: If validation fails
        """
        all_errors = []
        all_warnings = []
        
        for validator in self.validators:
            try:
                result = await validator.validate(template_content)
                all_errors.extend(result.errors)
                all_warnings.extend(result.warnings)
            except Exception as e:
                logger.error(f"Error validating template with {validator.__class__.__name__}: {e}")
                all_errors.append(f"Validation error: {e}")
                
        # Log warnings
        for warning in all_warnings:
            logger.warning(f"Template warning: {warning}")
            
        # Raise error if any
        if all_errors:
            error_msg = "Template validation failed: " + "; ".join(all_errors)
            logger.error(error_msg)
            raise TemplateError(error_msg)

def create_default_pipeline(
    search_paths: Optional[List[str]] = None,
    registry = None
) -> TemplatePipeline:
    """
    Create a default template pipeline.
    
    Args:
        search_paths: List of directories to search
        registry: Optional template registry
        
    Returns:
        Configured template pipeline
    """
    pipeline = TemplatePipeline()
    
    # Add cache resolver first for fastest resolution
    cache_resolver = CacheResolver()
    pipeline.add_resolver(cache_resolver)
    
    # Add registry resolver if available
    if registry:
        registry_resolver = RegistryResolver(registry)
        pipeline.add_resolver(registry_resolver)
        
    # Add file system resolver
    if search_paths:
        fs_resolver = FileSystemResolver(search_paths)
        pipeline.add_resolver(fs_resolver)
        
    # Add Jinja2 renderer
    pipeline.add_renderer(Jinja2Renderer())
    
    # Add validators
    pipeline.add_validator(SyntaxValidator())
    pipeline.add_validator(ScriptValidator())
    
    return pipeline
