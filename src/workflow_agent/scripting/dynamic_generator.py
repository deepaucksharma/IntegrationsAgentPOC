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
            "win32": {
                "header": "# Windows PowerShell installation script\nSet-ExecutionPolicy Bypass -Scope Process -Force\n$ErrorActionPreference = \"Stop\"\n",
                "error_handler": """
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
                if system == "win32":
                    lines.append(f"Write-Host 'Checking prerequisite: {prereq}'")
                else:
                    lines.append(f"echo 'Checking prerequisite: {prereq}'")
            lines.append("\n# Installation Steps")
            for i, step in enumerate(method.get("steps", []), 1):
                cleaned = self._clean_step(step)
                if system == "win32":
                    lines.append(f"\nWrite-Host 'Step {i}: {cleaned}'")
                    # Convert Linux commands to PowerShell
                    cleaned = self._convert_to_powershell(cleaned)
                else:
                    lines.append(f"\necho 'Step {i}: {cleaned}'")
                lines.append(cleaned)
            lines.append("\n# Verification Steps")
            verify_steps = state.template_data.get("docs", {}).get("verification_steps", [])
            for step in verify_steps:
                cleaned = self._clean_step(step)
                if system == "win32":
                    lines.append(f"\nWrite-Host 'Verifying: {cleaned}'")
                    cleaned = self._convert_to_powershell(cleaned)
                else:
                    lines.append(f"\necho 'Verifying: {cleaned}'")
                lines.append(cleaned)
            script = "\n".join(lines)
            logger.info("Installation script generated successfully")
            return {"script": script}
        except Exception as e:
            logger.error(f"Error generating script: {e}")
            return {"error": str(e)}

    def _clean_step(self, step: str) -> str:
        """Clean and sanitize a script step."""
        if isinstance(step, dict):
            return step.get("command", "")
        return str(step).strip()

    def _convert_to_powershell(self, command: str) -> str:
        """Convert Linux shell commands to PowerShell commands."""
        # Basic command conversions
        conversions = {
            "mkdir -p": "New-Item -ItemType Directory -Force -Path",
            "rm -rf": "Remove-Item -Recurse -Force",
            "echo": "Write-Host",
            "sleep": "Start-Sleep -Seconds",
            "test -d": "Test-Path -PathType Container",
            "test -f": "Test-Path -PathType Leaf",
            "grep": "Select-String -Pattern",
            ">": "| Out-File -FilePath",
            ">>": "| Add-Content -Path"
        }
        
        result = command
        for linux_cmd, ps_cmd in conversions.items():
            result = result.replace(linux_cmd, ps_cmd)
            
        # Convert paths
        if "/opt/" in result:
            result = result.replace("/opt/", "C:\\Program Files\\")
            
        return result