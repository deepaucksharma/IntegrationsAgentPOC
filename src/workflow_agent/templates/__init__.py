"""
Template management module for script generation.
"""
# Import the adapter but expose it as TemplateManager for backward compatibility
from .adapter import TemplateSystemAdapter as TemplateManager
from .pipeline import TemplatePipeline, create_default_pipeline
from .registry.template_registry import TemplateRegistry

__all__ = ['TemplateManager', 'TemplatePipeline', 'create_default_pipeline', 'TemplateRegistry']
