"""
Enhanced script validation with security checks and static analysis integration.
"""
import logging
import re
import subprocess
import tempfile
import os
import json
import shutil
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from ..config.configuration import WorkflowConfiguration, DANGEROUS_PATTERNS
from ..error.exceptions import ValidationError

logger = logging.getLogger(__name__)

class ScriptValidator:
    """Validates scripts for security and correctness using static analysis tools."""
    
    def __init__(self, config: WorkflowConfiguration):
        """
        Initialize script validator.
        
        Args:
            config: Workflow configuration
        """
        self.config = config
        self._initialize_analyzers()
        
    def _initialize_analyzers(self) -> None:
        """Initialize and verify availability of static analysis tools."""
        self.available_analyzers = {
            "shell": self._check_tool_available("shellcheck"),
            "powershell": self._check_tool_available("powershell"),
            "python": self._check_tool_available("pylint")
        }
        
        logger.info(f"Available static analyzers: {', '.join([k for k, v in self.available_analyzers.items() if v])}")
        
    def _check_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available in the PATH."""
        try:
            if tool_name == "powershell" and os.name != "nt":
                return False
                
            cmd = "where" if os.name == "nt" else "which"
            result = subprocess.run(
                [cmd, tool_name], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                check=False
            )
            return result.returncode == 0
        except Exception:
            return False
        
    def validate(self, script_content: str) -> Dict[str, Any]:
        """
        Validate a script for security and correctness using static analysis.
        
        Args:
            script_content: Content of the script to validate
            
        Returns:
            Dictionary with validation results
        """
        warnings = []
        errors = []
        static_analysis = []
        
        try:
            # Base security checks
            security_warnings = self._check_security_patterns(script_content)
            warnings.extend(security_warnings)
            
            # Determine script type
            script_type = self._detect_script_type(script_content)
            
            # Apply static analysis if configured
            if self.config.use_static_analysis:
                analysis_results = self._run_static_analysis(script_content, script_type)
                static_analysis.extend(analysis_results.get("results", []))
                warnings.extend(analysis_results.get("warnings", []))
                errors.extend(analysis_results.get("errors", []))
            
            # Perform additional checks based on script type
            if script_type == "shell":
                shell_results = self._run_shellcheck(script_content)
                warnings.extend(shell_results["warnings"])
                errors.extend(shell_results["errors"])
            
            elif script_type == "powershell":
                powershell_results = self._validate_powershell(script_content)
                warnings.extend(powershell_results["warnings"])
                errors.extend(powershell_results["errors"])
            
            elif script_type == "python":
                python_results = self._validate_python(script_content)
                warnings.extend(python_results["warnings"])
                errors.extend(python_results["errors"])
            
            # Check change tracking markers
            if not self._has_change_tracking(script_content, script_type):
                warnings.append("Script does not contain proper change tracking markers")
                
            # Check for proper error handling
            if not self._has_error_handling(script_content, script_type):
                warnings.append("Script might lack proper error handling")
                
            # Determine validity - fails only on errors, not warnings
            valid = len(errors) == 0
            
            return {
                "valid": valid,
                "warnings": warnings,
                "errors": errors,
                "static_analysis": static_analysis,
                "script_type": script_type
            }
            
        except Exception as e:
            logger.error(f"Error during script validation: {e}", exc_info=True)
            return {
                "valid": False,
                "warnings": warnings,
                "errors": [f"Validation error: {str(e)}"],
                "script_type": "unknown"
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
            r"format\s+[^\s]*\s+/[A-Za-z]",  # Format disk command
            r"mkfs\.[a-z]+\s+/dev/[a-z]+",   # Make filesystem
            r"fdisk\s+/dev/[a-z]+",          # Partition disk
            r"wget.*?\s*\|\s*(sudo|bash|sh)", # Wget piped to execution
            r"curl.*?\s*\|\s*(sudo|bash|sh)", # Curl piped to execution
            r"\bshutdown\b",                 # System shutdown
            r"\breboot\b",                   # System reboot
            r"rm\s+-rf\s+[^/]*[/]+[^/]*",    # Risky recursive delete
            r"chmod\s+-R\s+777",             # Insecure permissions
            r"eval\s+[\"\'].*{.*}",          # Potentially unsafe eval
            r"exec\s+[\"\'].*{.*}"           # Potentially unsafe exec
        ]
        
        for cmd in suspicious_cmds:
            if re.search(cmd, script_content, re.IGNORECASE):
                warnings.append(f"Suspicious command detected: {cmd}")
                
        return warnings
    def _detect_script_type(self, script_content: str) -> str:
        """
        Detect the type of script based on content.
        
        Args:
            script_content: Content of the script to analyze
            
        Returns:
            Script type: 'shell', 'powershell', 'python', or 'unknown'
        """
        # Shell script detection
        if (script_content.startswith("#!/bin/bash") or 
                script_content.startswith("#!/bin/sh") or
                script_content.startswith("#!/usr/bin/env bash") or
                re.search(r"if\s+\[\s+.*\s+\]\s*;", script_content) or
                re.search(r"echo\s+\".*\"", script_content)):
            return "shell"
                
        # PowerShell script detection
        if (script_content.startswith("#!powershell") or
                "<#" in script_content[:100] or
                script_content.startswith("param(") or
                "$ErrorActionPreference" in script_content[:500] or
                "Write-Host" in script_content or
                "Get-Item" in script_content):
            return "powershell"
                
        # Python script detection
        if (script_content.startswith("#!/usr/bin/env python") or
                script_content.startswith("#!/usr/bin/python") or
                script_content.startswith("import ") or
                script_content.startswith("from ") or
                "def " in script_content[:500] or
                re.search(r"print\(.*\)", script_content)):
            return "python"
            
        # Default to unknown
        return "unknown"
        
    def _run_static_analysis(self, script_content: str, script_type: str) -> Dict[str, Any]:
        """
        Run static analysis tools based on script type.
        
        Args:
            script_content: Content of the script to analyze
            script_type: Type of script ('shell', 'powershell', 'python', etc.)
            
        Returns:
            Dictionary with analysis results
        """
        results = {
            "results": [],
            "warnings": [],
            "errors": []
        }
        
        if script_type == "shell" and self.available_analyzers.get("shell"):
            shellcheck_results = self._run_shellcheck(script_content)
            results["results"].extend(shellcheck_results.get("results", []))
            results["warnings"].extend(shellcheck_results.get("warnings", []))
            results["errors"].extend(shellcheck_results.get("errors", []))
            
        elif script_type == "powershell" and self.available_analyzers.get("powershell"):
            psscript_analyzer_results = self._run_pscriptanalyzer(script_content)
            results["results"].extend(psscript_analyzer_results.get("results", []))
            results["warnings"].extend(psscript_analyzer_results.get("warnings", []))
            results["errors"].extend(psscript_analyzer_results.get("errors", []))
            
        elif script_type == "python" and self.available_analyzers.get("python"):
            pylint_results = self._run_pylint(script_content)
            results["results"].extend(pylint_results.get("results", []))
            results["warnings"].extend(pylint_results.get("warnings", []))
            results["errors"].extend(pylint_results.get("errors", []))
            
        return results
        
    def _has_change_tracking(self, script_content: str, script_type: str) -> bool:
        """
        Check if the script has proper change tracking markers.
        
        Args:
            script_content: Content of the script to check
            script_type: Type of script
            
        Returns:
            True if change tracking is present, False otherwise
        """
        change_markers = [
            r"CHANGE:[A-Z_]+:",
            r"# \[CHANGE\]",
            r"// \[CHANGE\]",
            r"Write-Output \"CHANGE:"
        ]
        
        for marker in change_markers:
            if re.search(marker, script_content):
                return True
                
        return False
        
    def _has_error_handling(self, script_content: str, script_type: str) -> bool:
        """
        Check if the script has proper error handling.
        
        Args:
            script_content: Content of the script to check
            script_type: Type of script
            
        Returns:
            True if error handling is present, False otherwise
        """
        if script_type == "shell":
            return (re.search(r"set -e", script_content) or 
                    re.search(r"trap.*ERR", script_content) or
                    re.search(r"if.*then.*exit", script_content))
        elif script_type == "powershell":
            return (re.search(r"\$ErrorActionPreference\s*=\s*[\"']Stop[\"']", script_content) or
                    re.search(r"try\s*{.*}\s*catch", script_content))
        elif script_type == "python":
            return re.search(r"try:.*except", script_content, re.DOTALL)
            
        return False
        
    def _run_shellcheck(self, script_content: str) -> Dict[str, Any]:
        """
        Run shellcheck on a shell script.
        
        Args:
            script_content: Content of the shell script
            
        Returns:
            Dictionary with analysis results
        """
        results = []
        warnings = []
        errors = []
        
        try:
            # Write script to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".sh", delete=False) as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(script_content.encode())
                
            try:
                # Run shellcheck with JSON output
                command = ["shellcheck", "-f", "json", temp_file_path]
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                # Parse shellcheck output
                if result.stdout:
                    try:
                        issues = json.loads(result.stdout)
                        for issue in issues:
                            level = issue.get("level", "warning")
                            message = issue.get("message", "Unknown issue")
                            line = issue.get("line", 0)
                            
                            issue_entry = {
                                "line": line,
                                "message": message,
                                "level": level,
                                "code": issue.get("code", "")
                            }
                            results.append(issue_entry)
                            
                            if level == "error":
                                errors.append(f"Line {line}: {message} (SC{issue.get('code', '')})")
                            else:
                                warnings.append(f"Line {line}: {message} (SC{issue.get('code', '')})")
                    except json.JSONDecodeError:
                        warnings.append("Failed to parse shellcheck output")
                        
            finally:
                # Clean up the temporary file
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
                
        except FileNotFoundError:
            warnings.append("shellcheck not found in PATH")
        except Exception as e:
            warnings.append(f"Error running shellcheck: {e}")
            
        return {
            "results": results,
            "warnings": warnings,
            "errors": errors
        }
        
    def _run_pscriptanalyzer(self, script_content: str) -> Dict[str, Any]:
        """
        Run PSScriptAnalyzer on a PowerShell script.
        
        Args:
            script_content: Content of the PowerShell script
            
        Returns:
            Dictionary with analysis results
        """
        results = []
        warnings = []
        errors = []
        
        try:
            # Only run on Windows
            if os.name != "nt":
                warnings.append("PowerShell validation skipped on non-Windows platform")
                return {"results": results, "warnings": warnings, "errors": errors}
                
            # Write script to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".ps1", delete=False) as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(script_content.encode())
                
            try:
                # First check basic syntax
                syntax_cmd = f'powershell -Command "& {{$ErrorActionPreference=\'Stop\'; $null = [System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw \'{temp_file_path}\'), [ref]$null)}}"'
                syntax_result = subprocess.run(
                    syntax_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if syntax_result.returncode != 0:
                    for line in syntax_result.stderr.splitlines():
                        if line.strip():
                            errors.append(f"Syntax error: {line.strip()}")
                
                # Try PSScriptAnalyzer if available
                analyzer_cmd = f'powershell -Command "& {{if (Get-Module -ListAvailable PSScriptAnalyzer) {{ Invoke-ScriptAnalyzer -Path \'{temp_file_path}\' | ConvertTo-Json }} else {{ Write-Output \'PSScriptAnalyzer not available\' }}}}"'
                analyzer_result = subprocess.run(
                    analyzer_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if "PSScriptAnalyzer not available" in analyzer_result.stdout:
                    warnings.append("PSScriptAnalyzer not available, skipping advanced PowerShell analysis")
                else:
                    try:
                        analyzer_output = analyzer_result.stdout.strip()
                        if analyzer_output and not analyzer_output.startswith("PSScriptAnalyzer"):
                            analyzer_issues = json.loads(analyzer_output)
                            if isinstance(analyzer_issues, dict):
                                analyzer_issues = [analyzer_issues]
                                
                            for issue in analyzer_issues:
                                severity = issue.get("Severity", "Warning")
                                message = issue.get("Message", "Unknown issue")
                                line = issue.get("Line", 0)
                                rule = issue.get("RuleName", "")
                                
                                issue_entry = {
                                    "line": line,
                                    "message": message,
                                    "level": severity.lower(),
                                    "code": rule
                                }
                                results.append(issue_entry)
                                
                                if severity.lower() == "error":
                                    errors.append(f"Line {line}: {message} ({rule})")
                                else:
                                    warnings.append(f"Line {line}: {message} ({rule})")
                    except json.JSONDecodeError:
                        warnings.append("Failed to parse PSScriptAnalyzer output")
                            
            finally:
                # Clean up the temporary file
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
                
        except FileNotFoundError:
            warnings.append("PowerShell not found in PATH")
        except Exception as e:
            warnings.append(f"Error validating PowerShell script: {e}")
            
        return {
            "results": results,
            "warnings": warnings,
            "errors": errors
        }
        
    def _run_pylint(self, script_content: str) -> Dict[str, Any]:
        """
        Run pylint on a Python script.
        
        Args:
            script_content: Content of the Python script
            
        Returns:
            Dictionary with analysis results
        """
        results = []
        warnings = []
        errors = []
        
        try:
            # First check basic syntax
            try:
                compile(script_content, "<string>", "exec")
            except SyntaxError as e:
                errors.append(f"Python syntax error: {e}")
                # Return early if syntax is invalid
                return {
                    "results": [{"line": getattr(e, "lineno", 0), "message": str(e), "level": "error"}],
                    "warnings": [],
                    "errors": errors
                }
            except Exception as e:
                errors.append(f"Python validation error: {e}")
                
            # Check for unsafe functions
            unsafe_functions = ["eval", "exec", "os.system", "subprocess.call", "subprocess.Popen"]
            for func in unsafe_functions:
                if re.search(rf"\b{func}\s*\(", script_content):
                    warnings.append(f"Potentially unsafe function call detected: {func}")
                    
            # Run pylint if available
            if self.available_analyzers.get("python"):
                # Write script to a temporary file
                with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp_file:
                    temp_file_path = temp_file.name
                    temp_file.write(script_content.encode())
                    
                try:
                    # Run pylint with JSON output format
                    pylint_cmd = ["pylint", "--output-format=json", temp_file_path]
                    pylint_result = subprocess.run(
                        pylint_cmd,
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    
                    try:
                        pylint_output = pylint_result.stdout.strip()
                        if pylint_output:
                            pylint_issues = json.loads(pylint_output)
                            
                            for issue in pylint_issues:
                                message_type = issue.get("type", "warning")
                                message = issue.get("message", "Unknown issue")
                                line = issue.get("line", 0)
                                message_id = issue.get("message-id", "")
                                
                                issue_entry = {
                                    "line": line,
                                    "message": message,
                                    "level": "error" if message_type in ["error", "fatal"] else "warning",
                                    "code": message_id
                                }
                                results.append(issue_entry)
                                
                                if message_type in ["error", "fatal"]:
                                    errors.append(f"Line {line}: {message} ({message_id})")
                                else:
                                    warnings.append(f"Line {line}: {message} ({message_id})")
                    except json.JSONDecodeError:
                        warnings.append("Failed to parse pylint output")
                        
                finally:
                    # Clean up the temporary file
                    try:
                        os.unlink(temp_file_path)
                    except Exception:
                        pass
                
        except FileNotFoundError:
            warnings.append("pylint not found in PATH, skipping advanced Python analysis")
        except Exception as e:
            warnings.append(f"Error running pylint: {e}")
            
        return {
            "results": results,
            "warnings": warnings,
            "errors": errors
        }
