# New Relic Integration Workflow PowerShell Script
# This script generates, runs, and verifies integration scripts using New Relic documentation

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("install", "verify", "uninstall", "generate-only")]
    [string]$Action,
    
    [Parameter(Mandatory=$true)]
    [string]$IntegrationType,
    
    [string]$HostName = "localhost",
    
    [string]$LicenseKey = "YOUR_LICENSE_KEY",
    
    [string]$InstallDir = "C:\Program Files\New Relic",
    
    [string]$ConfigPath = "C:\ProgramData\New Relic",
    
    [string]$LogPath = "C:\ProgramData\New Relic\logs",
    
    [string]$ConfigFile = "workflow_config.yaml",
    
    [switch]$UseLLM,
    
    [switch]$ShowDetails
)

# Error handling
$ErrorActionPreference = "Stop"
trap { Write-Error $_; exit 1 }

# Define directories
$ProjectRoot = $PSScriptRoot
$ScriptDir = Join-Path $ProjectRoot "generated_scripts"
$BackupDir = Join-Path $ProjectRoot "backup"
$KnowledgeDir = Join-Path $ProjectRoot "knowledge"

# Detailed logging function
function Write-DetailLog {
    param([string]$Message)
    
    if ($ShowDetails) {
        Write-Host $Message -ForegroundColor Cyan
    }
}

# Ensure directories exist
function Test-CreateDirectory($path) {
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Host "Created directory: $path"
    }
}

Test-CreateDirectory $ScriptDir
Test-CreateDirectory $BackupDir
Test-CreateDirectory $KnowledgeDir

# Set environment variables for Python scripts
$env:NR_LICENSE_KEY = $LicenseKey
$env:NR_HOST = $HostName
$env:NR_INSTALL_DIR = $InstallDir
$env:NR_CONFIG_PATH = $ConfigPath
$env:NR_LOG_PATH = $LogPath
$env:USE_LLM = if ($UseLLM) { "true" } else { "false" }

# Function to create a Python script that will fetch New Relic documentation and generate installation scripts
function New-DocumentationScript {
    param(
        [string]$ScriptName,
        [string]$IntegrationType,
        [string]$Action
    )
    
    $scriptPath = Join-Path $ProjectRoot $ScriptName
    $templateContent = @"
"""
Script to fetch New Relic documentation and generate $Action scripts for $IntegrationType integration.
"""
import os
import sys
import asyncio
import logging
import json
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import LLM modules if requested
use_llm = os.environ.get('USE_LLM', 'false').lower() == 'true'
if use_llm:
    try:
        logger.info("Attempting to import LLM modules...")
        from workflow_agent.llm.documentation_parser import DocumentationParser
        from workflow_agent.llm.script_generator import LLMScriptGenerator
        llm_available = True
        logger.info("LLM modules successfully imported")
    except ImportError as e:
        logger.warning(f"Could not import LLM modules: {e}")
        llm_available = False
else:
    llm_available = False

async def fetch_documentation():
    """Fetch New Relic documentation for the specified integration."""
    integration_type = "$IntegrationType"
    logger.info(f"Fetching documentation for {integration_type} integration...")
    
    # Path to knowledge directory
    knowledge_dir = Path(r"$KnowledgeDir")
    knowledge_file = knowledge_dir / f"{integration_type}_documentation.json"
    
    # Check if we already have documentation cached
    if knowledge_file.exists():
        logger.info(f"Using cached documentation from {knowledge_file}")
        with open(knowledge_file, 'r') as f:
            return json.load(f)
    
    # If LLM is available, use it to fetch and parse documentation
    if llm_available:
        logger.info("Using LLM to fetch and parse documentation")
        parser = DocumentationParser()
        doc_data = await parser.fetch_and_parse(integration_type)
        
        # Cache the documentation
        with open(knowledge_file, 'w') as f:
            json.dump(doc_data, f, indent=2)
            
        return doc_data
    else:
        # Otherwise use pre-defined documentation templates
        logger.info("Using pre-defined documentation templates")
        return {
            "name": integration_type,
            "description": f"New Relic {integration_type} integration",
            "parameters": {
                "license_key": {"description": "New Relic license key", "required": True},
                "host": {"description": "Host where the integration will be installed", "required": True},
                "port": {"description": "Port for the integration", "required": False, "default": "8080"},
                "install_dir": {"description": "Installation directory", "required": True},
                "config_path": {"description": "Configuration directory", "required": True},
                "log_path": {"description": "Log directory", "required": False}
            },
            "installation_steps": [
                "Create installation directory",
                "Create configuration directory",
                "Create log directory",
                "Generate configuration file",
                "Start the integration service"
            ],
            "verification_steps": [
                "Check if installation directory exists",
                "Check if configuration file exists",
                "Check if service is running"
            ],
            "uninstallation_steps": [
                "Stop the integration service",
                "Remove configuration files",
                "Remove installation files"
            ]
        }

async def generate_script_from_documentation():
    """Generate script from New Relic documentation."""
    try:
        # Fetch documentation
        doc_data = await fetch_documentation()
        logger.info(f"Documentation fetched for {doc_data['name']}")
        
        # Define parameters for the template based on documentation
        params = {
            "license_key": os.environ.get('NR_LICENSE_KEY', 'YOUR_LICENSE_KEY'),
            "host": os.environ.get('NR_HOST', 'localhost'),
            "port": "8080",
            "install_dir": os.environ.get('NR_INSTALL_DIR', 'C:\\Program Files\\New Relic'),
            "config_path": os.environ.get('NR_CONFIG_PATH', 'C:\\ProgramData\\New Relic'),
            "log_path": os.environ.get('NR_LOG_PATH', 'C:\\ProgramData\\New Relic\\logs')
        }
        
        # If LLM is available, use it to generate script
        if llm_available and use_llm:
            logger.info("Using LLM to generate script")
            generator = LLMScriptGenerator()
            script_content = await generator.generate_script(
                doc_data, 
                "$Action", 
                params
            )
        else:
            # Otherwise use templates
            logger.info("Using templates to generate script")
            template_dir = Path(r"$ProjectRoot") / "templates"
            env = Environment(loader=FileSystemLoader(template_dir))
            
            # For generate-only, use the install template
            action_type = 'install' if os.environ.get('ACTION') == 'generate-only' else os.environ.get('ACTION')
            
            # Force use of our new template
            template_name = "nr_infra_agent_install.ps1.j2"
            logger.info(f"Using template: {template_name}")
                
            template = env.get_template(template_name)
            
            # Define template context
            context = {
                'action': '$Action',
                'target_name': 'infrastructure-agent',
                'integration_type': doc_data['name'],
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'parameters': params,
                'documentation': doc_data
            }
            
            # Render the template
            script_content = template.render(**context)
        
        # Generate timestamp for the script filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        script_filename = f"{doc_data['name']}_{os.environ.get('ACTION', 'install')}_{timestamp}.ps1"
        script_path = Path(r"$ScriptDir") / script_filename
        
        # Write the script to file
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        logger.info(f"Script generated and saved to {script_path}")
        
        # If generate-only, don't execute
        if os.environ.get('ACTION') == 'generate-only':
            return str(script_path)
            
        # Execute the script
        if os.environ.get('ACTION') in ['install', 'verify', 'uninstall']:
            logger.info(f"Executing {os.environ.get('ACTION')} script...")
            
            # Execute the script
            cmd = f'powershell.exe -ExecutionPolicy Bypass -File "{script_path}"'
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                shell=True,
                text=True
            )
            
            # Process output
            stdout, stderr = process.communicate()
            
            logger.info(f"Script execution complete with exit code: {process.returncode}")
            
            if stdout:
                print("\nScript Output:")
                print("-" * 50)
                print(stdout)
            
            if stderr:
                print("\nScript Errors:")
                print("-" * 50)
                print(stderr)
                
            if process.returncode != 0:
                logger.error("Script execution failed.")
                return None
            
            logger.info("Script executed successfully!")
            return str(script_path)
        
        return str(script_path)
                
    except Exception as e:
        logger.error(f"Error generating script: {str(e)}", exc_info=True)
        return None

if __name__ == "__main__":
    # Check if running on Windows
    if os.name != 'nt':
        logger.error("This script must be run on Windows.")
        sys.exit(1)
        
    # Set action from environment
    os.environ['ACTION'] = "$Action"
    
    logger.info(f"Starting {os.environ.get('ACTION')} workflow for {os.environ.get('INTEGRATION_TYPE', '$IntegrationType')}")
    script_path = asyncio.run(generate_script_from_documentation())
    
    if script_path:
        logger.info(f"Workflow completed successfully. Script generated: {script_path}")
        sys.exit(0)
    else:
        logger.error("Workflow failed!")
        sys.exit(1)
"@

    Set-Content -Path $scriptPath -Value $templateContent
    Write-DetailLog "Created script: $scriptPath"
    return $scriptPath
}

# Main workflow execution
Write-Host "Starting $Action workflow for $IntegrationType..." -ForegroundColor Green

# Set environment variables
$env:INTEGRATION_TYPE = $IntegrationType
$env:ACTION = $Action
$env:CONFIG_FILE = $ConfigFile

# Create documentation script
$scriptPath = New-DocumentationScript -ScriptName "nr_documentation_script.py" -IntegrationType $IntegrationType -Action $Action

# Execute the script
Write-Host "Fetching documentation and generating script for $IntegrationType..." -ForegroundColor Yellow

# Add LLM message if enabled
if ($UseLLM) {
    Write-Host "Using LLM to enhance script generation based on New Relic documentation" -ForegroundColor Cyan
}

python $scriptPath

if ($LASTEXITCODE -eq 0) {
    switch ($Action) {
        "generate-only" {
            Write-Host "Script generation completed successfully!" -ForegroundColor Green
            Write-Host "Check the generated_scripts directory for the output script." -ForegroundColor Green
        }
        default {
            Write-Host "$Action workflow completed successfully!" -ForegroundColor Green
        }
    }
    exit 0
}
else {
    Write-Host "$Action workflow failed with exit code: $LASTEXITCODE" -ForegroundColor Red
    exit 1
}
