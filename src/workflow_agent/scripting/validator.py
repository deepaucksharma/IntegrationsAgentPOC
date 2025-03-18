import logging
import re
import tempfile
import os
import subprocess
import json
from typing import Dict, Any, Optional
from ..core.state import WorkflowState
from ..config.configuration import ensure_workflow_config, dangerous_patterns

logger = logging.getLogger(__name__)

class ScriptValidator:
    async def validate_script(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not state.script:
            return {"error": "No script to validate."}
        
        workflow_config = ensure_workflow_config(config or {})
        script_content = state.script
        warnings = []

        # Check for known dangerous patterns
        for pattern in dangerous_patterns:
            if re.search(pattern, script_content, re.IGNORECASE):
                logger.warning(f"Dangerous pattern detected: {pattern}")
                return {"error": f"Dangerous pattern found: {pattern}"}

        if "#!/usr/bin/env bash" not in script_content:
            warnings.append("Script is missing shebang (#!/usr/bin/env bash)")
        if "set -e" not in script_content:
            warnings.append("Script is missing 'set -e' for error handling")

        if workflow_config.use_static_analysis:
            try:
                import shellcheck_py
                shellcheck_bin = shellcheck_py.SHELLCHECK_PATH
                with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as tf:
                    tf.write(script_content)
                    tmp_path = tf.name
                try:
                    proc = subprocess.run([shellcheck_bin, "--format=json1", tmp_path],
                                          capture_output=True, text=True)
                    if proc.stdout.strip():
                        try:
                            data = json.loads(proc.stdout)
                            for cmt in data.get("comments", []):
                                lvl = cmt.get("level")
                                msg = cmt.get("message")
                                if lvl in ["error", "warning"]:
                                    warnings.append(f"ShellCheck {lvl}: {msg}")
                        except json.JSONDecodeError:
                            warnings.append("ShellCheck output not JSON-decodable.")
                except FileNotFoundError:
                    warnings.append("ShellCheck binary not found.")
                finally:
                    os.unlink(tmp_path)
            except ImportError:
                logger.info("ShellCheck not installed, skipping static analysis.")

        if warnings:
            return {"warnings": warnings}
        return {}