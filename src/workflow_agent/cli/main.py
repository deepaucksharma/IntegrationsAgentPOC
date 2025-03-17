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
from ..workflow_agent.agent import WorkflowAgent
from ..workflow_agent.configuration import parameter_schemas, WorkflowConfiguration
from ..workflow_agent.history import get_execution_history, get_execution_statistics, clear_history
from ..workflow_agent import __version__

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
BANNER = """
╭───────────────────────────────────────────────╮
│                                               │
│   Workflow Agent v{version}                    │
│   Multi-step Workflow Orchestration Tool      │
│                                               │
╰───────────────────────────────────────────────╯
"""

async def load_config(file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from a file.
    
    Args:
        file_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    default_config = {
        "configurable": {
            "user_id": "cli-user",
            "model_name": "openai/gpt-3.5-turbo",
            "system_prompt": "You are a helpful workflow agent.",
            "use_isolation": False,
            "isolation_method": "docker",
            "execution_timeout": 30000,
            "skip_verification": False,
            "use_llm_optimization": False,
            "rule_based_optimization": False,
            "use_static_analysis": False,
            "async_execution": False,
            "least_privilege_execution": True
        }
    }
    
    # Check for config in standard locations if not provided
    if not file_path:
        standard_paths = [
            "./workflow_config.yaml",
            "./workflow_config.yml",
            "./workflow_config.json",
            "~/.workflow_agent/config.yaml",
            "~/.workflow_agent/config.json"
        ]
        
        for path in standard_paths:
            expanded_path = Path(path).expanduser()
            if expanded_path.exists():
                file_path = str(expanded_path)
                break
    
    if file_path:
        try:
            content = Path(file_path).expanduser().read_text()
            if file_path.endswith('.json'):
                file_config = json.loads(content)
            elif file_path.endswith('.yaml') or file_path.endswith('.yml'):
                file_config = yaml.safe_load(content)
            else:
                console.print("Unknown config file format. Attempting to parse as JSON.")
                file_config = json.loads(content)
                
            merged_config = default_config.copy()
            if "configurable" in file_config:
                merged_config["configurable"].update(file_config["configurable"])
            
            return merged_config
        except Exception as e:
            console.print(f"Error loading config: {e}")
    
    return default_config

@app.command("version")
def version_command():
    """Display version information."""
    console.print(BANNER.format(version=__version__))
    console.print("For more information, visit: https://github.com/yourusername/workflow-agent")

@app.command("list")
def list_command(
    show_examples: bool = typer.Option(False, "--examples", "-e", help="Show usage examples")
):
    """List available actions and targets."""
    console.print(BANNER.format(version=__version__))
    
    console.print("\n[bold]Available actions:[/bold]")
    console.print("  - [cyan]install[/cyan] (setup a new resource)")
    console.print("  - [cyan]remove[/cyan] (remove an existing resource)")
    console.print("  - [cyan]verify[/cyan] (check if a resource is properly configured)")
    console.print("  - [cyan]update[/cyan] (update an existing resource)")
    
    console.print("\n[bold]Supported targets:[/bold]")
    for target, schema in parameter_schemas.items():
        if target != 'default':
            console.print(f"  - [green]{target}[/green]")
            for param, details in schema.items():
                required = " [bold red](required)[/bold red]" if details.required else ""
                default_val = f" (default: {details.default})" if details.default is not None else ""
                description = f" - {details.description}" if details.description else ""
                console.print(f"    - {param}{required}: {details.type}{default_val}{description}")
    
    if show_examples:
        console.print("\n[bold]Example commands:[/bold]")
        console.print("  # Install PostgreSQL monitoring agent")
        console.print("  workflow-agent run --action install --target postgres --param db_host=localhost --param db_port=5432")
        console.print("\n  # Remove MySQL monitoring agent")
        console.print("  workflow-agent run --action remove --target mysql")
        console.print("\n  # Install with AI optimization")
        console.print("  workflow-agent run --action install --target nginx --optimize")
        console.print("\n  # Run with Docker isolation")
        console.print("  workflow-agent run --action install --target redis --use-isolation")
        console.print("\n  # Perform a dry run (generate script without executing)")
        console.print("  workflow-agent run --action install --target mysql --dry-run")

@app.command("integrations")
def list_integrations(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed integration information")
):
    """List available integration types."""
    console.print(BANNER.format(version=__version__))
    
    console.print("\n[bold]Available Integration Types:[/bold]")
    console.print("\n[bold cyan]Infrastructure Agent Integrations[/bold cyan]")
    console.print("  Use with: [green]--integration-type infra_agent[/green]")
    console.print("  Supported targets:")
    for target, schema in parameter_schemas.items():
        if target not in ["default", "aws", "azure", "gcp", "apm", "browser", "newrelic"]:
            console.print(f"    - [yellow]{target}[/yellow]")
    
    console.print("\n[bold cyan]Cloud Integrations[/bold cyan]")
    for cloud in ["aws", "azure", "gcp"]:
        if cloud in parameter_schemas:
            console.print(f"  [green]{cloud.upper()}[/green] (use with: [yellow]--integration-type {cloud}[/yellow])")
            if verbose:
                console.print("    Parameters:")
                for param, spec in parameter_schemas[cloud].items():
                    required = " [bold red](required)[/bold red]" if spec.required else ""
                    default = f" (default: {spec.default})" if spec.default is not None else ""
                    console.print(f"      - {param}{required}: {spec.description}{default}")
    
    console.print("\n[bold cyan]APM Agent Integrations[/bold cyan]")
    console.print("  Use with: [green]--integration-type apm[/green]")
    if "apm" in parameter_schemas and verbose:
        console.print("  Parameters:")
        for param, spec in parameter_schemas["apm"].items():
            required = " [bold red](required)[/bold red]" if spec.required else ""
            default = f" (default: {spec.default})" if spec.default is not None else ""
            console.print(f"    - {param}{required}: {spec.description}{default}")
    
    console.print("\n[bold cyan]Browser Monitoring Integration[/bold cyan]")
    console.print("  Use with: [green]--integration-type browser[/green]")
    if "browser" in parameter_schemas and verbose:
        console.print("  Parameters:")
        for param, spec in parameter_schemas["browser"].items():
            required = " [bold red](required)[/bold red]" if spec.required else ""
            default = f" (default: {spec.default})" if spec.default is not None else ""
            console.print(f"    - {param}{required}: {spec.description}{default}")
    
    console.print("\n[bold]Example Commands:[/bold]")
    console.print("  Infrastructure agent: workflow-agent run --target mysql --integration-type infra_agent --param license_key=YOUR_KEY")
    console.print("  Cloud integration: workflow-agent run --target aws --integration-type aws --param aws_access_key=KEY --param license_key=YOUR_KEY")
    console.print("  APM integration: workflow-agent run --target webapp --integration-type apm --param language=python --param app_name=MyApp")

@app.command("history")
def history_command(
    target_name: Optional[str] = typer.Option(None, help="Filter by target name"),
    action: Optional[str] = typer.Option(None, help="Filter by action"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of records to display"),
    user_id: Optional[str] = typer.Option(None, "--user", "-u", help="Filter by user ID")
):
    """Show execution history."""
    try:
        history = await get_execution_history(target_name, action, limit, user_id)
        if not history:
            console.print("[yellow]No history records found.[/yellow]")
            return
        
        table = Table(title="Execution History")
        table.add_column("Timestamp")
        table.add_column("Target")
        table.add_column("Action")
        table.add_column("Success")
        table.add_column("Execution Time (ms)")
        table.add_column("Error")
        
        for record in history:
            table.add_row(
                record["timestamp"],
                record["target_name"],
                record["action"],
                "[green]Yes[/green]" if record["success"] else "[red]No[/red]",
                str(record["execution_time"]),
                record.get("error_message", "") or ""
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error retrieving history: {e}[/red]")

@app.command("stats")
def stats_command(
    target_name: str = typer.Option(..., help="Target name"),
    action: str = typer.Option(..., help="Action"),
    user_id: Optional[str] = typer.Option(None, "--user", "-u", help="Filter by user ID")
):
    """Show execution statistics."""
    try:
        stats = await get_execution_statistics(target_name, action, user_id)
        if not stats:
            console.print("[yellow]No statistics found.[/yellow]")
            return
        
        table = Table(title="Execution Statistics")
        table.add_column("Metric")
        table.add_column("Value")
        
        table.add_row("Total Executions", str(stats.get("total_executions", 0)))
        table.add_row("Success Rate", f"{stats.get('success_rate', 0):.2f}")
        table.add_row("Average Execution Time (ms)", f"{stats.get('average_execution_time', 0):.2f}")
        table.add_row("Success Trend", f"{stats.get('success_trend', 0):.2f}")
        table.add_row("Last Execution", str(stats.get("last_execution", "N/A")))
        
        if "common_errors" in stats and stats["common_errors"]:
            error_table = Table(title="Common Errors")
            error_table.add_column("Error Message")
            error_table.add_column("Count")
            for error in stats["common_errors"]:
                error_table.add_row(error["message"], str(error["count"]))
            console.print(error_table)
        
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error retrieving statistics: {e}[/red]")

@app.command("clear-history")
def clear_history_command(
    target: Optional[str] = typer.Option(None, "--target", "-t", help="Target resource to clear history for"),
    action: Optional[str] = typer.Option(None, "--action", "-a", help="Action to clear history for"),
    days: Optional[int] = typer.Option(None, "--days", "-d", help="Remove records older than this many days"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    all_records: bool = typer.Option(False, "--all", help="Clear all history records")
):
    """Clear execution history records."""
    scope = []
    if target:
        scope.append(f"target '{target}'")
    if action:
        scope.append(f"action '{action}'")
    if days:
        scope.append(f"older than {days} days")
    
    if all_records:
        scope = ["ALL RECORDS"]
        target = None
        action = None
    
    scope_str = " for " + " and ".join(scope) if scope else ""
    
    if not force:
        confirmed = typer.confirm(f"Are you sure you want to clear execution history{scope_str}?")
        if not confirmed:
            console.print("Operation cancelled.")
            return
    
    try:
        count = await clear_history(target, action, days)
        console.print(f"Cleared {count} execution records{scope_str}.")
    except Exception as e:
        console.print(f"[red]Error clearing history: {e}[/red]")

@app.command("configure")
def configure_command(
    output: str = typer.Option(None, "--output", "-o", help="Output configuration to file"),
    show: bool = typer.Option(False, "--show", help="Show current configuration")
):
    """Create or update configuration interactively."""
    # Default configuration
    default_config = {
        "configurable": {
            "user_id": "cli-user",
            "template_dir": "./templates",
            "custom_template_dir": None,
            "use_isolation": False,
            "isolation_method": "docker",
            "execution_timeout": 30000,
            "skip_verification": False,
            "use_llm_optimization": False,
            "rule_based_optimization": True,
            "use_static_analysis": True,
            "db_connection_string": None,
            "prune_history_days": 90,
            "async_execution": False,
            "least_privilege_execution": True,
            "log_level": "INFO"
        }
    }
    
    # Load existing configuration if available
    config = None
    config_path = output
    
    if not config_path:
        # Check standard locations
        standard_paths = [
            "./workflow_config.yaml",
            "./workflow_config.yml",
            "./workflow_config.json",
            "~/.workflow_agent/config.yaml"
        ]
        
        for path in standard_paths:
            expanded_path = Path(path).expanduser()
            if expanded_path.exists():
                config_path = str(expanded_path)
                break
    
    if config_path and Path(config_path).expanduser().exists():
        try:
            config = asyncio.run(load_config(config_path))
            console.print(f"Loaded existing configuration from {config_path}")
        except Exception as e:
            console.print(f"[yellow]Error loading existing configuration: {e}[/yellow]")
            config = default_config
    else:
        config = default_config
    
    # Show current configuration if requested
    if show:
        console.print("\n[bold]Current Configuration:[/bold]")
        console.print(json.dumps(config["configurable"], indent=2))
        return
    
    # Interactive configuration
    console.print("\n[bold]Workflow Agent Configuration[/bold]")
    console.print("Press Enter to keep current values, or enter new values.\n")
    
    # User ID
    user_id = inquirer.text(
        message="User ID:",
        default=config["configurable"].get("user_id", "cli-user")
    ).execute()
    
    # Template directories
    template_dir = inquirer.text(
        message="Template directory path:",
        default=config["configurable"].get("template_dir", "./templates")
    ).execute()
    
    custom_template_dir = inquirer.text(
        message="Custom template directory path (optional):",
        default=config["configurable"].get("custom_template_dir", "")
    ).execute()
    
    # Execution settings
    use_isolation = inquirer.confirm(
        message="Use isolation for script execution?",
        default=config["configurable"].get("use_isolation", False)
    ).execute()
    
    isolation_method = "docker"
    if use_isolation:
        isolation_method = inquirer.select(
            message="Select isolation method:",
            choices=[
                Choice("docker", "Docker container (recommended)"),
                Choice("chroot", "Chroot environment (requires root)"),
                Choice("venv", "Python virtual environment"),
                Choice("sandbox", "nsjail sandbox (advanced)")
            ],
            default=config["configurable"].get("isolation_method", "docker")
        ).execute()
    
    execution_timeout = inquirer.number(
        message="Execution timeout (milliseconds):",
        default=config["configurable"].get("execution_timeout", 30000),
        min_allowed=1000,
        max_allowed=300000
    ).execute()
    
    skip_verification = inquirer.confirm(
        message="Skip verification for removal actions?",
        default=config["configurable"].get("skip_verification", False)
    ).execute()
    
    # Optimization settings
    use_llm_optimization = inquirer.confirm(
        message="Use LLM (OpenAI) for script optimization?",
        default=config["configurable"].get("use_llm_optimization", False)
    ).execute()
    
    if not use_llm_optimization:
        rule_based_optimization = inquirer.confirm(
            message="Use rule-based script optimization?",
            default=config["configurable"].get("rule_based_optimization", True)
        ).execute()
    else:
        rule_based_optimization = False
    
    use_static_analysis = inquirer.confirm(
        message="Use static analysis for script validation?",
        default=config["configurable"].get("use_static_analysis", True)
    ).execute()
    
    # Database settings
    db_connection_string = inquirer.text(
        message="Database connection string (optional):",
        default=config["configurable"].get("db_connection_string", "")
    ).execute()
    
    prune_history_days = inquirer.number(
        message="Automatically prune history older than (days, 0 to disable):",
        default=config["configurable"].get("prune_history_days", 90),
        min_allowed=0
    ).execute()
    
    # Advanced settings
    async_execution = inquirer.confirm(
        message="Enable asynchronous workflow execution? (Advanced)",
        default=config["configurable"].get("async_execution", False)
    ).execute()
    
    least_privilege_execution = inquirer.confirm(
        message="Run scripts with least privileges?",
        default=config["configurable"].get("least_privilege_execution", True)
    ).execute()
    
    log_level = inquirer.select(
        message="Log level:",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=config["configurable"].get("log_level", "INFO")
    ).execute()
    
    # Build configuration
    new_config = {
        "configurable": {
            "user_id": user_id,
            "template_dir": template_dir,
            "custom_template_dir": custom_template_dir if custom_template_dir else None,
            "use_isolation": use_isolation,
            "isolation_method": isolation_method,
            "execution_timeout": execution_timeout,
            "skip_verification": skip_verification,
            "use_llm_optimization": use_llm_optimization,
            "rule_based_optimization": rule_based_optimization,
            "use_static_analysis": use_static_analysis,
            "db_connection_string": db_connection_string if db_connection_string else None,
            "prune_history_days": prune_history_days if prune_history_days > 0 else None,
            "async_execution": async_execution,
            "least_privilege_execution": least_privilege_execution,
            "log_level": log_level
        }
    }
    
    # Save configuration
    if not output:
        # Choose where to save
        default_path = config_path if config_path else "./workflow_config.yaml"
        output = inquirer.text(
            message="Save configuration to file:",
            default=default_path
        ).execute()
    
    try:
        output_path = Path(output).expanduser()
        
        # Create parent directory if needed
        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True)
        
        # Determine format based on extension
        if output.endswith('.json'):
            with open(output_path, 'w') as f:
                json.dump(new_config, f, indent=2)
        else:
            # Default to YAML
            with open(output_path, 'w') as f:
                yaml.dump(new_config, f, default_flow_style=False)
        
        console.print(f"[green]Configuration saved to {output_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error saving configuration: {e}[/red]")

@app.command("template")
def template_command(
    action: str = typer.Option(..., "--action", "-a", help="Action for the template (install, remove, etc.)"),
    target: str = typer.Option(..., "--target", "-t", help="Target for the template"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing template")
):
    """Create a new script template."""
    from ..workflow_agent.configuration import ensure_workflow_config, script_templates
    
    # Create template key
    template_key = f"{target}-{action}"
    
    # Check if template already exists
    if template_key in script_templates and not force:
        console.print(f"[yellow]Template for {target}-{action} already exists. Use --force to overwrite.[/yellow]")
        return
    
    # Create template content
    template_content = f"""#!/usr/bin/env bash
# Template for {action} {target}
set -e

# Error handling
error_exit() {{
    echo "ERROR: $1" >&2
    exit 1
}}

# Logging function
log_message() {{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}}

log_message "Starting {action} for {target}"

# Check for required tools
command -v curl >/dev/null 2>&1 || error_exit "curl is required but not installed"

# Example of parameter usage
{% if parameters.db_host is defined %}
DB_HOST="{{ parameters.db_host }}"
log_message "Using database host: $DB_HOST"
{% else %}
log_message "No database host specified"
{% endif %}

{% if parameters.db_port is defined %}
DB_PORT="{{ parameters.db_port }}"
log_message "Using database port: $DB_PORT"
{% else %}
DB_PORT="5432"  # Default port
log_message "Using default database port: $DB_PORT"
{% endif %}

# Main logic for {action} {target}
log_message "Executing {action} for {target}"

# TODO: Add your {action} logic here

{% if action == 'install' %}
# Installation specific steps
log_message "Installing {target}"
# TODO: Add installation steps
{% elif action == 'remove' %}
# Removal specific steps
log_message "Removing {target}"
# TODO: Add removal steps
{% elif action == 'verify' %}
# Verification specific steps
log_message "Verifying {target}"
# TODO: Add verification steps
{% endif %}

log_message "{action} for {target} completed successfully"
"""
    
    # Determine output location
    if not output:
        config = asyncio.run(load_config())
        template_dir = config["configurable"].get("template_dir", "./templates")
        output = os.path.join(template_dir, f"{template_key}.sh.j2")
    
    # Ensure directory exists
    output_path = Path(output)
    if not output_path.parent.exists():
        output_path.parent.mkdir(parents=True)
    
    # Save template
    try:
        with open(output_path, 'w') as f:
            f.write(template_content)
        console.print(f"[green]Template created at {output_path}[/green]")
        console.print("Edit this template to customize the script generation logic.")
    except Exception as e:
        console.print(f"[red]Error creating template: {e}[/red]")

@app.command("run")
async def run_command(
    config_file: str = typer.Option(None, "--config", "-c", help="Path to config file"),
    action: str = typer.Option("install", "--action", "-a", help="Workflow action (install, remove, verify)"),
    target: str = typer.Option("default", "--target", "-t", help="Target resource name"),
    integration_type: str = typer.Option("infra_agent", "--integration-type", "-i", 
                                        help="Integration type (infra_agent, aws, azure, gcp, apm, browser)"),
    param: List[str] = typer.Option([], "--param", "-p", help="Parameter in key=value format"),
    file: str = typer.Option(None, "--file", "-f", help="Load parameters from JSON/YAML file"),
    timeout: int = typer.Option(30000, "--timeout", help="Execution timeout in milliseconds"),
    batch: bool = typer.Option(False, "--batch", help="Run in batch mode (no interactive prompts)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Generate script but don't execute it"),
    optimize: bool = typer.Option(False, "--optimize", "-o", help="Use optimization for script generation"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show more detailed output"),
    skip_verify: bool = typer.Option(False, "--skip-verify", help="Skip verification step"),
    use_isolation: bool = typer.Option(False, "--use-isolation", help="Run script in isolated environment"),
    isolation_method: str = typer.Option(None, "--isolation-method", help="Isolation method (docker, chroot, venv, sandbox)"),
    output: str = typer.Option(None, "--output", help="Save generated script to file"),
    verify_cmd: str = typer.Option(None, "--verify-cmd", help="Custom verification command"),
    transaction_id: str = typer.Option(None, "--transaction-id", help="Custom transaction ID for tracking"),
    shell_check: bool = typer.Option(False, "--shell-check", help="Use ShellCheck for static analysis"),
    llm_optimize: bool = typer.Option(False, "--llm-optimize", help="Use LLM for script optimization")
):
    """Run a workflow to perform an action on a target."""
    try:
        # Load configuration
        config = await load_config(config_file)
        
        # Override configuration with command line options
        if timeout:
            config["configurable"]["execution_timeout"] = timeout
        
        if skip_verify:
            config["configurable"]["skip_verification"] = True
            
        if use_isolation:
            config["configurable"]["use_isolation"] = True
        
        if isolation_method:
            config["configurable"]["isolation_method"] = isolation_method
        
        if shell_check:
            config["configurable"]["use_static_analysis"] = True
        
        if llm_optimize:
            config["configurable"]["use_llm_optimization"] = True
            optimize = True
        elif optimize:
            # Default to rule-based optimization unless llm_optimize is specified
            config["configurable"]["rule_based_optimization"] = True
        
        # Validate integration type
        valid_integration_types = ["infra_agent", "aws", "azure", "gcp", "apm", "browser", "custom"]
        if integration_type not in valid_integration_types:
            console.print(f"[red]Error: Invalid integration_type. Valid options are: {', '.join(valid_integration_types)}[/red]")
            sys.exit(1)
        
        # Parse parameters
        parameters = {}
        for p in param:
            if '=' in p:
                k, v = p.split('=', 1)
                parameters[k] = v
            else:
                console.print(f"Invalid parameter format (expected key=value): {p}")
                sys.exit(1)
        
        # Load parameters from file if specified
        if file:
            try:
                content = Path(file).read_text()
                if file.endswith('.json'):
                    file_params = json.loads(content)
                elif file.endswith('.yaml') or file.endswith('.yml'):
                    file_params = yaml.safe_load(content)
                else:
                    console.print("Unknown parameter file format. Attempting to parse as JSON.")
                    file_params = json.loads(content)
                    
                parameters.update(file_params)
            except Exception as e:
                console.print(f"Error loading parameters file: {e}")
                sys.exit(1)
        
        # Interactive parameter collection if not in batch mode
        if not batch:
            schema_key = integration_type if integration_type != "infra_agent" else target
            if schema_key in parameter_schemas:
                schema = parameter_schemas.get(schema_key, {})
                missing_params = [(key, spec) for key, spec in schema.items() if spec.required and key not in parameters]
                
                if missing_params:
                    console.print("Please provide the following required parameters:")
                    for key, spec in missing_params:
                        description = f" ({spec.description})" if spec.description else f" ({spec.type})"
                        prompt = f"{key}{description}:"
                        value = await inquirer.text(message=prompt).execute_async()
                        
                        if spec.type == "number":
                            try:
                                value = float(value)
                            except ValueError:
                                console.print(f"Invalid number: {value}. Using as string.")
                        elif spec.type == "boolean":
                            value = value.lower() in ["true", "yes", "1", "y"]
                            
                        parameters[key] = value
        
        # Initialize workflow agent
        agent = WorkflowAgent()
        await agent.initialize(config)
        
        # Prepare workflow state
        state_dict = {
            "action": action,
            "target_name": target,
            "integration_type": integration_type,
            "parameters": parameters,
            "optimized": optimize,
            "messages": []
        }
        
        # Add custom transaction ID if provided
        if transaction_id:
            state_dict["transaction_id"] = transaction_id
        
        # Add custom verification command if provided
        if verify_cmd:
            state_dict["custom_verification"] = verify_cmd
        
        # Run the workflow
        start_time = time.time()
        result = await agent.invoke(state_dict, config)
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Print results
        if "error" in result:
            console.print(f"[red]Error:[/red] {result['error']}")
        else:
            console.print(f"[green]Workflow completed successfully in {execution_time:.2f}s[/green]")
            if "status" in result:
                console.print(f"[green]Status:[/green] {result['status']}")
            if "output" in result and result["output"]:
