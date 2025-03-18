# Development environment bootstrap script
Write-Host "Setting up development environment..." -ForegroundColor Green

# Error handling
$ErrorActionPreference = "Stop"

# Function to check if command exists
function Test-Command {
    param($Command)
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'stop'
    try { if (Get-Command $Command) { return $true } }
    catch { return $false }
    finally { $ErrorActionPreference = $oldPreference }
}

# Check Python installation
Write-Host "Checking Python installation..." -ForegroundColor Yellow
if (-not (Test-Command python)) {
    Write-Host "Python not found in PATH. Please install Python 3.8 or higher." -ForegroundColor Red
    exit 1
}

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
pip install -e .

# Create necessary directories
Write-Host "Setting up project directories..." -ForegroundColor Yellow
$directories = @(
    ".\plugins",
    ".\src\workflow_agent\integrations\common_templates\install",
    ".\src\workflow_agent\integrations\common_templates\remove",
    ".\src\workflow_agent\integrations\common_templates\verify",
    ".\src\workflow_agent\integrations\common_templates\macros"
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Created directory: $dir" -ForegroundColor Gray
    }
}

# Test the installation
Write-Host "Testing workflow-agent installation..." -ForegroundColor Yellow
try {
    $env:PYTHONPATH = ".\src"
    workflow-agent --help
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`nSetup completed successfully!" -ForegroundColor Green
        Write-Host "`nYou can now use the following commands:" -ForegroundColor Cyan
        Write-Host "workflow-agent install infra_agent --license-key=YOUR_KEY --host=YOUR_HOST" -ForegroundColor Gray
        Write-Host "workflow-agent remove infra_agent" -ForegroundColor Gray
        Write-Host "workflow-agent verify infra_agent" -ForegroundColor Gray
    } else {
        Write-Host "`nSetup completed but workflow-agent test failed. Please check the error messages above." -ForegroundColor Yellow
    }
} catch {
    Write-Host "`nError testing workflow-agent: $_" -ForegroundColor Red
}

Write-Host "`nTo activate the virtual environment in a new terminal, run:" -ForegroundColor Cyan
Write-Host ".\venv\Scripts\Activate.ps1" -ForegroundColor Gray 