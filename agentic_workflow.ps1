# Agentic New Relic Integration Workflow
# This script implements a fully LLM-driven agentic workflow for New Relic integrations

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("install", "verify", "uninstall", "diagnose")]
    [string]$Action,
    
    [Parameter(Mandatory=$true)]
    [string]$IntegrationType,
    
    [string]$HostName = "localhost",
    
    [string]$LicenseKey = "YOUR_LICENSE_KEY",
    
    [string]$InstallDir,
    
    [string]$ConfigPath,
    
    [string]$LogPath,
    
    [string]$ConfigFile = "workflow_config.yaml",
    
    [string]$ModelProvider = "gemini",  # openai, gemini, anthropic
    
    [switch]$Interactive,
    
    [switch]$Debug
)

# Error handling
$ErrorActionPreference = "Stop"
trap { Write-Error $_; exit 1 }

# Define directories
$ProjectRoot = $PSScriptRoot
$ScriptDir = Join-Path $ProjectRoot "generated_scripts"
$BackupDir = Join-Path $ProjectRoot "backup"
$KnowledgeDir = Join-Path $ProjectRoot "knowledge"
$FeedbackDir = Join-Path $ProjectRoot "feedback"
$HistoryDir = Join-Path $ProjectRoot "history"

# Banner
function Show-Banner {
    Clear-Host
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                                                              ║" -ForegroundColor Cyan
    Write-Host "║   Agentic New Relic Integration Workflow                     ║" -ForegroundColor Cyan
    Write-Host "║   Powered by AI-Driven Multi-Agent System                    ║" -ForegroundColor Cyan
    Write-Host "║                                                              ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

# Ensure required directories exist
function Ensure-Directories {
    New-Item -ItemType Directory -Force -Path $ScriptDir | Out-Null
    New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
    New-Item -ItemType Directory -Force -Path $KnowledgeDir | Out-Null
    New-Item -ItemType Directory -Force -Path $FeedbackDir | Out-Null
    New-Item -ItemType Directory -Force -Path $HistoryDir | Out-Null
}

# Activate Python environment
function Activate-Environment {
    if (Test-Path (Join-Path $ProjectRoot "venv")) {
        Write-Host "Activating virtual environment..." -ForegroundColor Yellow
        & (Join-Path $ProjectRoot "venv\Scripts\Activate.ps1")
    } else {
        Write-Host "Virtual environment not found, using system Python" -ForegroundColor Yellow
    }
}

# Set Python path
function Set-PythonPath {
    $env:PYTHONPATH = $ProjectRoot
    Write-Host "Setting PYTHONPATH to: $env:PYTHONPATH" -ForegroundColor Yellow
}

# Create parameter dictionary for the workflow agent
function Get-WorkflowParameters {
    $params = @{
        "action" = $Action
        "integration_type" = $IntegrationType
        "host" = $HostName
        "target_name" = "$IntegrationType-integration"
    }
    
    # Add optional parameters if provided
    if ($LicenseKey -ne "YOUR_LICENSE_KEY") {
        $params["license_key"] = $LicenseKey
    }
    
    if ($InstallDir) {
        $params["install_dir"] = $InstallDir
    }
    
    if ($ConfigPath) {
        $params["config_path"] = $ConfigPath
    }
    
    if ($LogPath) {
        $params["log_path"] = $LogPath
    }
    
    return $params
}

# Run the workflow agent
function Invoke-WorkflowAgent {
    $params = Get-WorkflowParameters
    $paramString = $params.Keys | ForEach-Object { "--$_ `"$($params[$_])`"" } | Join-String -Separator " "
    
    if ($Debug) {
        $paramString += " --debug"
    }
    
    Write-Host "Running workflow agent with parameters: $paramString" -ForegroundColor Green
    
    # Set environment variables
    $env:MODEL_PROVIDER = $ModelProvider
    
    # Execute Python module
    $command = "python -m workflow_agent $Action $IntegrationType"
    
    # Add appropriate parameters
    if ($LicenseKey -ne "YOUR_LICENSE_KEY") {
        $command += " --license-key `"$LicenseKey`""
    }
    
    $command += " --host `"$HostName`""
    
    if (Test-Path $ConfigFile) {
        $command += " --config-file `"$ConfigFile`""
    }
    
    Write-Host "Executing: $command" -ForegroundColor Green
    Invoke-Expression $command
}

# Main execution
function Main {
    Show-Banner
    Ensure-Directories
    Activate-Environment
    Set-PythonPath
    
    Write-Host "Starting $Action workflow for $IntegrationType integration..." -ForegroundColor Cyan
    
    try {
        Invoke-WorkflowAgent
        Write-Host "Workflow completed successfully." -ForegroundColor Green
    }
    catch {
        Write-Host "Error executing workflow: $_" -ForegroundColor Red
        exit 1
    }
}

# Run the script
Main