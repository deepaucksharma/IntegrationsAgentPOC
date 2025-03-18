"""
Main entry point for the workflow agent.
"""
import asyncio
import logging
import sys
import os
from typing import Any, Dict, Optional

import typer
from typing_extensions import Annotated

from .core.state import WorkflowState
from .core.container import DependencyContainer
from .config import (
    WorkflowConfiguration,
    ensure_workflow_config,
    load_config_file,
    find_default_config,
    merge_configs
)
from .error.exceptions import (
    WorkflowError,
    ConfigurationError,
    InitializationError,
    ExecutionError
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class WorkflowAgent:
    """Orchestrates and executes workflows."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the workflow agent."""
        try:
            if isinstance(config, WorkflowConfiguration):
                self.config = config
            else:
                self.config = ensure_workflow_config(config)
            
            # Create dependency container
            self.container = DependencyContainer(self.config)
            
        except ConfigurationError as e:
            logger.error(f"Configuration error: {e}")
            raise

    async def initialize(self) -> None:
        """Initialize all components asynchronously."""
        try:
            await self.container.initialize()
            self.container.validate_initialization()
        except InitializationError as e:
            logger.error(f"Initialization error: {e}")
            raise

    async def run_workflow(self, state: WorkflowState) -> WorkflowState:
        """Runs a workflow based on the given state."""
        try:
            # Check privileges if needed
            if state.action in ["install", "setup", "remove"] and self.config.least_privilege_execution:
                state = await self._check_privileges(state)
                if state.error:
                    return state

            # Enhance state with dynamic knowledge
            try:
                integration_knowledge = self.container.get('integration_knowledge')
                state = await integration_knowledge.enhance_workflow_state(state)
            except Exception as e:
                return state.set_error(f"Failed to enhance workflow state: {str(e)}")

            # Select installation method if needed
            if state.action in ["install", "setup"] and not state.template_data.get("selected_method"):
                try:
                    installation_strategy = self.container.get('installation_strategy')
                    state = await installation_strategy.determine_best_approach(state)
                except Exception as e:
                    return state.set_error(f"Failed to determine installation approach: {str(e)}")

            # Generate script
            if not state.script:
                try:
                    if state.template_key:
                        # Pass configuration correctly
                        config_dict = {"configurable": self.config.__dict__}
                        script_generation_result = await self.container.get('script_generator').generate_script(state, config=config_dict)
                    elif state.action in ["install", "setup", "remove", "uninstall"]:
                        script_generation_result = await self.container.get('dynamic_script_generator').generate_from_knowledge(state)
                    else:
                        script_generation_result = {"error": "No template or dynamic script generation available for this action."}
                    
                    if script_generation_result.get("error"):
                        return script_generation_result
                    state.script = script_generation_result["script"]
                except (ValueError, KeyError) as e:
                    logger.error(f"Script generation failed: {e}")
                    return {"error": f"Script generation error: {str(e)}"}

            # Validate script
            try:
                script_validator = self.container.get('script_validator')
                validation_result = await script_validator.validate_script(state, config={"configurable": self.config.__dict__})
                if validation_result.get("warnings"):
                    for warning in validation_result["warnings"]:
                        state = state.add_warning(warning)
                if validation_result.get("error"):
                    return state.set_error(validation_result["error"])
            except Exception as e:
                return state.set_error(f"Script validation failed: {str(e)}")

            # Execute script
            try:
                script_executor = self.container.get('script_executor')
                state = await script_executor.run_script(state, config={"configurable": self.config.__dict__})
                if state.error:
                    return await self._handle_execution_failure(state)
            except Exception as e:
                return await self._handle_execution_failure(state.set_error(str(e)))

            # Build and run verification if needed
            if state.action in ["install", "setup"] and not self.config.skip_verification:
                try:
                    verification_builder = self.container.get('verification_builder')
                    verification_script = await verification_builder.build_verification_script(state)
                    
                    verification_state = WorkflowState(
                        action="verify",
                        target_name=state.target_name,
                        integration_type=state.integration_type,
                        script=verification_script,
                        parameters=state.parameters,
                        template_data=state.template_data,
                        system_context=state.system_context,
                        isolation_method=state.isolation_method,
                        transaction_id=state.transaction_id,
                        execution_id=state.execution_id
                    )
                    
                    verification_state = await script_executor.run_script(
                        verification_state,
                        config={"configurable": self.config.__dict__}
                    )
                    
                    if verification_state.error:
                        return await self._handle_execution_failure(verification_state)
                        
                except Exception as e:
                    return await self._handle_execution_failure(state.set_error(f"Verification failed: {str(e)}"))

            return state

        except Exception as e:
            logger.error(f"Unexpected error during workflow execution: {e}")
            return await self._handle_execution_failure(state.set_error(f"Unexpected error: {str(e)}"))

    async def close(self) -> None:
        """Closes the agent and releases resources."""
        try:
            await self.container.cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            raise

    async def _check_privileges(self, state: WorkflowState) -> WorkflowState:
        """Check if the agent has necessary privileges."""
        try:
            platform_manager = self.container.get('platform_manager')
            if platform_manager.platform_type.value == "windows":
                import ctypes
                is_admin = ctypes.windll.shell32.IsUserAnAdmin()
                if not is_admin:
                    return state.set_error(
                        "This operation requires administrator privileges. "
                        "Please run PowerShell or Command Prompt as Administrator and try again.\n"
                        "Right-click PowerShell/Command Prompt -> Run as Administrator"
                    )
            else:
                is_admin = os.geteuid() == 0
                if not is_admin:
                    return state.set_error(
                        "This operation requires root privileges. "
                        "Please run with sudo or as root:\n"
                        "sudo python test_workflow.py"
                    )
        except Exception as e:
            logger.warning(f"Could not check privileges: {e}")
            return state.add_warning(
                "Could not verify administrator privileges. "
                "If the operation fails, try running as Administrator/root."
            )
        return state

    async def _handle_execution_failure(self, state: WorkflowState) -> WorkflowState:
        """Handle execution failure and perform rollback if needed."""
        try:
            logger.info(f"Initiating rollback for {state.target_name} due to: {state.error}")
            recovery_manager = self.container.get('recovery_manager')
            rollback_result = await recovery_manager.perform_rollback(
                state,
                config={"configurable": self.config.__dict__}
            )
            
            if isinstance(rollback_result, dict) and rollback_result.get("error"):
                return state.add_warning(f"Rollback failed: {rollback_result['error']}")
            
            return state.add_warning("Rollback completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to perform rollback: {e}")
            return state.add_warning(f"Failed to perform rollback: {str(e)}")

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
        config_dict = load_config_file(config_path) if config_path else find_default_config()
        print(f"Configuration loaded: {config_dict}")
        
        print("Initializing agent...")
        agent = WorkflowAgent(config_dict)
        
        print("Creating workflow state...")
        state = WorkflowState(
            action="install",
            target_name=integration_type,
            integration_type=integration_type,
            parameters={"license_key": license_key, "host": host} if host else {"license_key": license_key},
            system_context={"platform": {"system": sys.platform}},
            template_data={}
        )
        print(f"Workflow state created: {state}")
        
        print("Running workflow...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            print("Initializing agent components...")
            loop.run_until_complete(agent.initialize())
            print("Running workflow execution...")
            result = loop.run_until_complete(agent.run_workflow(state))
            print(f"Workflow execution completed with result: {result}")
            loop.run_until_complete(agent.close())
        except Exception as e:
            print(f"Error during workflow execution: {str(e)}")
            logger.exception("Detailed error during workflow execution:")
            raise
        finally:
            loop.close()
        
        if result.error:
            typer.echo(f"Error: {result.error}", err=True)
            raise typer.Exit(1)
        typer.echo("Installation completed successfully")
        return result
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def remove(
    integration_type: str,
    config_path: Annotated[str, typer.Option(help="Path to custom configuration file")] = None,
):
    """Remove an integration."""
    try:
        config_dict = load_config_file(config_path) if config_path else find_default_config()
        agent = WorkflowAgent(config_dict)
        state = WorkflowState(
            action="remove",
            target_name=integration_type,
            integration_type=integration_type,
            system_context={"platform": {"system": sys.platform}},
            template_data={}
        )
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(agent.initialize())
            result = loop.run_until_complete(agent.run_workflow(state))
            loop.run_until_complete(agent.close())
        finally:
            loop.close()
        
        if result.error:
            typer.echo(f"Error: {result.error}", err=True)
            raise typer.Exit(1)
        typer.echo("Removal completed successfully")
        return result
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
        config_dict = load_config_file(config_path) if config_path else find_default_config()
        agent = WorkflowAgent(config_dict)
        state = WorkflowState(
            action="verify",
            target_name=integration_type,
            integration_type=integration_type,
            system_context={"platform": {"system": sys.platform}},
            template_data={}
        )
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(agent.initialize())
            result = loop.run_until_complete(agent.run_workflow(state))
            loop.run_until_complete(agent.close())
        finally:
            loop.close()
        
        if result.error:
            typer.echo(f"Error: {result.error}", err=True)
            raise typer.Exit(1)
        typer.echo("Verification completed successfully")
        return result
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

if __name__ == "__main__":
    app()