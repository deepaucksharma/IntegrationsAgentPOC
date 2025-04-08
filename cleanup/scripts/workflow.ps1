# IntegrationsAgentPOC Workflow PowerShell Script
# This script provides a comprehensive workflow for installing, verifying, and uninstalling integrations

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("install", "verify", "uninstall")]
    [string]$Action,
    
    [Parameter(Mandatory=$true)]
    [string]$IntegrationType = "infra_agent",
    
    [string]$HostName = "localhost",
    
    [string]$LicenseKey = "YOUR_LICENSE_KEY",
    
    [string]$ConfigFile = "workflow_config.yaml",
    
    [string]$InstallDir = "C:\Program Files\New Relic",
    
    [string]$ConfigPath = "C:\ProgramData\New Relic",
    
    [string]$LogPath = "C:\ProgramData\New Relic\logs",
    
    [switch]$ShowDetails
)

# Error handling
$ErrorActionPreference = "Stop"
trap { Write-Error $_; exit 1 }

# Define directories
$ProjectRoot = $PSScriptRoot
$ScriptDir = Join-Path $ProjectRoot "generated_scripts"
$BackupDir = Join-Path $ProjectRoot "backup"

# Detailed logging function
function Write-DetailLog {
    param([string]$Message)
    
    if ($ShowDetails) {
        Write-Host $Message -ForegroundColor Cyan
    }
}

# Ensure directories exist
function Test-CreateDirectory($path) {
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Host "Created directory: $path"
    }
}

Test-CreateDirectory $ScriptDir
Test-CreateDirectory $BackupDir

# Create an environment variables dictionary for the Python scripts
$env:NR_LICENSE_KEY = $LicenseKey
$env:NR_HOST = $HostName
$env:NR_INSTALL_DIR = $InstallDir
$env:NR_CONFIG_PATH = $ConfigPath
$env:NR_LOG_PATH = $LogPath

# Function to create dynamic scripts
function New-IntegrationScript {
    param(
        [string]$ScriptName,
        [string]$TemplateName,
        [hashtable]$Parameters
    )
    
    $scriptPath = Join-Path $ProjectRoot $ScriptName
    $templateContent = @"
"""
$TemplateName script for $IntegrationType integration.
"""
import os
import sys
import asyncio
import logging
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def render_and_execute_template():
    """Render the template and execute it directly."""
    try:
        # Path to templates
        project_root = Path(__file__).parent
        template_dir = project_root / 'templates'
        env = Environment(loader=FileSystemLoader(template_dir))
        
        # Load template
        template = env.get_template('$TemplateName')
        
        # Define parameters for the template
        params = {
            "license_key": os.environ.get('NR_LICENSE_KEY', 'YOUR_LICENSE_KEY'),
            "host": os.environ.get('NR_HOST', 'localhost'),
            "port": "8080",
            "install_dir": os.environ.get('NR_INSTALL_DIR', 'C:\\Program Files\\New Relic'),
            "config_path": os.environ.get('NR_CONFIG_PATH', 'C:\\ProgramData\\New Relic'),
            "log_path": os.environ.get('NR_LOG_PATH', 'C:\\ProgramData\\New Relic\\logs')
        }
        
        # Define template context
        context = {
            'action': '$Action',
            'target_name': 'infrastructure-agent',
            'integration_type': '$IntegrationType',
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'parameters': params
        }
        
        # Render the template
        logger.info("Rendering template...")
        rendered = template.render(**context)
        
        # Write the rendered script to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".ps1", delete=False, mode='w') as temp:
            temp_path = temp.name
            temp.write(rendered)
            logger.info(f"Rendered script written to: {temp_path}")
        
        # Execute the script
        logger.info("Executing script...")
        cmd = f'powershell.exe -ExecutionPolicy Bypass -File "{temp_path}"'
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            shell=True,
            text=True
        )
        
        # Process output
        stdout, stderr = process.communicate()
        
        logger.info("Script execution complete.")
        logger.info(f"Exit code: {process.returncode}")
        
        if stdout:
            print("\nScript Output:")
            print("-" * 50)
            print(stdout)
        
        if stderr:
            print("\nScript Errors:")
            print("-" * 50)
            print(stderr)
            
        if process.returncode != 0:
            logger.error("Script execution failed.")
            return False
        
        logger.info("Script executed successfully!")
        return True
            
    except Exception as e:
        logger.error(f"Error during execution: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    # Check if running on Windows
    if os.name != 'nt':
        logger.error("This script must be run on Windows.")
        sys.exit(1)
        
    logger.info("Starting workflow execution...")
    result = asyncio.run(render_and_execute_template())
    
    if result:
        logger.info("Workflow completed successfully!")
        sys.exit(0)
    else:
        logger.error("Workflow failed!")
        sys.exit(1)
"@

    Set-Content -Path $scriptPath -Value $templateContent
    Write-DetailLog "Created script: $scriptPath"
    return $scriptPath
}

# Main workflow execution
Write-Host "Starting $Action workflow for $IntegrationType..." -ForegroundColor Green

# Create appropriate script based on action
switch ($Action) {
    "install" {
        $scriptName = "dynamic_install.py"
        $templateName = "${IntegrationType}_install.ps1.j2"
        $parameters = @{
            "license_key" = "NR_LICENSE_KEY"
            "host" = "NR_HOST" 
            "port" = "'8080'"
            "install_dir" = "NR_INSTALL_DIR"
            "config_path" = "NR_CONFIG_PATH"
            "log_path" = "NR_LOG_PATH"
        }
    }
    "verify" {
        $scriptName = "dynamic_verify.py"
        $templateName = "${IntegrationType}_verify.ps1.j2"
        $parameters = @{
            "host" = "NR_HOST"
            "port" = "'8080'"
            "install_dir" = "NR_INSTALL_DIR"
            "config_path" = "NR_CONFIG_PATH"
            "log_path" = "NR_LOG_PATH"
        }
    }
    "uninstall" {
        $scriptName = "dynamic_uninstall.py"
        $templateName = "${IntegrationType}_uninstall.ps1.j2"
        $parameters = @{
            "install_dir" = "NR_INSTALL_DIR"
            "config_path" = "NR_CONFIG_PATH"
        }
    }
}

# Generate the dynamic script
$scriptPath = New-IntegrationScript -ScriptName $scriptName -TemplateName $templateName -Parameters $parameters

# Execute the script
Write-Host "Running $Action workflow..." -ForegroundColor Yellow
python $scriptPath

if ($LASTEXITCODE -eq 0) {
    Write-Host "$Action workflow completed successfully!" -ForegroundColor Green
    exit 0
}
else {
    Write-Host "$Action workflow failed with exit code: $LASTEXITCODE" -ForegroundColor Red
    exit 1
}
