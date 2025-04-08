# Infrastructure Agent Installation Template

# Error handling
$ErrorActionPreference = "Stop"

# Output information
Write-Host "Installing infra_agent-integration"
Write-Host "Integration type: infra_agent"
Write-Host "License Key: test-key"
Write-Host "Host: localhost"

# Set default values for parameters with user-accessible paths
$InstallDir = "$env:USERPROFILE\InfraAgent"
$ConfigPath = "$env:USERPROFILE\InfraAgent\config" 
$LogPath = "$env:USERPROFILE\InfraAgent\logs"
$Port = "8765"

# Create directories
New-Item -ItemType Directory -Force -Path "$InstallDir" | Out-Null
New-Item -ItemType Directory -Force -Path "$ConfigPath" | Out-Null
New-Item -ItemType Directory -Force -Path "$LogPath" | Out-Null

# Write configuration
$config = @{
    "license_key" = "test-key"
    "host" = "localhost"
    "port" = "$Port"
    "log_level" = "INFO"
}

$configJson = $config | ConvertTo-Json
Set-Content -Path "$ConfigPath\config.json" -Value $configJson

# Installation process
Write-Host "Installing infrastructure agent..."
Write-Host "Installation directory: $InstallDir"
Write-Host "Configuration path: $ConfigPath"
Write-Host "Log path: $LogPath"

# Simulate installation
Start-Sleep -Seconds 1
Write-Host "Downloading agent package..."
Start-Sleep -Seconds 1
Write-Host "Installing agent package..."
Start-Sleep -Seconds 1
Write-Host "Configuring agent..."

# Report changes for tracking and rollback
Write-Host "CHANGE_JSON_BEGIN"
Write-Host @"
{
  "type": "file_create",
  "target": "$ConfigPath\\config.json",
  "revertible": true,
  "backup_file": null
}
"@
Write-Host "CHANGE_JSON_END"

Write-Host "CHANGE_JSON_BEGIN"
Write-Host @"
{
  "type": "directory_create",
  "target": "$InstallDir",
  "revertible": true,
  "backup_file": null
}
"@
Write-Host "CHANGE_JSON_END"

Write-Host "Infrastructure agent installed successfully"
# Exit with success code
exit 0
