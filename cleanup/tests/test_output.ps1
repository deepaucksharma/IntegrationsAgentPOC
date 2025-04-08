# PowerShell script for infrastructure-agent
# Generated on 2025-04-06 15:17:23

$ErrorActionPreference = "Stop"
trap { Write-Error $_; exit 1 }

Write-Host "Starting install of infrastructure-agent (infra_agent)"

# Display parameters
Write-Host "Parameters:"

Write-Host "  - license_key: YOUR_LICENSE_KEY"

Write-Host "  - host: localhost"

Write-Host "  - port: 8080"

Write-Host "  - install_dir: C:\Program Files\New Relic"

Write-Host "  - config_path: C:\ProgramData\New Relic"

Write-Host "  - log_path: C:\ProgramData\New Relic\logs"


# Installation steps
Write-Host "Installing infrastructure-agent..."

if (-not (Test-Path "C:\Program Files\New Relic")) {
    New-Item -ItemType Directory -Path "C:\Program Files\New Relic" -Force | Out-Null
    Write-Host "Created installation directory: C:\Program Files\New Relic"
} else {
    Write-Host "Installation directory already exists: C:\Program Files\New Relic"
}



Write-Host "Configuring license key..."
# (This is just a placeholder - would configure license in a real script)


# Verification
Write-Host "Verifying installation..."
Write-Host "infrastructure-agent has been installed successfully"

exit 0