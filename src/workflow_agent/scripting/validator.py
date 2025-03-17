# src/workflow_agent/scripting/validator.py
import re
import logging
import tempfile
import os
import uuid
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from ..core.state import WorkflowState
from ..config.configuration import dangerous_patterns, ensure_workflow_config

logger = logging.getLogger(__name__)

class ScriptValidator:
    """Validates scripts for safety and proper error handling."""
    
    def __init__(self):
        """Initialize the script validator."""
        self.dangerous_patterns = dangerous_patterns
    
    async def validate_script(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate the script for safety and proper error handling.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with validation results or error
        """
        if not state.script or not state.script.strip():
            error_msg = "Script validation failed: Empty script"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Check for dangerous patterns
        for pattern in self.dangerous_patterns:
            if re.search(pattern, state.script):
                error_msg = f"Script validation failed: Potentially dangerous command detected ({pattern})."
                logger.error(error_msg)
                return {"error": error_msg}
        
        # Verify basic script requirements
        if not any(line.startswith("#!/") for line in state.script.split("\n")):
            error_msg = "Script validation failed: Missing proper shebang (#!/usr/bin/env bash or #!/bin/bash)."
            logger.error(error_msg)
            return {"error": error_msg}
        
        if "set -e" not in state.script:
            error_msg = "Script validation failed: Missing 'set -e' for proper error handling."
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Check script size
        if len(state.script) > 50000:
            logger.warning(f"Script is very large ({len(state.script)} bytes). This might indicate a problem.")
        
        # Get workflow configuration
        workflow_config = ensure_workflow_config(config)
        
        # Perform static analysis if enabled
        if workflow_config.use_static_analysis:
            validation_result = await self._perform_static_analysis(state.script)
            
            if validation_result["error"]:
                error_msg = f"Script validation failed: Static analysis error: {validation_result['error']}"
                logger.error(error_msg)
                return {"error": error_msg}
            
            if validation_result["warnings"]:
                logger.warning(f"Static analysis warnings: {validation_result['warnings']}")
                return {"warnings": validation_result["warnings"]}
        
        logger.info("Script validation passed successfully")
        return {}
    
    async def _perform_static_analysis(self, script: str) -> Dict[str, Any]:
        """
        Perform static analysis on the script using ShellCheck if available.
        
        Args:
            script: Script content to analyze
            
        Returns:
            Dict with analysis results
        """
        result = {
            "error": None,
            "warnings": []
        }
        
        # Check if ShellCheck is available
        try:
            import shellcheck_py
        except ImportError:
            logger.info("ShellCheck not available for static analysis")
            return result
        
        try:
            # Create temporary file
            temp_script_path = os.path.join(tempfile.gettempdir(), f"script_{uuid.uuid4()}.sh")
            with open(temp_script_path, "w") as f:
                f.write(script)
            
            # Run ShellCheck
            issues = shellcheck_py.parse(temp_script_path)
            
            # Process results
            critical_issues = []
            warnings = []
            
            for issue in issues:
                level = issue.get("level", "info")
                message = issue.get("message", "")
                code = issue.get("code", "")
                line = issue.get("line", 0)
                
                issue_text = f"Line {line}: SC{code} - {message}"
                
                # Categorize issues
                if level == "error":
                    critical_issues.append(issue_text)
                elif level == "warning":
                    warnings.append(issue_text)
            
            # Set result
            if critical_issues:
                result["error"] = f"Critical issues found: {'; '.join(critical_issues)}"
            
            result["warnings"] = warnings
            
            # Clean up temporary file
            try:
                os.remove(temp_script_path)
            except:
                pass
                
            return result
        except Exception as e:
            logger.error(f"Error performing static analysis: {e}")
            return result