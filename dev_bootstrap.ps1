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

# More realistic mock template content
$MOCK_TEMPLATE_CONTENT = @"
#!/bin/bash
set -e

# Common functions
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

# Prerequisites check
check_prerequisites() {
    log_message "Checking prerequisites..."
    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed"
        exit 1
    fi
    if ! command -v jq &> /dev/null; then
        log_error "jq is required but not installed"
        exit 1
    fi
}

# Installation steps
install() {
    log_message "Starting installation..."
    check_prerequisites
    
    # Download and install
    log_message "Downloading package..."
    curl -sL https://example.com/package.tar.gz -o /tmp/package.tar.gz
    
    log_message "Extracting package..."
    tar xzf /tmp/package.tar.gz -C /opt
    
    # Configure
    log_message "Configuring..."
    cat > /etc/config.json << EOF
{
    "license_key": "{{ license_key }}",
    "host": "{{ host }}",
    "port": {{ port }},
    "log_level": "{{ log_level }}"
}
EOF
    
    # Start service
    log_message "Starting service..."
    systemctl enable service-name
    systemctl start service-name
    
    # Cleanup
    rm -f /tmp/package.tar.gz
}

# Verification steps
verify() {
    log_message "Verifying installation..."
    
    # Check service status
    if ! systemctl is-active --quiet service-name; then
        log_error "Service is not running"
        exit 1
    fi
    
    # Check configuration
    if ! jq -e '.license_key' /etc/config.json > /dev/null; then
        log_error "Invalid configuration"
        exit 1
    fi
    
    # Check connectivity
    if ! curl -s http://localhost:{{ port }}/health > /dev/null; then
        log_error "Service is not responding"
        exit 1
    fi
    
    log_message "Verification successful"
}

# Main execution
case "$1" in
    install)
        install
        ;;
    verify)
        verify
        ;;
    *)
        log_error "Unknown command: $1"
        exit 1
        ;;
esac

log_message "Operation completed successfully"
"@

# Function to clean up mock templates
function Remove-MockTemplates {
    foreach ($dir in $TEMPLATE_DIRS) {
        $templateFile = Join-Path $dir "mock_template.sh"
        if (Test-Path $templateFile) {
            Remove-Item -Path $templateFile -Force
            Write-Host "Removed mock template: $templateFile" -ForegroundColor Gray
        }
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

    # Clean up mock templates after tests
    Write-Host "`nCleaning up mock templates..." -ForegroundColor Yellow
    Remove-MockTemplates
    
}
catch {
    # Clean up mock templates on error
    Write-Host "`nCleaning up mock templates after error..." -ForegroundColor Yellow
    Remove-MockTemplates
    throw
} 