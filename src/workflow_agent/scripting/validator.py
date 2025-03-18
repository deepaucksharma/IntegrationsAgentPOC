"""Script validation for workflow agent."""
import logging
import re
import tempfile
import os
import subprocess
import json
from typing import Dict, Any, Optional, List

from ..core.state import WorkflowState
from ..config.configuration import dangerous_patterns, ensure_workflow_config

logger = logging.getLogger(__name__)

class ScriptValidator:
    """Validates scripts for security, correctness, and best practices."""
    
    async def validate_script(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not state.script:
            logger.error("No script to validate")
            return {"error": "No script to validate."}
        
        logger.info(f"Validating script for {state.action} on {state.target_name}")
        workflow_config = ensure_workflow_config(config or {})
        warnings = []
        
        # Check dangerous patterns
        dangerous_found = []
        for pattern in dangerous_patterns:
            matches = re.findall(pattern, state.script, re.IGNORECASE | re.MULTILINE)
            if matches:
                dangerous_found.append(pattern)
        if dangerous_found:
            logger.warning(f"Potentially dangerous patterns found: {dangerous_found}")
            warnings.append("Script contains potentially dangerous patterns")
        
        if "#!/usr/bin/env bash" not in state.script and "#!/bin/bash" not in state.script:
            logger.warning("Script is missing shebang")
            warnings.append("Script is missing shebang (#!/usr/bin/env bash)")
        
        if "set -e" not in state.script:
            logger.warning("Script is missing error handling (set -e)")
            warnings.append("Script is missing error handling (set -e)")
        
        # Check for command injection characters in parameters
        for key, value in state.parameters.items():
            if isinstance(value, str) and any(c in value for c in ";|&`$(){}[]<>\\"):
                logger.warning(f"Parameter '{key}' might contain command injection characters")
                warnings.append(f"Parameter '{key}' might contain command injection characters")
        
        # Perform ShellCheck analysis if enabled
        if workflow_config.use_static_analysis:
            try:
                import shellcheck_py
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as tf:
                    script_path = tf.name
                    tf.write(state.script)
                try:
                    shellcheck_bin = shellcheck_py.SHELLCHECK_PATH
                    cmd = [shellcheck_bin, '--format=json1', script_path]
                    proc = subprocess.run(cmd, capture_output=True, text=True)
                    if proc.stdout.strip():
                        try:
                            data = json.loads(proc.stdout)
                            comments = data.get('comments', [])
                            shellcheck_warnings = []
                            for comment in comments:
                                lvl = comment.get('level', '').lower()
                                message = comment.get('message', '')
                                if lvl == 'error':
                                    shellcheck_warnings.append(f"ShellCheck error: {message}")
                                elif lvl == 'warning':
                                    shellcheck_warnings.append(f"ShellCheck warning: {message}")
                            if shellcheck_warnings:
                                logger.warning(f"ShellCheck found {len(shellcheck_warnings)} issues")
                                warnings.extend(shellcheck_warnings)
                        except json.JSONDecodeError:
                            logger.warning(f"ShellCheck output not valid JSON: {proc.stdout}")
                            warnings.append("ShellCheck returned invalid JSON output.")
                    if proc.stderr.strip():
                        logger.debug(f"ShellCheck stderr: {proc.stderr.strip()}")
                finally:
                    os.unlink(script_path)
            except ImportError:
                logger.info("ShellCheck (shellcheck-py) not installed; skipping static analysis")
        
        if dangerous_found:
            logger.error("Script validation failed due to dangerous patterns")
            return {"error": "Script validation failed: dangerous patterns detected.", "warnings": warnings}
        if warnings:
            logger.info(f"Script validation passed with warnings: {warnings}")
            return {"warnings": warnings}
        logger.info("Script validation passed successfully")
        return {}