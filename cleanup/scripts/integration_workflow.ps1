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
    
    [string]$LogPath = "C:\ProgramData\New Relic\logs"
)

# Error handling
$ErrorActionPreference = "Stop"
trap { Write-Error $_; exit 1 }

# Define directories
$ProjectRoot = $PSScriptRoot
$TemplateDir = Join-Path $ProjectRoot "templates"
$ScriptDir = Join-Path $ProjectRoot "generated_scripts"
$BackupDir = Join-Path $ProjectRoot "backup"

# Ensure directories exist
function Test-CreateDirectory($path) {
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Host "Created directory: $path"
    }
}

Test-CreateDirectory $ScriptDir
Test-CreateDirectory $BackupDir

# Load Jinja2 Template functionality through Python
function Invoke-TemplateRendering {
    param(
        [string]$Action,
        [string]$IntegrationType,
        [string]$TemplateName,
        [hashtable]$Parameters
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $outputScript = Join-Path $ScriptDir "${IntegrationType}_${Action}_${timestamp}.ps1"
    
    # Create a temporary Python script to render the template
    $tempPythonScript = Join-Path $env:TEMP "render_template_$timestamp.py"
    
    $pythonCode = @"
import os
import sys
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

# Path to templates
template_dir = r"$TemplateDir"
template_name = "$TemplateName"
env = Environment(loader=FileSystemLoader(template_dir))

# Get the template
template = env.get_template(template_name)

# Context data
context = {
    'action': '$Action',
    'target_name': 'infrastructure-agent',
    'integration_type': '$IntegrationType',
    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    'parameters': {
"@

    # Add parameters to Python script with proper escaping for Windows paths
    foreach ($key in $Parameters.Keys) {
        $value = $Parameters[$key].Replace("\", "\\")
        $pythonCode += "        '$key': '$value',`n"
    }

    $pythonCode += @"
    }
}

# Render the template
rendered = template.render(**context)

# Write to file
with open(r"$outputScript", 'w') as f:
    f.write(rendered)

print("Template rendered to: $outputScript")
"@

    # Write Python script to temp file
    Set-Content -Path $tempPythonScript -Value $pythonCode
    
    # Execute Python script
    Write-Host "Rendering template..."
    python $tempPythonScript
    
    # Clean up temp Python script
    Remove-Item -Path $tempPythonScript -Force
    
    return $outputScript
}

# Function to execute a PowerShell script
function Invoke-WorkflowScript {
    param(
        [string]$ScriptPath
    )
    
    Write-Host "Executing script: $ScriptPath" -ForegroundColor Cyan
    
    try {
        & powershell.exe -ExecutionPolicy Bypass -File $ScriptPath
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Script execution failed with exit code: $LASTEXITCODE"
            return $false
        }
        
        Write-Host "Script executed successfully!" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Error "Error executing script: $_"
        return $false
    }
}

# Main workflow execution
Write-Host "Starting $Action workflow for $IntegrationType..." -ForegroundColor Green

# Determine which template to use based on action
switch ($Action) {
    "install" {
        $templateName = "${IntegrationType}_install.ps1.j2"
        $parameters = @{
            "license_key" = $LicenseKey
            "host" = $HostName
            "port" = "8080"
            "install_dir" = $InstallDir
            "config_path" = $ConfigPath
            "log_path" = $LogPath
        }
    }
    "verify" {
        $templateName = "${IntegrationType}_verify.ps1.j2"
        $parameters = @{
            "host" = $HostName
            "port" = "8080"
            "install_dir" = $InstallDir
            "config_path" = $ConfigPath
            "log_path" = $LogPath
        }
    }
    "uninstall" {
        $templateName = "${IntegrationType}_uninstall.ps1.j2"
        $parameters = @{
            "install_dir" = $InstallDir
            "config_path" = $ConfigPath
        }
    }
}

# Render template
try {
    $scriptPath = Invoke-TemplateRendering -Action $Action -IntegrationType $IntegrationType -TemplateName $templateName -Parameters $parameters
    
    # Execute script
    $result = Invoke-WorkflowScript -ScriptPath $scriptPath
    
    if ($result) {
        Write-Host "$Action workflow completed successfully!" -ForegroundColor Green
        exit 0
    }
    else {
        Write-Host "$Action workflow failed!" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "Error during $Action workflow: $_" -ForegroundColor Red
    exit 1
}
