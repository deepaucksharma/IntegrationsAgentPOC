"""
Conditional template renderer for dynamic template selection based on context.
"""
import logging
import re
import os
from typing import Dict, Any, List, Optional, Tuple, Union
import json

from .manager import TemplateManager
from .validator import TemplateValidator

logger = logging.getLogger(__name__)

class ConditionalTemplateRenderer:
    """
    Conditional template renderer that selects templates based on context.
    Supports template inheritance, composition, and conditional blocks.
    """
    
    def __init__(self, template_manager: TemplateManager):
        """
        Initialize conditional template renderer.
        
        Args:
            template_manager: Template manager to use
        """
        self.template_manager = template_manager
        self.validator = TemplateValidator(template_manager)
        
    async def render_template(self, 
                             action: str, 
                             integration_type: str, 
                             context: Dict[str, Any],
                             validate_parameters: bool = True) -> Dict[str, Any]:
        """
        Render a template for the given action and integration type.
        
        Args:
            action: Action to perform (install, verify, remove)
            integration_type: Type of integration
            context: Template rendering context
            validate_parameters: Whether to validate parameters
            
        Returns:
            Dictionary with rendered template and metadata
        """
        # Get system context
        system_context = context.get("system_context", {})
        
        # Find suitable templates
        templates = await self.template_manager.find_templates_for_integration(
            integration_type, action, system_context
        )
        
        if not templates:
            logger.warning(f"No templates found for {integration_type}/{action}")
            return {
                "success": False,
                "error": f"No templates found for {integration_type}/{action}",
                "templates_searched": f"{integration_type}/{action}"
            }
            
        # Create template candidates with scores
        candidates = []
        for template in templates:
            path = template["path"]
            
            # Extract conditions from metadata
            conditions = {}
            if "metadata" in template and template["metadata"]:
                metadata = template["metadata"]
                
                # Platform condition
                if "platform" in metadata:
                    conditions["system_context.platform"] = metadata["platform"]
                    
                # Tags as conditions
                if "tags" in metadata and metadata["tags"]:
                    for tag in metadata["tags"]:
                        if "=" in tag:
                            key, value = tag.split("=", 1)
                            conditions[key] = value
                            
            candidates.append({
                "path": path,
                "conditions": conditions,
                "score": template.get("score", 0)
            })
        
        # Sort candidates by score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # Select best template
        template_path = await self.template_manager.select_best_template(candidates, context)
        
        if not template_path:
            logger.warning(f"No suitable template found for {integration_type}/{action}")
            return {
                "success": False,
                "error": f"No suitable template found for {integration_type}/{action}",
                "candidates": [c["path"] for c in candidates]
            }
            
        # Validate parameters if requested
        if validate_parameters:
            validation = await self.validator.validate_parameters(template_path, context)
            if not validation["valid"]:
                logger.warning(f"Parameter validation failed for {template_path}: {validation}")
                return {
                    "success": False,
                    "error": "Parameter validation failed",
                    "validation": validation,
                    "template_path": template_path
                }
                
        # Render the template
        try:
            rendered = await self.template_manager.render_template(template_path, context)
            
            return {
                "success": True,
                "rendered": rendered,
                "template_path": template_path,
                "selected_from": len(candidates)
            }
        except Exception as e:
            logger.error(f"Error rendering template {template_path}: {e}")
            return {
                "success": False,
                "error": f"Error rendering template: {str(e)}",
                "template_path": template_path
            }
            
    async def get_template_requirements(self, 
                                       action: str, 
                                       integration_type: str, 
                                       system_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get template parameter requirements for the given action and integration type.
        
        Args:
            action: Action to perform
            integration_type: Type of integration
            system_context: System context
            
        Returns:
            Dictionary with required parameters and template info
        """
        # Find suitable templates
        templates = await self.template_manager.find_templates_for_integration(
            integration_type, action, system_context
        )
        
        if not templates:
            logger.warning(f"No templates found for {integration_type}/{action}")
            return {
                "success": False,
                "error": f"No templates found for {integration_type}/{action}",
                "templates_searched": f"{integration_type}/{action}"
            }
            
        # Create template candidates with scores
        candidates = []
        for template in templates:
            path = template["path"]
            
            # Extract conditions from metadata
            conditions = {}
            if "metadata" in template and template["metadata"]:
                metadata = template["metadata"]
                
                # Platform condition
                if "platform" in metadata:
                    conditions["system_context.platform"] = metadata["platform"]
                    
                # Tags as conditions
                if "tags" in metadata and metadata["tags"]:
                    for tag in metadata["tags"]:
                        if "=" in tag:
                            key, value = tag.split("=", 1)
                            conditions[key] = value
                            
            candidates.append({
                "path": path,
                "conditions": conditions,
                "score": template.get("score", 0),
                "metadata": template.get("metadata", {})
            })
        
        # Sort candidates by score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # Get top candidate
        if not candidates:
            return {
                "success": False,
                "error": "No candidate templates found"
            }
            
        top_candidate = candidates[0]
        template_path = top_candidate["path"]
        
        # Get template requirements
        required_params = self.template_manager.get_template_required_params(template_path)
        
        # Filter out special variables
        required_params = [p for p in required_params if not p.startswith(('_', 'range', 'dict', 'lipsum', 'cycler', 'loop'))]
        
        # Get parameter information from template metadata
        param_info = {}
        metadata = top_candidate.get("metadata", {})
        
        return {
            "success": True,
            "template_path": template_path,
            "required_params": required_params,
            "metadata": metadata,
            "candidates": [c["path"] for c in candidates]
        }
        
    async def render_nested_template(self, 
                                    template_path: str, 
                                    context: Dict[str, Any],
                                    include_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Render a template with nested templates and includes.
        
        Args:
            template_path: Path to primary template
            context: Template rendering context
            include_paths: Additional paths to include in rendering
            
        Returns:
            Dictionary with rendered template and metadata
        """
        # Convert include paths to context for include_file function
        if include_paths:
            if "includes" not in context:
                context["includes"] = {}
                
            # Add include paths to context
            for i, path in enumerate(include_paths):
                context["includes"][f"path_{i}"] = path
                
        # Validate parameters
        validation = await self.validator.validate_parameters(template_path, context)
        if not validation["valid"]:
            logger.warning(f"Parameter validation failed for {template_path}: {validation}")
            return {
                "success": False,
                "error": "Parameter validation failed",
                "validation": validation,
                "template_path": template_path
            }
            
        # Render the template
        try:
            rendered = await self.template_manager.render_template(template_path, context)
            
            return {
                "success": True,
                "rendered": rendered,
                "template_path": template_path
            }
        except Exception as e:
            logger.error(f"Error rendering template {template_path}: {e}")
            return {
                "success": False,
                "error": f"Error rendering template: {str(e)}",
                "template_path": template_path
            }
            
    async def render_conditional_blocks(self, content: str, context: Dict[str, Any]) -> str:
        """
        Render conditional blocks in content string.
        
        Args:
            content: String with conditional blocks
            context: Rendering context
            
        Returns:
            Rendered content with conditional blocks processed
        """
        # Define conditional block regex
        # Format: <!-- BEGIN:IF condition --> content <!-- END:IF -->
        block_pattern = r'<!-- BEGIN:IF (.*?) -->(.*?)<!-- END:IF -->'
        
        # Find all conditional blocks
        matches = re.finditer(block_pattern, content, re.DOTALL)
        
        # Process each block
        result = content
        for match in matches:
            condition = match.group(1).strip()
            block_content = match.group(2)
            
            # Evaluate condition
            try:
                # Parse condition
                condition_parts = re.split(r'\s+(AND|OR)\s+', condition)
                if len(condition_parts) == 1:
                    # Single condition
                    condition_met = self._evaluate_simple_condition(condition_parts[0], context)
                else:
                    # Multiple conditions
                    conditions = []
                    operators = []
                    
                    for i, part in enumerate(condition_parts):
                        if i % 2 == 0:
                            # Condition
                            conditions.append(self._evaluate_simple_condition(part, context))
                        else:
                            # Operator
                            operators.append(part)
                            
                    # Evaluate the combined condition
                    condition_met = conditions[0]
                    for i, op in enumerate(operators):
                        if op == "AND":
                            condition_met = condition_met and conditions[i + 1]
                        elif op == "OR":
                            condition_met = condition_met or conditions[i + 1]
                
                # Replace block with content if condition is met, otherwise empty string
                if condition_met:
                    result = result.replace(match.group(0), block_content)
                else:
                    result = result.replace(match.group(0), "")
                    
            except Exception as e:
                logger.warning(f"Error evaluating condition '{condition}': {e}")
                # Replace with original content in case of error
                result = result.replace(match.group(0), block_content)
                
        return result
        
    def _evaluate_simple_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        Evaluate a simple condition against context.
        
        Args:
            condition: Condition string
            context: Context to evaluate against
            
        Returns:
            True if condition is met, False otherwise
        """
        # Equality condition
        if "==" in condition:
            left, right = [s.strip() for s in condition.split("==", 1)]
            left_value = self._get_value_from_context(left, context)
            right_value = self._get_value_from_context(right, context)
            return left_value == right_value
            
        # Inequality condition
        elif "!=" in condition:
            left, right = [s.strip() for s in condition.split("!=", 1)]
            left_value = self._get_value_from_context(left, context)
            right_value = self._get_value_from_context(right, context)
            return left_value != right_value
            
        # Greater than
        elif ">" in condition:
            left, right = [s.strip() for s in condition.split(">", 1)]
            left_value = self._get_value_from_context(left, context)
            right_value = self._get_value_from_context(right, context)
            return left_value > right_value
            
        # Less than
        elif "<" in condition:
            left, right = [s.strip() for s in condition.split("<", 1)]
            left_value = self._get_value_from_context(left, context)
            right_value = self._get_value_from_context(right, context)
            return left_value < right_value
            
        # Greater than or equal
        elif ">=" in condition:
            left, right = [s.strip() for s in condition.split(">=", 1)]
            left_value = self._get_value_from_context(left, context)
            right_value = self._get_value_from_context(right, context)
            return left_value >= right_value
            
        # Less than or equal
        elif "<=" in condition:
            left, right = [s.strip() for s in condition.split("<=", 1)]
            left_value = self._get_value_from_context(left, context)
            right_value = self._get_value_from_context(right, context)
            return left_value <= right_value
            
        # Contains
        elif "contains" in condition:
            left, right = [s.strip() for s in condition.split("contains", 1)]
            left_value = self._get_value_from_context(left, context)
            right_value = self._get_value_from_context(right, context)
            return right_value in left_value
            
        # Not contains
        elif "not contains" in condition:
            left, right = [s.strip() for s in condition.split("not contains", 1)]
            left_value = self._get_value_from_context(left, context)
            right_value = self._get_value_from_context(right, context)
            return right_value not in left_value
            
        # Boolean value
        elif condition.lower() in ("true", "false"):
            return condition.lower() == "true"
            
        # Variable existence
        else:
            return bool(self._get_value_from_context(condition, context))
            
    def _get_value_from_context(self, key: str, context: Dict[str, Any]) -> Any:
        """
        Get a value from context by key.
        
        Args:
            key: Key to lookup
            context: Context dictionary
            
        Returns:
            Value from context
        """
        # Handle quoted strings
        if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
            return key[1:-1]
            
        # Handle numeric literals
        if key.isdigit():
            return int(key)
        if key.replace('.', '', 1).isdigit() and key.count('.') == 1:
            return float(key)
            
        # Handle special values
        if key.lower() == "true":
            return True
        if key.lower() == "false":
            return False
        if key.lower() == "null" or key.lower() == "none":
            return None
            
        # Nested key lookup
        if '.' in key:
            parts = key.split('.')
            value = context
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return None
            return value
            
        # Simple key lookup
        return context.get(key, None)