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

# Create workflow configuration
$WORKFLOW_CONFIG = @"
# Workflow Agent Configuration

# Logging Configuration
log_level: "DEBUG"
log_file: "workflow_agent.log"

# Integration Configuration
template_dir: "./templates"
storage_dir: "./storage"
plugin_dirs: 
  - "./plugins"

# LLM Configuration
llm_provider: "gemini"
gemini_api_key: "AIzaSyAyGoywP_4dr5fWFi8LjR6ZV6gyk7HuAME"

# Execution Configuration
use_recovery: true
max_retries: 3
timeout_seconds: 300
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

# Function to run a test suite with proper formatting
function Invoke-TestSuite {
    param(
        [string]$Name,
        [scriptblock]$TestBlock
    )
    Write-Host "`nRunning ${Name}..." -ForegroundColor Yellow
    try {
        & $TestBlock
        Write-Host "${Name}: SUCCESS" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "${Name}: FAILED - $_" -ForegroundColor Red
        Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
        return $false
    }
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

    # Clean up any existing installations
    Write-Host "Cleaning up existing installations..." -ForegroundColor Yellow
    pip uninstall -y workflow-agent

    # Install dependencies
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    pip install -e ".[llm]"

    # Create configuration
    Write-Host "Creating workflow configuration..." -ForegroundColor Yellow
    Set-Content -Path "workflow_config.yaml" -Value $WORKFLOW_CONFIG
    Write-Host "Configuration saved to workflow_config.yaml" -ForegroundColor Gray

    # Create required directories
    Write-Host "Creating required directories..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "templates" -Force | Out-Null
    New-Item -ItemType Directory -Path "storage" -Force | Out-Null
    New-Item -ItemType Directory -Path "plugins" -Force | Out-Null

    # Create mock templates
    Write-Host "Setting up mock templates..." -ForegroundColor Yellow
    Create-MockTemplates

    # Initialize test results tracking
    $testResults = @{}

    # Test Suites
    Write-Host "`nRunning test suites..." -ForegroundColor Green

    # Set Python path for all tests
    $env:PYTHONPATH = (Resolve-Path ".\src").Path

    # 1. Basic Functionality Tests
    $testResults["Basic Help"] = Invoke-TestSuite "Basic Help Command" {
        python -m workflow_agent --help
    }

    # 2. Core Workflow Tests
    $testResults["Installation"] = Invoke-TestSuite "Installation Workflow" {
        python -m workflow_agent install infra_agent --license-key $TEST_LICENSE_KEY --host $TEST_HOST
    }

    $testResults["Verification"] = Invoke-TestSuite "Verification Workflow" {
        python -m workflow_agent verify infra_agent --host $TEST_HOST
    }

    $testResults["Removal"] = Invoke-TestSuite "Removal Workflow" {
        python -m workflow_agent remove infra_agent --host $TEST_HOST
    }

    # 3. LLM Workflow Tests
    $testResults["LLM Workflows"] = Invoke-TestSuite "LLM Workflow Tests" {
        python test_llm_workflows.py
    }

    # 4. Example Workflow
    $testResults["Example Workflow"] = Invoke-TestSuite "Example Workflow" {
        python test_workflow.py
    }

    # Final status report
    Write-Host "`nTest Execution Summary:" -ForegroundColor Cyan
    Write-Host "Environment Setup:" -ForegroundColor White
    Write-Host "- Python environment: READY" -ForegroundColor Green
    Write-Host "- Dependencies: INSTALLED" -ForegroundColor Green
    Write-Host "- Configuration: CREATED" -ForegroundColor Green
    Write-Host "- Mock templates: CREATED" -ForegroundColor Green

    Write-Host "`nTest Results:" -ForegroundColor White
    foreach ($test in $testResults.Keys) {
        $status = if ($testResults[$test]) { "SUCCESS" } else { "FAILED" }
        $color = if ($testResults[$test]) { "Green" } else { "Red" }
        Write-Host "- $test : $status" -ForegroundColor $color
    }
    
    if (-not (Test-AdminPrivileges)) {
        Write-Host "`nNote: Some tests may have failed due to lack of administrator privileges." -ForegroundColor Yellow
        Write-Host "To run with full privileges, execute this script as administrator:" -ForegroundColor Yellow
        Write-Host "Right-click PowerShell -> Run as Administrator" -ForegroundColor Gray
    }

    Write-Host "`nTo activate the virtual environment in a new terminal, run:" -ForegroundColor Cyan
    Write-Host ".\venv\Scripts\Activate.ps1" -ForegroundColor Gray

    # Check if any tests failed
    if ($testResults.Values -contains $false) {
        Write-Host "`nWarning: Some tests failed. Please review the output above." -ForegroundColor Yellow
        exit 1
    }
    else {
        Write-Host "`nAll tests completed successfully!" -ForegroundColor Green
    }
}
catch {
    Write-Host "`nError during setup/testing: $_" -ForegroundColor Red
    Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
    exit 1
} 