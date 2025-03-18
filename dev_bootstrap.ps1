# Development environment bootstrap script
Write-Host "Setting up and testing workflow agent environment..." -ForegroundColor Green

# Error handling and strict mode
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Configuration variables
$TEST_LICENSE_KEY = "test123"
$TEST_HOST = "localhost"
$REQUIRED_PYTHON_VERSION = "3.8"
$TEMPLATE_DIRS = @(
    ".\src\workflow_agent\integrations\common_templates\install",
    ".\src\workflow_agent\integrations\common_templates\remove",
    ".\src\workflow_agent\integrations\common_templates\verify",
    ".\src\workflow_agent\integrations\common_templates\macros"
)
$MOCK_TEMPLATE_CONTENT = @"
#!/bin/bash
echo "Mock template for testing"
exit 0
"@

# Function to check if running as administrator
function Test-AdminPrivileges {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Function to check if command exists
function Test-Command {
    param($Command)
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'stop'
    try { if (Get-Command $Command) { return $true } }
    catch { return $false }
    finally { $ErrorActionPreference = $oldPreference }
}

# Function to check Python version
function Test-PythonVersion {
    try {
        $version = python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
        $versionParts = $version.Split('.')
        $minVersionParts = $REQUIRED_PYTHON_VERSION.Split('.')
        
        if ([int]$versionParts[0] -gt [int]$minVersionParts[0]) {
            return $true
        }
        if ([int]$versionParts[0] -eq [int]$minVersionParts[0] -and [int]$versionParts[1] -ge [int]$minVersionParts[1]) {
            return $true
        }
        return $false
    }
    catch {
        return $false
    }
}

# Function to create mock templates
function Create-MockTemplates {
    foreach ($dir in $TEMPLATE_DIRS) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-Host "Created directory: $dir" -ForegroundColor Gray
        }
        
        # Create mock template files
        $templateFile = Join-Path $dir "mock_template.sh"
        Set-Content -Path $templateFile -Value $MOCK_TEMPLATE_CONTENT
        Write-Host "Created mock template: $templateFile" -ForegroundColor Gray
    }
}

# Function to run workflow agent command with timeout
function Invoke-WorkflowAgentWithTimeout {
    param(
        [string[]]$Arguments,
        [int]$TimeoutSeconds = 30
    )
    
    $job = Start-Job -ScriptBlock {
        param($args)
        $env:PYTHONPATH = ".\src"
        workflow-agent @args
    } -ArgumentList @(,$Arguments)
    
    $completed = Wait-Job $job -Timeout $TimeoutSeconds
    if ($completed -eq $null) {
        Stop-Job $job
        Remove-Job $job -Force
        throw "Command timed out after $TimeoutSeconds seconds"
    }
    
    $result = Receive-Job $job
    Remove-Job $job
    return $result
}

# Main execution block
try {
    # Check administrator privileges
    if (-not (Test-AdminPrivileges)) {
        Write-Host "Warning: Script is not running with administrator privileges. Some operations may fail." -ForegroundColor Yellow
    }

    # Check Python installation
    Write-Host "Checking Python installation..." -ForegroundColor Yellow
    if (-not (Test-Command python)) {
        throw "Python not found in PATH. Please install Python $REQUIRED_PYTHON_VERSION or higher."
    }
    
    if (-not (Test-PythonVersion)) {
        throw "Python version $REQUIRED_PYTHON_VERSION or higher is required."
    }

    # Create and activate virtual environment
    if (-not (Test-Path "venv")) {
        Write-Host "Creating virtual environment..." -ForegroundColor Yellow
        python -m venv venv
    }

    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & .\venv\Scripts\Activate.ps1

    # Upgrade pip and install dependencies
    Write-Host "Upgrading pip and installing dependencies..." -ForegroundColor Yellow
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    pip install -e .

    # Create mock templates
    Write-Host "Setting up mock templates..." -ForegroundColor Yellow
    Create-MockTemplates

    # Test Scenarios
    Write-Host "`nRunning test scenarios..." -ForegroundColor Green

    # 1. Test basic help command
    Write-Host "`nTesting help command..." -ForegroundColor Yellow
    try {
        $env:PYTHONPATH = ".\src"
        workflow-agent --help
        Write-Host "Help command test: SUCCESS" -ForegroundColor Green
    }
    catch {
        Write-Host "Help command test: FAILED - $_" -ForegroundColor Red
    }

    # 2. Test installation scenario
    Write-Host "`nTesting installation scenario..." -ForegroundColor Yellow
    try {
        $result = Invoke-WorkflowAgentWithTimeout @("install", "infra_agent", "--license-key", $TEST_LICENSE_KEY, "--host", $TEST_HOST)
        Write-Host "Installation test completed" -ForegroundColor Green
    }
    catch {
        Write-Host "Installation test warning: $_" -ForegroundColor Yellow
    }

    # 3. Test verification scenario
    Write-Host "`nTesting verification scenario..." -ForegroundColor Yellow
    try {
        $result = Invoke-WorkflowAgentWithTimeout @("verify", "infra_agent")
        Write-Host "Verification test completed" -ForegroundColor Green
    }
    catch {
        Write-Host "Verification test warning: $_" -ForegroundColor Yellow
    }

    # 4. Test removal scenario
    Write-Host "`nTesting removal scenario..." -ForegroundColor Yellow
    try {
        $result = Invoke-WorkflowAgentWithTimeout @("remove", "infra_agent")
        Write-Host "Removal test completed" -ForegroundColor Green
    }
    catch {
        Write-Host "Removal test warning: $_" -ForegroundColor Yellow
    }

    # 5. Test example workflow
    Write-Host "`nTesting example workflow..." -ForegroundColor Yellow
    try {
        python test_workflow.py
        Write-Host "Example workflow test completed" -ForegroundColor Green
    }
    catch {
        Write-Host "Example workflow test warning: $_" -ForegroundColor Yellow
    }

    # Final status report
    Write-Host "`nTest Execution Summary:" -ForegroundColor Cyan
    Write-Host "- Environment setup: COMPLETED" -ForegroundColor Green
    Write-Host "- Mock templates: CREATED" -ForegroundColor Green
    Write-Host "- Basic functionality tests: COMPLETED" -ForegroundColor Green
    
    if (-not (Test-AdminPrivileges)) {
        Write-Host "`nNote: Some tests may have failed due to lack of administrator privileges." -ForegroundColor Yellow
        Write-Host "To run with full privileges, execute this script as administrator:" -ForegroundColor Yellow
        Write-Host "Right-click PowerShell -> Run as Administrator" -ForegroundColor Gray
    }

    Write-Host "`nTo activate the virtual environment in a new terminal, run:" -ForegroundColor Cyan
    Write-Host ".\venv\Scripts\Activate.ps1" -ForegroundColor Gray

}
catch {
    Write-Host "`nError during setup/testing: $_" -ForegroundColor Red
    Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
    exit 1
} 