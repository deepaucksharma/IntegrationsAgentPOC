# Infrastructure Agent Test Script
# This script demonstrates use of the refactored workflow engine

# Error handling
$ErrorActionPreference = "Stop"

# Import the module if possible
try {
    Import-Module -Name "WorkflowAgent" -ErrorAction Stop
    $moduleLoaded = $true
} catch {
    Write-Host "WorkflowAgent module not available, running as direct script." -ForegroundColor Yellow
    $moduleLoaded = $false
}

# Use the centralized configuration
$configParams = @{
    "license_key" = "test-key"
    "host" = "localhost"
    "install_dir" = "$env:USERPROFILE\InfraAgent"
    "config_path" = "$env:USERPROFILE\InfraAgent\config"
    "log_path" = "$env:USERPROFILE\InfraAgent\logs"
    "integration_type" = "infra_agent"
    "target_name" = "infrastructure-agent"
    "action" = "install"
}

# Display info banner
Write-Host "Running test for: $($configParams.integration_type)" -ForegroundColor Cyan
Write-Host "  Action: $($configParams.action)" -ForegroundColor Cyan
Write-Host "  Target: $($configParams.target_name)" -ForegroundColor Cyan
Write-Host "  Host: $($configParams.host)" -ForegroundColor Cyan
Write-Host ""

# Construct the command
$command = "python -m workflow_agent $($configParams.action) $($configParams.integration_type)"

# Add parameters
foreach ($key in $configParams.Keys) {
    # Skip action and integration_type as they're already in the command
    if ($key -ne "action" -and $key -ne "integration_type") {
        $command += " --$key `"$($configParams[$key])`""
    }
}

Write-Host "Executing command:" -ForegroundColor Green
Write-Host $command -ForegroundColor Yellow
Write-Host ""

# Execute the command
try {
    Invoke-Expression $command
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -eq 0) {
        Write-Host "Command executed successfully!" -ForegroundColor Green
    } else {
        Write-Host "Command failed with exit code: $exitCode" -ForegroundColor Red
    }
} catch {
    Write-Host "Error executing command: $_" -ForegroundColor Red
    exit 1
}
