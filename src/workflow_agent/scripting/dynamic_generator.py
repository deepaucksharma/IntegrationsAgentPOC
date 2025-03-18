"""Dynamic script generator based on documentation knowledge."""
import logging
import os
from typing import Dict, Any, List, Optional
from string import Template

logger = logging.getLogger(__name__)

class DynamicScriptGenerator:
    """Generates dynamic installation scripts from documentation knowledge."""
    
    def __init__(self):
        """Initialize the script generator with template mappings."""
        self.script_templates = {
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
# Check for admin privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script requires administrator privileges"
    exit 1
}
""",
                "package_manager_check": """
# Check for package manager
if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Chocolatey package manager..."
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))
}
""",
                "prereq_check": Template("""
# Check for $name
if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
    Write-Host "Installing $name..."
    $install_command
}
""")
            },
            "linux": {
                "header": "#!/bin/bash\nset -e\n",
                "error_handler": """
trap 'handle_error $? $LINENO' ERR

handle_error() {
    echo "Error $1 occurred on line $2"
    exit 1
}
""",
                "check_admin": """
# Check for root privileges
if [ "$EUID" -ne 0 ]; then
    echo "This script requires root privileges"
    exit 1
fi
""",
                "package_manager_check": """
# Detect package manager
if command -v apt-get >/dev/null 2>&1; then
    PKG_MANAGER="apt-get"
    INSTALL_CMD="apt-get install -y"
    UPDATE_CMD="apt-get update"
elif command -v yum >/dev/null 2>&1; then
    PKG_MANAGER="yum"
    INSTALL_CMD="yum install -y"
    UPDATE_CMD="yum check-update || true"
elif command -v dnf >/dev/null 2>&1; then
    PKG_MANAGER="dnf"
    INSTALL_CMD="dnf install -y"
    UPDATE_CMD="dnf check-update || true"
elif command -v zypper >/dev/null 2>&1; then
    PKG_MANAGER="zypper"
    INSTALL_CMD="zypper install -y"
    UPDATE_CMD="zypper refresh"
else
    echo "No supported package manager found"
    exit 1
fi
""",
                "prereq_check": Template("""
# Check for $name
if ! command -v $command &> /dev/null; then
    echo "Installing $name..."
    $INSTALL_CMD $package
fi
""")
            }
        }

    async def generate_from_knowledge(self, state: Any) -> Dict[str, str]:
        """Creates an installation script based on the selected method."""
        try:
            logger.info("Generating installation script from documentation")
            
            # Get platform-specific information
            platform_info = state.template_data.get("platform_info", {})
            system = platform_info.get("system", "").lower()
            
            # Get selected method and prerequisites
            method = state.template_data.get("selected_method", {})
            prereqs = state.template_data.get("platform_specific", {}).get("prerequisites", [])
            
            if not method:
                raise Exception("No installation method selected")
            
            # Generate the script
            script_lines = []
            
            # Add appropriate header and error handling
            script_lines.extend(self._generate_header(system))
            
            # Add package manager detection
            script_lines.append(self.script_templates.get(system, self.script_templates["linux"])["package_manager_check"])
            
            # Add prerequisite checks
            script_lines.extend(self._generate_prereq_checks(system, prereqs))
            
            # Add installation steps
            script_lines.extend(self._generate_installation_steps(system, method))
            
            # Add verification steps
            script_lines.extend(self._generate_verification_steps(state))
            
            script = "\n".join(script_lines)
            
            logger.info("Successfully generated installation script")
            return {"script": script}
            
        except Exception as e:
            logger.error(f"Failed to generate installation script: {e}")
            return {"error": str(e)}

    def _generate_header(self, system: str) -> List[str]:
        """Generates script header with appropriate shell and error handling."""
        templates = self.script_templates.get(system, self.script_templates["linux"])
        
        header_lines = []
        header_lines.append(templates["header"])
        header_lines.append(templates["error_handler"])
        header_lines.append(templates["check_admin"])
        header_lines.append("\n# Begin installation\n")
        
        return header_lines

    def _generate_prereq_checks(self, system: str, prereqs: List[str]) -> List[str]:
        """Generates prerequisite check commands."""
        templates = self.script_templates.get(system, self.script_templates["linux"])
        prereq_lines = ["\n# Check prerequisites"]
        
        for prereq in prereqs:
            # Extract command name and installation command from prerequisite text
            command = self._extract_command_from_prereq(prereq)
            if command:
                if system == "linux":
                    check = templates["prereq_check"].substitute(
                        name=command,
                        command=command,
                        package=command
                    )
                else:  # windows
                    check = templates["prereq_check"].substitute(
                        name=command,
                        command=command,
                        install_command=f"choco install {command} -y"
                    )
                prereq_lines.append(check)
        
        return prereq_lines

    def _generate_installation_steps(self, system: str, method: Dict[str, Any]) -> List[str]:
        """Generates installation commands from method steps."""
        steps = method.get("steps", [])
        install_lines = ["\n# Installation steps"]
        
        for i, step in enumerate(steps, 1):
            # Clean and format the step
            if isinstance(step, str):
                step_text = step
            elif isinstance(step, dict) and "command" in step:
                step_text = step["command"]
            else:
                continue
                
            cleaned_step = self._clean_step_command(step_text)
            if cleaned_step:
                install_lines.extend([
                    f"\necho 'Step {i}: {cleaned_step}'",
                    cleaned_step
                ])
        
        return install_lines

    def _generate_verification_steps(self, state: Any) -> List[str]:
        """Generates verification commands."""
        verify_steps = state.template_data.get("docs", {}).get("verification_steps", [])
        verify_lines = ["\n# Verification steps"]
        
        for step in verify_steps:
            # Clean and format the verification command
            cleaned_step = self._clean_step_command(step)
            if cleaned_step:
                verify_lines.extend([
                    f"\necho 'Verifying: {cleaned_step}'",
                    cleaned_step
                ])
        
        verify_lines.append('\necho "Installation and verification completed successfully"')
        return verify_lines

    def _extract_command_from_prereq(self, prereq: str) -> str:
        """Extracts command name from prerequisite text."""
        # Common command keywords
        keywords = ["install", "requires", "need", "dependency"]
        words = prereq.lower().split()
        
        for i, word in enumerate(words):
            if word in keywords and i + 1 < len(words):
                return words[i + 1].strip(".,:")
        
        return ""

    def _clean_step_command(self, step: str) -> str:
        """Cleans and formats a command step."""
        # Remove common documentation artifacts
        step = step.strip()
        step = step.replace("```", "").replace("`", "")
        step = step.replace("$ ", "").replace("# ", "")
        
        # Remove explanatory text in parentheses
        import re
        step = re.sub(r'\([^)]*\)', '', step)
        
        return step