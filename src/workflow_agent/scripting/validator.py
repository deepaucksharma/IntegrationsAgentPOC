"""
Script validation with security checks.
"""
import logging
import re
import subprocess
import tempfile
import os
from typing import Dict, Any, List, Optional

from ..config.configuration import WorkflowConfiguration, DANGEROUS_PATTERNS

logger = logging.getLogger(__name__)

class ScriptValidator:
    """Validates scripts for security and correctness."""
    
    def __init__(self, config: WorkflowConfiguration):
        """
        Initialize script validator.
        
        Args:
            config: Workflow configuration
        """
        self.config = config
        
    def validate(self, script_content: str) -> Dict[str, Any]:
        """
        Validate a script for security and correctness.
        
        Args:
            script_content: Content of the script to validate
            
        Returns:
            Dictionary with validation results
        """
        warnings = []
        errors = []
        
        # Check for dangerous patterns
        security_warnings = self._check_security_patterns(script_content)
        warnings.extend(security_warnings)
        
        # Check for syntax if the appropriate tools are available
        # Try shellcheck for shell scripts
        if self._is_shell_script(script_content):
            shellcheck_results = self._run_shellcheck(script_content)
            warnings.extend(shellcheck_results["warnings"])
            errors.extend(shellcheck_results["errors"])
        
        # Check for PowerShell syntax
        elif self._is_powershell_script(script_content):
            powershell_results = self._validate_powershell(script_content)
            warnings.extend(powershell_results["warnings"])
            errors.extend(powershell_results["errors"])
        
        # Check for Python syntax
        elif self._is_python_script(script_content):
            python_results = self._validate_python(script_content)
            warnings.extend(python_results["warnings"])
            errors.extend(python_results["errors"])
        
        # Determine validity based on errors
        valid = len(errors) == 0
        
        return {
            "valid": valid,
            "warnings": warnings,
            "errors": errors
        }
        
    def _check_security_patterns(self, script_content: str) -> List[str]:
        """
        Check for dangerous security patterns.
        
        Args:
            script_content: Content of the script to check
            
        Returns:
            List of security warnings
        """
        warnings = []
        
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, script_content, re.IGNORECASE):
                warnings.append(f"Potentially dangerous pattern detected: {pattern}")
        
        # Check for suspicious commands
        suspicious_cmds = [
            "format",
            "mkfs",
            "fdisk",
            "wget.*sudo",
            "curl.*sudo",
            "shutdown",
            "reboot"
        ]
        
        for cmd in suspicious_cmds:
            if re.search(rf"\b{cmd}\b", script_content, re.IGNORECASE):
                warnings.append(f"Suspicious command detected: {cmd}")
                
        return warnings
        
    def _run_shellcheck(self, script_content: str) -> Dict[str, List[str]]:
        """
        Run shellcheck on a shell script.
        
        Args:
            script_content: Content of the shell script
            
        Returns:
            Dictionary with warnings and errors
        """
        warnings = []
        errors = []
        
        try:
            # Write script to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".sh", delete=False) as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(script_content.encode())
                
            try:
                # Run shellcheck
                result = subprocess.run(
                    ["shellcheck", "-f", "json", temp_file_path],
                    capture_output=True,
                    text=True
                )
                
                # Parse output
                if result.returncode != 0:
                    import json
                    try:
                        issues = json.loads(result.stdout)
                        for issue in issues:
                            level = issue.get("level", "warning")
                            message = issue.get("message", "Unknown issue")
                            line = issue.get("line", 0)
                            
                            if level == "error":
                                errors.append(f"Line {line}: {message}")
                            else:
                                warnings.append(f"Line {line}: {message}")
                    except json.JSONDecodeError:
                        warnings.append("Failed to parse shellcheck output")
                        
            finally:
                # Clean up the temporary file
                os.unlink(temp_file_path)
                
        except FileNotFoundError:
            warnings.append("shellcheck not found in PATH, skipping shell script validation")
        except Exception as e:
            warnings.append(f"Error running shellcheck: {e}")
            
        return {
            "warnings": warnings,
            "errors": errors
        }
        
    def _validate_powershell(self, script_content: str) -> Dict[str, List[str]]:
        """
        Validate PowerShell script syntax.
        
        Args:
            script_content: Content of the PowerShell script
            
        Returns:
            Dictionary with warnings and errors
        """
        warnings = []
        errors = []
        
        try:
            # Only run on Windows
            if os.name != "nt":
                warnings.append("PowerShell validation skipped on non-Windows platform")
                return {"warnings": warnings, "errors": errors}
                
            # Write script to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".ps1", delete=False) as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(script_content.encode())
                
            try:
                # Run PowerShell syntax check
                result = subprocess.run(
                    ["powershell", "-c", f"Test-Script '{temp_file_path}'"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    for line in result.stderr.splitlines():
                        if line.strip():
                            errors.append(line.strip())
                            
            finally:
                # Clean up the temporary file
                os.unlink(temp_file_path)
                
        except FileNotFoundError:
            warnings.append("PowerShell not found in PATH, skipping PowerShell script validation")
        except Exception as e:
            warnings.append(f"Error validating PowerShell script: {e}")
            
        return {
            "warnings": warnings,
            "errors": errors
        }
        
    def _validate_python(self, script_content: str) -> Dict[str, List[str]]:
        """
        Validate Python script syntax.
        
        Args:
            script_content: Content of the Python script
            
        Returns:
            Dictionary with warnings and errors
        """
        warnings = []
        errors = []
        
        try:
            # Compile the Python code to check syntax
            compile(script_content, "<string>", "exec")
        except SyntaxError as e:
            errors.append(f"Python syntax error: {e}")
        except Exception as e:
            errors.append(f"Python validation error: {e}")
            
        # Check for unsafe functions
        unsafe_functions = ["eval", "exec", "os.system", "subprocess.call", "subprocess.Popen"]
        for func in unsafe_functions:
            if re.search(rf"\b{func}\s*\(", script_content):
                warnings.append(f"Potentially unsafe function call detected: {func}")
                
        return {
            "warnings": warnings,
            "errors": errors
        }
        
    def _is_shell_script(self, script_content: str) -> bool:
        """Check if content is a shell script."""
        return (script_content.startswith("#!/bin/bash") or 
                script_content.startswith("#!/bin/sh") or
                script_content.startswith("#!/usr/bin/env bash"))
                
    def _is_powershell_script(self, script_content: str) -> bool:
        """Check if content is a PowerShell script."""
        return (script_content.startswith("#!powershell") or
                "<#" in script_content[:100] or
                script_content.startswith("param(") or
                "$ErrorActionPreference" in script_content[:500])
                
    def _is_python_script(self, script_content: str) -> bool:
        """Check if content is a Python script."""
        return (script_content.startswith("#!/usr/bin/env python") or
                script_content.startswith("#!/usr/bin/python") or
                script_content.startswith("import ") or
                script_content.startswith("from ") or
                "def " in script_content[:500])
