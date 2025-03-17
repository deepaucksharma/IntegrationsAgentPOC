import os
import sys
import json
import yaml
import typer
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from ..agent import WorkflowAgent
from ..config.schemas import parameter_schemas
from ..config.configuration import WorkflowConfiguration
from ..storage import get_execution_history, get_execution_statistics, clear_history
from .. import __version__

# Load environment variables
load_dotenv()

app = typer.Typer(
    name="workflow-agent",
    help="CLI for orchestrating multi-step workflows with AI-driven adaptation"
)
console = Console()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, console=console)]
)
logger = logging.getLogger("workflow-cli")

# Banner text
BANNER = (
    "\n"
    "╭───────────────────────────────────────────────╮\n"
    "│                                               │\n"
    "│   Workflow Agent " + __version__ + "                       │\n"
    "│   Multi-step Workflow Orchestration Tool      │\n"
    "│                                               │\n"
    "╰───────────────────────────────────────────────╯\n"
)

def load_config(file_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from file."""
    if file_path and os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    return {}

@app.command()
def version():
    """Display version information."""
    console.print(BANNER)
    console.print("For more information, visit: https://github.com/yourusername/workflow-agent")

@app.command()
def list_actions():
    """List available actions and targets."""
    console.print(BANNER)
    
    console.print("\n[bold]Available actions:[/bold]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Action")
    table.add_column("Description")
    
    actions = {
        "install": "Install an integration",
        "remove": "Remove an integration",
        "update": "Update an integration",
        "verify": "Verify an integration",
        "configure": "Configure an integration",
        "test": "Test an integration",
        "backup": "Backup integration data",
        "restore": "Restore integration data",
        "status": "Check integration status",
    }
    
    for action, desc in actions.items():
        table.add_row(action, desc)
    
    console.print(table)

@app.command()
def list_integrations():
    """List available integration types."""
    console.print(BANNER)
    
    console.print("\n[bold]Available Integration Types:[/bold]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Type")
    table.add_column("Description")
    
    integrations = {
        "infra_agent": "Infrastructure monitoring agent",
        "aws": "Amazon Web Services integration",
        "azure": "Microsoft Azure integration",
        "gcp": "Google Cloud Platform integration",
        "apm": "Application Performance Monitoring",
        "browser": "Browser-based monitoring",
        "custom": "Custom integration",
    }
    
    for integration, desc in integrations.items():
        table.add_row(integration, desc)
    
    console.print(table)

if __name__ == "__main__":
    app()
