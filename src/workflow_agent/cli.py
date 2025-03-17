import os
import json
import yaml
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.prompt import Prompt, Confirm
from rich.table import Table

from .agent import WorkflowAgent
from .config.configuration import ensure_workflow_config
from .integrations.registry import IntegrationRegistry
from .core.state import WorkflowState

# Initialize Typer app
app = typer.Typer(help="Workflow Agent CLI")
verify_app = typer.Typer(help="Verification commands")
templates_app = typer.Typer(help="Template management")

# Add subcommands
app.add_typer(verify_app, name="verify")
app.add_typer(templates_app, name="templates")

# Initialize Rich console
console = Console()

@app.command("configure")
def configure(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config file")
):
    """Configure the workflow agent."""
    # Load existing configuration
    config = ensure_workflow_config()
    
    # Get user input
    user_id = Prompt.ask(
        "User ID",
        default=config["configurable"]["user_id"]
    )
    
    template_dir = Prompt.ask(
        "Template directory",
        default=config["configurable"]["template_dir"]
    )
    
    custom_template_dir = Prompt.ask(
        "Custom template directory (optional)",
        default=config["configurable"].get("custom_template_dir", "")
    )
    
    use_isolation = Confirm.ask(
        "Use isolation for script execution?",
        default=config["configurable"]["use_isolation"]
    )
    
    isolation_method = Prompt.ask(
        "Isolation method (docker, chroot, venv, sandbox)",
        default=config["configurable"]["isolation_method"],
        choices=["docker", "chroot", "venv", "sandbox"]
    )
    
    execution_timeout = Prompt.ask(
        "Execution timeout (milliseconds)",
        default=str(config["configurable"]["execution_timeout"])
    )
    
    skip_verification = Confirm.ask(
        "Skip verification for removal actions?",
        default=config["configurable"]["skip_verification"]
    )
    
    rule_based_optimization = Confirm.ask(
        "Use rule-based script optimization?",
        default=config["configurable"]["rule_based_optimization"]
    )
    
    use_static_analysis = Confirm.ask(
        "Use static analysis for script validation?",
        default=config["configurable"]["use_static_analysis"]
    )
    
    prune_history_days = Prompt.ask(
        "Automatically prune history older than N days (0 to disable)",
        default=str(config["configurable"]["prune_history_days"])
    )
    
    max_concurrent_tasks = Prompt.ask(
        "Maximum concurrent tasks",
        default=str(config["configurable"]["max_concurrent_tasks"])
    )
    
    log_level = Prompt.ask(
        "Log level (DEBUG, INFO, WARNING, ERROR)",
        default=config["configurable"]["log_level"],
        choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    
    # Build new configuration
    new_config = {
        "configurable": {
            "user_id": user_id,
            "template_dir": template_dir,
            "custom_template_dir": custom_template_dir or None,
            "use_isolation": use_isolation,
            "isolation_method": isolation_method,
            "execution_timeout": int(execution_timeout),
            "skip_verification": skip_verification,
            "use_llm_optimization": False,  # Default to False as it requires OpenAI API key
            "rule_based_optimization": rule_based_optimization,
            "use_static_analysis": use_static_analysis,
            "db_connection_string": None,  # Use default SQLite
            "prune_history_days": int(prune_history_days),
            "plugin_dirs": ["./plugins"],
            "async_execution": False,  # Default to False for simplicity
            "max_concurrent_tasks": int(max_concurrent_tasks),
            "least_privilege_execution": True,
            "sandbox_isolation": False,
            "log_level": log_level
        }
    }
    
    # Ask where to save configuration
    save_path = Prompt.ask(
        "Save configuration to",
        default=config_path or "./workflow_config.yaml"
    )
    
    # Save configuration
    try:
        with open(save_path, "w") as f:
            if save_path.endswith(".json"):
                json.dump(new_config, f, indent=2)
            else:
                yaml.dump(new_config, f, default_flow_style=False)
        
        console.print(f"\n[bold green]Configuration saved to {save_path}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error saving configuration: {e}[/bold red]")

@verify_app.command("run")
def verify(
    target: str = typer.Option(..., "--target", "-t", help="Target to verify"),
    integration_type: str = typer.Option("infra_agent", "--integration-type", "-i", help="Integration type"),
    param: List[str] = typer.Option([], "--param", "-p", help="Parameters in format key=value"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Integration category")
):
    """Verify an integration is working."""
    async def _verify():
        # Parse parameters
        parameters = {}
        for p in param:
            if "=" in p:
                key, value = p.split("=", 1)
                parameters[key] = value
        
        # Determine integration type and category
        if not integration_type or integration_type == "infra_agent":
            best_match = IntegrationRegistry.get_best_integration_for_target(target)
            if best_match:
                integration_name, metadata = best_match
                integration_type = integration_name
                if not category:
                    category = metadata.category
        
        # If no category specified, use "custom"
        if not category:
            category = "custom"
        
        # Create input state
        input_state = {
            "action": "verify",
            "target_name": target,
            "integration_type": integration_type,
            "integration_category": category,
            "parameters": parameters
        }
        
        # Create configuration
        config = {
            "configurable": {
                "use_isolation": True,
                "isolation_method": "docker"
            }
        }
        
        # Create and initialize agent
        agent = WorkflowAgent()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Initializing...[/bold blue]"),
            transient=True
        ) as progress:
            progress.add_task("initializing", total=1)
            await agent.initialize(config)
        
        try:
            # Execute verification
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Verifying integration...[/bold blue]"),
                transient=True
            ) as progress:
                progress.add_task("verifying", total=1)
                result = await agent.invoke(input_state, config)
            
            # Display result
            if "error" in result:
                console.print(f"\n[bold red]Verification failed:[/bold red] {result['error']}")
                
                if "verification_output" in result and result["verification_output"]:
                    console.print("\n[bold yellow]Verification details:[/bold yellow]")
                    console.print(json.dumps(result["verification_output"], indent=2))
                
                return
            
            console.print("\n[bold green]Verification successful![/bold green]")
            
            if "verification_output" in result and result["verification_output"]:
                console.print("\n[bold]Verification details:[/bold]")
                console.print(json.dumps(result["verification_output"], indent=2))
            
            if "output" in result and result["output"]:
                console.print("\n[bold]Output:[/bold]")
                console.print(result["output"].stdout)
        finally:
            await agent.cleanup()
    
    asyncio.run(_verify())

@verify_app.command("batch")
def verify_batch(
    targets_file: Path = typer.Option(..., "--targets-file", "-f", help="File with targets (one per line)"),
    params_file: Optional[Path] = typer.Option(None, "--params-file", "-p", help="Parameters file (JSON)")
):
    """Verify multiple integrations."""
    async def _verify_batch():
        # Read targets from file
        if not targets_file.exists():
            console.print(f"[bold red]Targets file not found: {targets_file}[/bold red]")
            return
        
        with open(targets_file, "r") as f:
            targets = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
        if not targets:
            console.print("[bold yellow]No targets found in file.[/bold yellow]")
            return
        
        console.print(f"[bold]Found {len(targets)} targets in file.[/bold]")
        
        # Read parameters
        parameters = {}
        if params_file:
            if not params_file.exists():
                console.print(f"[bold red]Parameters file not found: {params_file}[/bold red]")
                return
            
            try:
                with open(params_file, "r") as f:
                    parameters = json.load(f)
            except Exception as e:
                console.print(f"[bold red]Error loading parameters: {e}[/bold red]")
                return
        
        # Confirm execution
        if not Confirm.ask(f"Verify {len(targets)} targets?"):
            return
        
        # Create and initialize agent
        agent = WorkflowAgent()
        await agent.initialize()
        
        # Process targets
        results = {"success": [], "failed": []}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Verifying targets...[/bold blue]"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn()
        ) as progress:
            task = progress.add_task("Verifying", total=len(targets))
            
            for target in targets:
                # Determine best integration
                best_match = IntegrationRegistry.get_best_integration_for_target(target)
                if best_match:
                    integration_type, metadata = best_match
                    category = metadata.category
                else:
                    integration_type = "infra_agent"
                    category = "custom"
                
                # Create input state
                input_state = {
                    "action": "verify",
                    "target_name": target,
                    "integration_type": integration_type,
                    "integration_category": category,
                    "parameters": parameters.copy()
                }
                
                # Execute verification
                result = await agent.invoke(input_state)
                
                if "error" in result:
                    results["failed"].append({
                        "target": target,
                        "error": result["error"],
                        "details": result.get("verification_output", {})
                    })
                else:
                    results["success"].append({
                        "target": target,
                        "details": result.get("verification_output", {})
                    })
                
                progress.update(task, advance=1, description=f"Verified: {target}")
        
        # Show summary
        console.print("\n[bold]Verification Summary:[/bold]")
        console.print(f"[bold green]Success: {len(results['success'])}")
        console.print(f"[bold red]Failed: {len(results['failed'])}")
        
        if results["failed"]:
            console.print("\n[bold red]Failed targets:[/bold red]")
            table = Table(show_header=True, header_style="bold red")
            table.add_column("Target")
            table.add_column("Error")
            
            for failure in results["failed"]:
                table.add_row(failure["target"], failure["error"])
            
            console.print(table)
        
        # Save results to file
        results_file = f"verify_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        
        console.print(f"\n[bold green]Results saved to {results_file}[/bold green]")
        
        await agent.cleanup()
    
    asyncio.run(_verify_batch())

@templates_app.command("list")
def list_templates(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category")
):
    """List available templates."""
    from ..config.templates import get_available_templates, get_template_categories
    
    if category:
        templates = get_available_templates(category)
        console.print(f"\n[bold]Templates in category {category}:[/bold]")
    else:
        templates = get_available_templates()
        categories = get_template_categories()
        
        console.print("\n[bold]Template categories:[/bold]")
        for cat in sorted(categories):
            console.print(f"- {cat}")
        
        console.print("\n[bold]All templates:[/bold]")
    
    if not templates:
        console.print("[bold yellow]No templates found.[/bold yellow]")
        return
    
    # Group templates by action
    by_action = {}
    for template in templates:
        if "-" in template:
            parts = template.split("-")
            action = parts[-1]
            target = "-".join(parts[:-1])
        else:
            action = "unknown"
            target = template
        
        if action not in by_action:
            by_action[action] = []
        
        by_action[action].append(template)
    
    # Display by action
    for action, templates in sorted(by_action.items()):
        console.print(f"\n[bold]Action: {action}[/bold]")
        
        table = Table(show_header=False)
        table.add_column("Template")
        
        for template in sorted(templates):
            table.add_row(template)
        
        console.print(table)
    
    console.print(f"\nTotal templates: {len(templates)}")

@templates_app.command("show")
def show_template(
    template: str = typer.Argument(..., help="Template name to show")
):
    """Show template content."""
    from ..config.templates import get_template
    
    content = get_template(template)
    
    if not content:
        console.print(f"[bold red]Template {template} not found.[/bold red]")
        return
    
    console.print(f"\n[bold]Template: {template}[/bold]")
    console.print(f"```jinja\n{content}\n```")

@templates_app.command("create")
def create_template(
    target: str = typer.Option(..., "--target", "-t", help="Target name"),
    action: str = typer.Option(..., "--action", "-a", help="Action name"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Category"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path")
):
    """Create a new template."""
    from ..config.configuration import ensure_workflow_config
    
    # Determine output path
    if not output:
        config = ensure_workflow_config()
        template_dir = config.template_dir
        
        if category:
            template_dir = os.path.join(template_dir, category)
            
            # Create category directory if it doesn't exist
            if not os.path.exists(template_dir):
                try:
                    os.makedirs(template_dir)
                except Exception as e:
                    console.print(f"[bold red]Error creating category directory: {e}[/bold red]")
                    return
        
        filename = f"{target}-{action}.sh.j2"
        output = os.path.join(template_dir, filename)
    
    # Check if file already exists
    if os.path.exists(output):
        if not Confirm.ask(f"Template file {output} already exists. Overwrite?"):
            return
    
    # Generate template content
    content = f"""#!/usr/bin/env bash
# Template for {action} {target}
set -e

# Error handling function
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
{{% if parameters.port is defined %}}
PORT="{{ parameters.port }}"
log_message "Using custom port: $PORT"
{{% else %}}
PORT="8080"
log_message "Using default port: $PORT"
{{% endif %}}

# Your {action} logic here
log_message "{action.capitalize()}ing {target}"

# Add your commands here

log_message "{target} {action} completed successfully"
"""
    
    # Write template to file
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        
        with open(output, "w") as f:
            f.write(content)
        
        console.print(f"[bold green]Template created: {output}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error creating template: {e}[/bold red]")

if __name__ == "__main__":
    app() 