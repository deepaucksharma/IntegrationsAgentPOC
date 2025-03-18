import logging
import os
import json
from typing import Dict, Any, Optional, List
from string import Template
from pathlib import Path
from ..core.state import WorkflowState
from ..config.configuration import ensure_workflow_config

logger = logging.getLogger(__name__)

class DynamicScriptGenerator:
    """Generates dynamic installation scripts from documentation-based knowledge."""
    def __init__(self):
        # Define base templates for Linux and Windows
        self.script_templates = {
            "linux": {
                "header": "#!/bin/bash\nset -e\n",
                "error_handler": """
trap 'echo "Error occurred at line $LINENO"; exit 1' ERR
""",
                "check_admin": """
if [ "$EUID" -ne 0 ]; then
    echo "This script requires root privileges"
    exit 1
fi
""",
            },
            "windows": {
                "header": "# Windows installation script\nSet-ExecutionPolicy Bypass -Scope Process -Force\n",
                "error_handler": """
$ErrorActionPreference = "Stop"
trap {
    Write-Error $_
    exit 1
}
""",
                "check_admin": """
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script requires administrator privileges"
    exit 1
}
"""
            }
        }

    async def generate_from_knowledge(self, state: Any) -> Dict[str, str]:
        try:
            logger.info("Generating installation script from knowledge")
            platform_info = state.template_data.get("platform_info", {})
            system = platform_info.get("system", "linux").lower()
            method = state.template_data.get("selected_method", {})
            prereqs = state.template_data.get("platform_specific", {}).get("prerequisites", [])
            lines = []
            templates = self.script_templates.get(system, self.script_templates["linux"])
            lines.append(templates["header"])
            lines.append(templates["error_handler"])
            lines.append(templates["check_admin"])
            lines.append("\n# Prerequisite Checks")
            for prereq in prereqs:
                lines.append(f"echo 'Checking prerequisite: {prereq}'")
            lines.append("\n# Installation Steps")
            for i, step in enumerate(method.get("steps", []), 1):
                cleaned = self._clean_step(step)
                lines.append(f"\necho 'Step {i}: {cleaned}'")
                lines.append(cleaned)
            lines.append("\n# Verification Steps")
            verify_steps = state.template_data.get("docs", {}).get("verification_steps", [])
            for step in verify_steps:
                cleaned = self._clean_step(step)
                lines.append(f"\necho 'Verifying: {cleaned}'")
                lines.append(cleaned)
            script = "\n".join(lines)
            logger.info("Installation script generated successfully")
            return {"script": script}
        except Exception as e:
            logger.error(f"Error generating script: {e}")
            return {"error": str(e)}

    def _clean_step(self, step: str) -> str:
        step = step.strip().replace("```", "").replace("`", "")
        while "(" in step and ")" in step:
            start = step.find("(")
            end = step.find(")") + 1
            step = step[:start].strip() + step[end:].strip()
        return step