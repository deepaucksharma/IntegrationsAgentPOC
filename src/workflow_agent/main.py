"""
Main entry point for the workflow agent.
"""
import asyncio
import logging
import sys
from typing import Any, Dict, Optional

import typer
from typing_extensions import Annotated

from .core.state import WorkflowState
from .core.message_bus import MessageBus
from .execution import ScriptExecutor
from .scripting import ScriptGenerator, ScriptValidator, DynamicScriptGenerator
from .verification import DynamicVerificationBuilder
from .knowledge import DynamicIntegrationKnowledge
from .strategy import InstallationStrategyAgent
from .rollback import RecoveryManager
from .storage import ExecutionHistoryManager
from .config import (
    WorkflowConfiguration,
    ensure_workflow_config,
    load_config_file,
    find_default_config,
    merge_configs,
    initialize_template_environment,
    load_templates,
)
from .error.exceptions import ConfigurationError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class WorkflowAgent:
    """Orchestrates and executes workflows."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the workflow agent."""
        try:
            self.config = ensure_workflow_config(config)
        except ConfigurationError as e:
            logger.error(f"Configuration error: {e}")
            sys.exit(1)
        
        self.message_bus = MessageBus()
        self.history_manager = ExecutionHistoryManager()
        self.executor = ScriptExecutor(history_manager=self.history_manager, timeout=self.config.execution_timeout)
        self.script_generator = ScriptGenerator(history_manager=self.history_manager)
        self.script_validator = ScriptValidator()
        self.dynamic_script_generator = DynamicScriptGenerator()
        self.dynamic_verification_builder = DynamicVerificationBuilder()
        self.rollback_manager = RecoveryManager(history_manager=self.history_manager)
        self.integration_knowledge = DynamicIntegrationKnowledge()
        self.installation_strategy = InstallationStrategyAgent()
        
        # Initialize template environment and load templates
        initialize_template_environment([self.config.template_dir])
        load_templates()

    async def initialize(self) -> None:
        """Initialize all components asynchronously."""
        await self.executor.initialize()
        await self.history_manager.initialize()
        await self.rollback_manager.initialize()
        if hasattr(self.integration_knowledge, 'initialize'):
            await self.integration_knowledge.initialize()
        if hasattr(self.installation_strategy, 'initialize'):
            await self.installation_strategy.initialize()

    async def run_workflow(self, state: WorkflowState) -> Dict[str, Any]:
        """Runs a workflow based on the given state."""
        try:
            # Enhance state with dynamic knowledge
            state = await self.integration_knowledge.enhance_workflow_state(state)
            
            # Select installation method if needed
            if state.action in ["install", "setup"] and not state.template_data.get("selected_method"):
                state = await self.installation_strategy.determine_best_approach(state)
            
            # Generate script
            if not state.script:
                if state.template_key:
                    script_generation_result = await self.script_generator.generate_script(state, config={"configurable": self.config.__dict__})
                elif state.action in ["install", "setup", "remove", "uninstall"]:
                    script_generation_result = await self.dynamic_script_generator.generate_from_knowledge(state)
                else:
                    script_generation_result = {"error": "No template or dynamic script generation available for this action."}
                
                if script_generation_result.get("error"):
                    return script_generation_result
                state.script = script_generation_result["script"]
            
            # Validate script
            validation_result = await self.script_validator.validate_script(state, config={"configurable": self.config.__dict__})
            if validation_result.get("warnings"):
                for warning in validation_result["warnings"]:
                    logger.warning(f"Script validation warning: {warning}")
            if validation_result.get("error"):
                return validation_result
            
            # Run script
            execution_result = await self.executor.run_script(state, config={"configurable": self.config.__dict__})
            if execution_result.get("error"):
                logger.error(f"Script execution failed: {execution_result['error']}")
                # Perform rollback if script execution fails
                logger.info("Initiating rollback due to script execution failure...")
                rollback_result = await self.rollback_manager.perform_rollback(state, config={"configurable": self.config.__dict__})
                if rollback_result.get("error"):
                    logger.error(f"Rollback failed: {rollback_result['error']}")
                    execution_result["rollback_error"] = rollback_result["error"]
                else:
                    logger.info("Rollback completed successfully")
                    execution_result["rollback_status"] = "success"
                return execution_result
            
            # Build verification script if needed
            if state.action in ["install", "setup"] and self.config.skip_verification is False:
                verification_script = await self.dynamic_verification_builder.build_verification_script(state)
                verification_state = WorkflowState(
                    action="verify",
                    target_name=state.target_name,
                    integration_type=state.integration_type,
                    script=verification_script,
                    parameters=state.parameters,
                    template_data=state.template_data,
                    system_context=state.system_context,
                    isolation_method=state.isolation_method,
                    transaction_id=execution_result.get("transaction_id"),
                    execution_id=execution_result.get("execution_id")
                )
                verification_result = await self.executor.run_script(verification_state, config={"configurable": self.config.__dict__})
                if verification_result.get("error"):
                    logger.error(f"Verification failed: {verification_result['error']}")
                    # Rollback if verification fails
                    logger.info("Initiating rollback due to verification failure...")
                    rollback_result = await self.rollback_manager.perform_rollback(state, config={"configurable": self.config.__dict__})
                    if rollback_result.get("error"):
                        logger.error(f"Rollback failed: {rollback_result['error']}")
                        verification_result["rollback_error"] = rollback_result["error"]
                    else:
                        logger.info("Rollback completed successfully")
                        verification_result["rollback_status"] = "success"
                    return verification_result
                
            return execution_result
        
        except Exception as e:
            logger.error(f"Unexpected error during workflow execution: {str(e)}")
            # Attempt rollback on unexpected errors
            try:
                logger.info("Initiating rollback due to unexpected error...")
                rollback_result = await self.rollback_manager.perform_rollback(state, config={"configurable": self.config.__dict__})
                if rollback_result.get("error"):
                    logger.error(f"Rollback failed: {rollback_result['error']}")
                    return {"error": str(e), "rollback_error": rollback_result["error"]}
                else:
                    logger.info("Rollback completed successfully")
                    return {"error": str(e), "rollback_status": "success"}
            except Exception as rollback_error:
                logger.error(f"Failed to perform rollback: {str(rollback_error)}")
                return {"error": str(e), "rollback_error": str(rollback_error)}
    
    async def close(self) -> None:
        """Closes the agent and releases resources."""
        await self.executor.cleanup()
        logger.info("Workflow agent closed.")

app = typer.Typer(help="Workflow Agent CLI")

@app.command()
def install(
    integration_type: str,
    license_key: Annotated[str, typer.Option(help="License key for the integration")],
    host: Annotated[str, typer.Option(help="Host for the integration")] = None,
    config_path: Annotated[str, typer.Option(help="Path to custom configuration file")] = None,
):
    """Install an integration."""
    try:
        print("Loading configuration...")
        config = load_config_file(config_path) if config_path else find_default_config()
        print(f"Configuration loaded: {config}")
        
        print("Initializing agent...")
        agent = WorkflowAgent(config)
        
        print("Creating workflow state...")
        state = WorkflowState(
            action="install",
            target_name=integration_type,
            integration_type=integration_type,
            parameters={"license_key": license_key, "host": host} if host else {"license_key": license_key}
        )
        print(f"Workflow state created: {state}")
        
        print("Running workflow...")
        result = asyncio.run(agent.run_workflow(state))
        print(f"Workflow result: {result}")
        
        if result.get("error"):
            typer.echo(f"Error: {result['error']}", err=True)
            raise typer.Exit(1)
        typer.echo("Installation completed successfully")
    except Exception as e:
        print(f"Exception occurred: {str(e)}")
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def remove(
    integration_type: str,
    config_path: Annotated[str, typer.Option(help="Path to custom configuration file")] = None,
):
    """Remove an integration."""
    try:
        config = load_config_file(config_path) if config_path else find_default_config()
        agent = WorkflowAgent(config)
        state = WorkflowState(
            action="remove",
            target_name=integration_type,
            integration_type=integration_type
        )
        result = asyncio.run(agent.run_workflow(state))
        if result.get("error"):
            typer.echo(f"Error: {result['error']}", err=True)
            raise typer.Exit(1)
        typer.echo("Removal completed successfully")
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def verify(
    integration_type: str,
    config_path: Annotated[str, typer.Option(help="Path to custom configuration file")] = None,
):
    """Verify an integration."""
    try:
        config = load_config_file(config_path) if config_path else find_default_config()
        agent = WorkflowAgent(config)
        state = WorkflowState(
            action="verify",
            target_name=integration_type,
            integration_type=integration_type
        )
        result = asyncio.run(agent.run_workflow(state))
        if result.get("error"):
            typer.echo(f"Error: {result['error']}", err=True)
            raise typer.Exit(1)
        typer.echo("Verification completed successfully")
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

if __name__ == "__main__":
    app()