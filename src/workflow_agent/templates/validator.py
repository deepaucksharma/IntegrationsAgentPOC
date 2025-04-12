"""
Template validator for ensuring template correctness and parameter validation.
"""
import logging
import re
from typing import Dict, Any, List, Optional, Tuple, Union, Set
import json
import yaml

from jinja2 import Environment, TemplateSyntaxError, meta
from .manager import TemplateManager

logger = logging.getLogger(__name__)

class TemplateValidator:
    """
    Validates templates and their parameters for correctness and security.
    """
    
    def __init__(self, template_manager: Optional[TemplateManager] = None):
        """
        Initialize template validator.
        
        Args:
            template_manager: Optional template manager to use
        """
        self.template_manager = template_manager
        self.dangerous_patterns = [
            r'rm\s+-rf\s+[/~]',               # Dangerous rm commands
            r'sudo\s+rm',                      # sudo rm commands
            r'chmod\s+777',                    # chmod 777 (too permissive)
            r'find\s+.*\s+-delete',            # find with delete
            r'dd\s+.*\s+of=/dev/',             # dd to devices
            r';\s*rm\s',                       # rm after semicolon
            r'mkfs',                           # filesystem formatting
            r'wget.*\|\s*sh',                  # piping wget to shell
            r'curl.*\|\s*sh',                  # piping curl to shell
            r'eval.*\$\(',                     # eval of command substitution
            r'>\s*/etc/passwd',                # overwriting passwd
            r'>\s*/etc/shadow',                # overwriting shadow
            r'mv\s+.*\s+/etc/',                # moving to /etc
            r'\|\s*xargs\s+rm',                # piping to xargs rm
        ]
        
    async def validate_template(self, template_path: str) -> Dict[str, Any]:
        """
        Validate a template for syntax errors and security issues.
        
        Args:
            template_path: Path to template
            
        Returns:
            Validation result dictionary
        """
        # Initialize result
        result = {
            "valid": False,
            "syntax_errors": [],
            "security_warnings": [],
            "parameter_warnings": []
        }
        
        # Check if template manager is available
        if self.template_manager is None:
            logger.error("Template manager not available for validation")
            result["error"] = "Template manager not available"
            return result
            
        try:
            # First, check syntax by attempting to load the template
            try:
                template = self.template_manager.env.get_template(template_path)
            except TemplateSyntaxError as e:
                result["syntax_errors"].append({
                    "line": e.lineno,
                    "message": str(e)
                })
                return result
                
            # Get template source
            source = self.template_manager.env.loader.get_source(self.template_manager.env, template_path)[0]
            
            # Check for security issues
            security_warnings = await self._check_security_issues(source)
            if security_warnings:
                result["security_warnings"] = security_warnings
                
            # Check for parameter issues
            param_warnings = await self._check_parameter_issues(template_path, source)
            if param_warnings:
                result["parameter_warnings"] = param_warnings
                
            # Template is valid if there are no syntax errors
            result["valid"] = len(result["syntax_errors"]) == 0
            
            return result
            
        except Exception as e:
            logger.error(f"Error validating template {template_path}: {e}")
            result["error"] = str(e)
            return result
            
    async def _check_security_issues(self, source: str) -> List[Dict[str, Any]]:
        """
        Check template source for security issues.
        
        Args:
            source: Template source
            
        Returns:
            List of security warnings
        """
        warnings = []
        
        # Check each dangerous pattern
        for pattern in self.dangerous_patterns:
            matches = re.finditer(pattern, source, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                start_line = source[:match.start()].count('\n') + 1
                context = source[max(0, match.start() - 20):min(len(source), match.end() + 20)]
                
                warnings.append({
                    "line": start_line,
                    "pattern": pattern,
                    "match": match.group(0),
                    "context": context.strip(),
                    "severity": "high",
                    "message": f"Potentially dangerous pattern found: {match.group(0)}"
                })
                
        # Additional security checks
        if re.search(r'eval\s*\(', source):
            warnings.append({
                "pattern": "eval",
                "severity": "medium",
                "message": "Use of eval() is discouraged for security reasons"
            })
            
        if re.search(r'exec\s*\(', source):
            warnings.append({
                "pattern": "exec",
                "severity": "medium",
                "message": "Use of exec() is discouraged for security reasons"
            })
            
        # Check for unvalidated input usage
        if re.search(r'\{\{\s*params\..*\s*\}\}', source):
            if not re.search(r'if\s+params\.', source):
                warnings.append({
                    "pattern": "unvalidated_params",
                    "severity": "low",
                    "message": "Template uses parameters without validation"
                })
                
        return warnings
        
    async def _check_parameter_issues(self, template_path: str, source: str) -> List[Dict[str, Any]]:
        """
        Check template for parameter issues.
        
        Args:
            template_path: Path to template
            source: Template source
            
        Returns:
            List of parameter warnings
        """
        warnings = []
        
        # Parse template to get required variables
        try:
            ast = self.template_manager.env.parse(source)
            required_vars = meta.find_undeclared_variables(ast)
            
            # Check for common typos in variable names
            var_names = list(required_vars)
            for i, var1 in enumerate(var_names):
                for var2 in var_names[i+1:]:
                    # Check for similar variable names using Levenshtein distance
                    if var1 != var2 and self._levenshtein_distance(var1, var2) <= 2:
                        warnings.append({
                            "param1": var1,
                            "param2": var2,
                            "severity": "low",
                            "message": f"Similar parameter names '{var1}' and '{var2}' may indicate a typo"
                        })
                        
            # Check for unused blocks in extension templates
            if '{% extends' in source:
                defined_blocks = re.findall(r'{%\s*block\s+([^\s%]+)[^%]*%}', source)
                if not defined_blocks:
                    warnings.append({
                        "pattern": "no_blocks",
                        "severity": "low",
                        "message": "Template extends another template but defines no blocks"
                    })
                    
            # Check for inconsistent variable naming
            camel_case = sum(1 for v in required_vars if re.match(r'^[a-z]+([A-Z][a-z]+)+$', v))
            snake_case = sum(1 for v in required_vars if re.match(r'^[a-z]+(_[a-z]+)+$', v))
            
            if camel_case > 0 and snake_case > 0:
                warnings.append({
                    "pattern": "mixed_naming",
                    "severity": "low",
                    "message": "Template uses mixed variable naming conventions (camelCase and snake_case)"
                })
                
        except Exception as e:
            logger.warning(f"Error checking parameter issues for {template_path}: {e}")
            
        return warnings
        
    async def validate_parameters(self, template_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parameters against template requirements.
        
        Args:
            template_path: Path to template
            parameters: Parameters to validate
            
        Returns:
            Validation result
        """
        result = {
            "valid": False,
            "missing_parameters": [],
            "unexpected_parameters": [],
            "type_mismatches": []
        }
        
        # Check if template manager is available
        if self.template_manager is None:
            logger.error("Template manager not available for parameter validation")
            result["error"] = "Template manager not available"
            return result
            
        try:
            # Get required parameters
            required_params = self.template_manager.get_template_required_params(template_path)
            
            # Check for missing parameters
            for param in required_params:
                # Skip special variables
                if param.startswith(('_', 'range', 'dict', 'lipsum', 'cycler', 'loop')):
                    continue
                    
                # Skip nested variables (handled below)
                if '.' in param:
                    continue
                    
                if param not in parameters:
                    result["missing_parameters"].append(param)
                    
            # Check for nested parameters
            nested_params = [p for p in required_params if '.' in p]
            for param in nested_params:
                parts = param.split('.')
                parent = parts[0]
                
                # Skip if parent is missing (already reported)
                if parent in result["missing_parameters"]:
                    continue
                    
                # Check if parent exists
                if parent not in parameters:
                    result["missing_parameters"].append(parent)
                    continue
                    
                # Check nested structure
                value = parameters.get(parent)
                for i in range(1, len(parts)):
                    if not isinstance(value, dict):
                        result["type_mismatches"].append({
                            "param": '.'.join(parts[:i]),
                            "expected": "dict",
                            "actual": type(value).__name__
                        })
                        break
                        
                    if parts[i] not in value:
                        result["missing_parameters"].append('.'.join(parts[:i+1]))
                        break
                        
                    value = value.get(parts[i])
                    
            # Check for unexpected parameters
            provided_params = list(parameters.keys())
            for param in provided_params:
                if param not in required_params and not any(req.startswith(f"{param}.") for req in required_params):
                    result["unexpected_parameters"].append(param)
                    
            # Template is valid if there are no missing parameters
            result["valid"] = len(result["missing_parameters"]) == 0
            
            return result
            
        except Exception as e:
            logger.error(f"Error validating parameters for {template_path}: {e}")
            result["error"] = str(e)
            return result
            
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Levenshtein distance
        """
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
            
        if len(s2) == 0:
            return len(s1)
            
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
            
        return previous_row[-1]