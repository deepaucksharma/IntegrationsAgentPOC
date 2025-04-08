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

# Main workflow execution
Write-Host "Starting $Action workflow for $IntegrationType..." -ForegroundColor Green

# Determine which action to run
switch ($Action) {
    "install" {
        Write-Host "Running installation workflow..."
        python $ProjectRoot\standalone_workflow.py
    }
    "verify" {
        Write-Host "Running verification workflow..."
        python $ProjectRoot\verify_workflow.py
    }
    "uninstall" {
        Write-Host "Running uninstallation workflow..."
        python $ProjectRoot\uninstall_workflow.py
    }
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "$Action workflow completed successfully!" -ForegroundColor Green
    exit 0
}
else {
    Write-Host "$Action workflow failed with exit code: $LASTEXITCODE" -ForegroundColor Red
    exit 1
}
