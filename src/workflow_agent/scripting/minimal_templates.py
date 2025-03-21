"""Minimal templates for script generation."""
from typing import Dict, Any

# Linux/Unix minimal templates
LINUX_TEMPLATES = {
    "header": """#!/bin/bash
set -e
trap 'echo "Error on line $LINENO"' ERR

# Script generated for {action} of {target_name}
# Generated at: {timestamp}

""",

    "logging": """
# Logging function
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

log_success() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $1"
}

""",

    "parameters": """
# Parameters
{parameters}

# Verify required parameters
{parameter_verification}
""",

    "package_manager_detection": """
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
    log_error "No supported package manager found"
    exit 1
fi
""",

    "prerequisites_check": """
# Check prerequisites
check_prerequisites() {
    log_message "Checking prerequisites..."
    {prerequisite_checks}
}
""",

    "admin_check": """
# Check for root privileges
if [ "$EUID" -ne 0 ]; then
    log_error "This script requires root privileges"
    exit 1
fi
""",

    "verification": """
# Verification
verify_installation() {
    log_message "Verifying installation..."
    {verification_steps}
}
"""
}

# Windows/PowerShell minimal templates
WINDOWS_TEMPLATES = {
    "header": """# PowerShell script
Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = "Stop"

# Script generated for {action} of {target_name}
# Generated at: {timestamp}

""",

    "logging": """
# Logging functions
function Write-LogMessage {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message"
}

function Write-LogError {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] ERROR: $Message" -ForegroundColor Red
}

function Write-LogSuccess {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] SUCCESS: $Message" -ForegroundColor Green
}

""",

    "parameters": """
# Parameters
{parameters}

# Verify required parameters
{parameter_verification}
""",

    "admin_check": """
# Check for administrator privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-LogError "This script requires administrator privileges."
    exit 1
}
""",

    "prerequisites_check": """
# Check prerequisites
function Check-Prerequisites {
    Write-LogMessage "Checking prerequisites..."
    {prerequisite_checks}
}
""",

    "verification": """
# Verification
function Verify-Installation {
    Write-LogMessage "Verifying installation..."
    {verification_steps}
}
"""
}

def get_minimal_template(section: str, os_type: str) -> str:
    """Get minimal template by section and OS type."""
    if os_type.lower() in ["windows", "win32", "win"]:
        return WINDOWS_TEMPLATES.get(section, "")
    else:
        return LINUX_TEMPLATES.get(section, "")

def build_parameter_list(parameters: Dict[str, Any], os_type: str) -> str:
    """Build parameter list from parameter dictionary."""
    if not parameters:
        return "# No parameters provided"
        
    result = []
    if os_type.lower() in ["windows", "win32", "win"]:
        for name, value in parameters.items():
            if isinstance(value, str):
                result.append(f'${name} = "{value}"')
            else:
                result.append(f'${name} = {value}')
    else:
        for name, value in parameters.items():
            if isinstance(value, str):
                result.append(f'{name}="{value}"')
            else:
                result.append(f'{name}={value}')
                
    return "\n".join(result)

def build_parameter_verification(parameters: Dict[str, Any], os_type: str) -> str:
    """Build parameter verification code."""
    if not parameters:
        return "# No parameters to verify"
        
    result = []
    if os_type.lower() in ["windows", "win32", "win"]:
        for name in parameters.keys():
            result.append(f'if ([string]::IsNullOrEmpty(${name})) {{')
            result.append(f'    Write-LogError "Parameter {name} is required but not provided"')
            result.append('    exit 1')
            result.append('}')
    else:
        for name in parameters.keys():
            result.append(f'if [ -z "${{name}}" ]; then')
            result.append(f'    log_error "Parameter {name} is required but not provided"')
            result.append('    exit 1')
            result.append('fi')
                
    return "\n".join(result)

def build_prerequisite_checks(prerequisites: list, os_type: str) -> str:
    """Build prerequisite checks from list."""
    if not prerequisites:
        return "# No prerequisites to check"
        
    result = []
    if os_type.lower() in ["windows", "win32", "win"]:
        for prereq in prerequisites:
            # Try to extract command name
            if isinstance(prereq, dict) and "name" in prereq:
                cmd = prereq["name"]
            elif isinstance(prereq, str):
                words = prereq.split()
                cmd = next((word for word in words if not word.startswith("-")), words[0])
            else:
                continue
                
            result.append(f'if (-not (Get-Command {cmd} -ErrorAction SilentlyContinue)) {{')
            result.append(f'    Write-LogMessage "Installing {cmd}..."')
            result.append(f'    try {{')
            result.append(f'        # Install command would go here')
            result.append(f'        # Example: choco install {cmd} -y')
            result.append(f'    }} catch {{')
            result.append(f'        Write-LogError "Failed to install {cmd}: $_"')
            result.append(f'    }}')
            result.append('}')
    else:
        for prereq in prerequisites:
            # Try to extract command name
            if isinstance(prereq, dict) and "name" in prereq:
                cmd = prereq["name"]
            elif isinstance(prereq, str):
                words = prereq.split()
                cmd = next((word for word in words if not word.startswith("-")), words[0])
            else:
                continue
                
            result.append(f'if ! command -v {cmd} &> /dev/null; then')
            result.append(f'    log_message "Installing {cmd}..."')
            result.append(f'    $INSTALL_CMD {cmd} || {{ log_error "Failed to install {cmd}"; exit 1; }}')
            result.append('fi')
                
    return "\n".join(result)

def build_verification_steps(verification_steps: list, os_type: str) -> str:
    """Build verification steps from list."""
    if not verification_steps:
        return "# No verification steps provided"
        
    result = []
    if os_type.lower() in ["windows", "win32", "win"]:
        for i, step in enumerate(verification_steps, 1):
            if isinstance(step, dict) and "command" in step:
                command = step["command"]
            elif isinstance(step, str):
                command = step
            else:
                continue
                
            result.append(f'Write-LogMessage "Verification step {i}: {command}"')
            result.append(f'try {{')
            result.append(f'    {command}')
            result.append(f'    if ($LASTEXITCODE -ne 0) {{')
            result.append(f'        Write-LogError "Verification step {i} failed"')
            result.append(f'        return $false')
            result.append(f'    }}')
            result.append(f'}} catch {{')
            result.append(f'    Write-LogError "Verification step {i} failed: $_"')
            result.append(f'    return $false')
            result.append(f'}}')
        result.append('return $true')
    else:
        for i, step in enumerate(verification_steps, 1):
            if isinstance(step, dict) and "command" in step:
                command = step["command"]
            elif isinstance(step, str):
                command = step
            else:
                continue
                
            result.append(f'log_message "Verification step {i}: {command}"')
            result.append(f'{command}')
            result.append('if [ $? -ne 0 ]; then')
            result.append(f'    log_error "Verification step {i} failed"')
            result.append('    return 1')
            result.append('fi')
        result.append('return 0')
                
    return "\n".join(result)