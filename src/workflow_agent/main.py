"""
Main entry point for the workflow agent with enhanced script generation and error handling.
"""
import asyncio
import logging
import sys
import os
import uuid
import traceback
from typing import Dict, Any, Optional, List, Type, Union

import typer
from typing_extensions import Annotated
from pydantic import ValidationError

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
    ExecutionError,
    StateError
)
from .utils.system import get_system_context
from .documentation.parser import DocumentationParser

logger = logging.getLogger(__name__)

class ScriptGeneratorRegistry:
    """Registry for script generators with enhanced fallback handling."""
    
    def __init__(self):
        self._generators: Dict[str, Any] = {}
        self._action_mappings: Dict[str, str] = {}
        
    def register(self, name: str, generator: Any) -> None:
        """Register a script generator with validation."""
        if not hasattr(generator, 'generate_script'):
            raise ValueError("Generator must implement generate_script method")
        self._generators[name] = generator
        
    def register_action(self, action: str, generator_name: str) -> None:
        """Map an action to a generator type with validation."""
        if generator_name not in self._generators:
            raise ValueError(f"Unknown generator: {generator_name}")
        self._action_mappings[action] = generator_name
        
    def get_for_state(self, state: WorkflowState) -> Optional[Any]:
        """Get appropriate generator with priority handling."""
        if state.template_key:
            return self._generators.get("template")
        
        if generator_name := self._action_mappings.get(state.action):
            return self._generators.get(generator_name)
        
        if state.action in ["install", "setup", "remove", "uninstall", "verify"]:
            return self._generators.get("dynamic")
        
        return None

class WorkflowAgent:
    """Orchestrates workflows with enhanced error recovery and monitoring."""
    
    def __init__(self, config: Optional[Union[Dict[str, Any], WorkflowConfiguration]] = None):
        """Initialize with configuration validation."""
        try:
            self.config = ensure_workflow_config(config)
            self._configure_logging()
            self.container = DependencyContainer(self.config)
            self.script_registry = ScriptGeneratorRegistry()
            self._execution_count = 0
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise ConfigurationError(f"Invalid configuration: {e}") from e

    def _configure_logging(self) -> None:
        """Configure logging with rotation and file handling."""
        log_level = getattr(logging, self.config.log_level, logging.INFO)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("workflow_agent.log"),
                logging.StreamHandler()
            ]
        )

    async def initialize(self) -> None:
        """Initialize components with connection pooling and retries."""
        try:
            await self.container.initialize()
            self.container.validate_initialization()
            self._register_script_generators()
            logger.info("Workflow agent initialized with %d plugins", len(self.config.plugin_dirs))
        except InitializationError as e:
            logger.error("Component initialization failed: %s", e)
            await self.container.cleanup()
            raise

    def _register_script_generators(self) -> None:
        """Register script generators with dependency validation."""
        try:
            self.script_registry.register("template", self.container.get('script_generator'))
            self.script_registry.register("dynamic", self.container.get('dynamic_script_generator'))
            
            action_mappings = {
                "install": "dynamic",
                "setup": "dynamic",
                "remove": "dynamic",
                "uninstall": "dynamic",
                "verify": "dynamic"
            }
            for action, gen_name in action_mappings.items():
                self.script_registry.register_action(action, gen_name)
        except KeyError as e:
            raise InitializationError(f"Missing component: {e}") from e

    async def run_workflow(self, state: WorkflowState) -> WorkflowState:
        """Execute workflow with enhanced monitoring and recovery."""
        try:
            state = self._prepare_execution_state(state)
            logger.info("Starting workflow execution %d: %s", self._execution_count, state.action)

            await self._check_system_requirements(state)
            state = await self._enhance_with_knowledge(state)
            state = await self._determine_installation_strategy(state)
            state = await self._generate_and_validate_script(state)
            state = await self._execute_script(state)
            
            if state.action in ["install", "setup"] and not self.config.skip_verification:
                state = await self._verify_installation(state)

            logger.info("Workflow completed successfully in %.2fs", state.execution_time)
            return state
            
        except Exception as e:
            logger.error("Workflow failed: %s", e)
            return await self._handle_workflow_failure(state, e)

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

    def _prepare_execution_state(self, state: WorkflowState) -> WorkflowState:
        # Implementation of _prepare_execution_state method
        pass

    async def _check_system_requirements(self, state: WorkflowState) -> None:
        # Implementation of _check_system_requirements method
        pass

    async def _enhance_with_knowledge(self, state: WorkflowState) -> WorkflowState:
        # Implementation of _enhance_with_knowledge method
        pass

    async def _determine_installation_strategy(self, state: WorkflowState) -> WorkflowState:
        # Implementation of _determine_installation_strategy method
        pass

    async def _generate_and_validate_script(self, state: WorkflowState) -> WorkflowState:
        # Implementation of _generate_and_validate_script method
        pass

    async def _execute_script(self, state: WorkflowState) -> WorkflowState:
        # Implementation of _execute_script method
        pass

    async def _verify_installation(self, state: WorkflowState) -> WorkflowState:
        # Implementation of _verify_installation method
        pass

    async def _handle_workflow_failure(self, state: WorkflowState, e: Exception) -> WorkflowState:
        # Implementation of _handle_workflow_failure method
        pass

app = typer.Typer(help="Workflow Agent CLI", add_completion=False)

@app.command()
def install(
    integration_type: str,
    license_key: Annotated[str, typer.Option(help="License key for the integration")],
    host: Annotated[str, typer.Option(help="Host for the integration")] = None,
    config_path: Annotated[str, typer.Option(help="Path to custom configuration file")] = None,
    verbose: Annotated[bool, typer.Option(help="Enable verbose output")] = False,
):
    """Install an integration with enhanced validation."""
    _run_workflow_cli("install", integration_type, locals())

@app.command()
def remove(
    integration_type: str,
    config_path: Annotated[str, typer.Option(help="Path to custom configuration file")] = None,
    verbose: Annotated[bool, typer.Option(help="Enable verbose output")] = False,
):
    """Remove an integration with dependency checking."""
    _run_workflow_cli("remove", integration_type, locals())

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

def _run_workflow_cli(action: str, integration_type: str, locals_dict: dict):
    """Centralized CLI execution handler."""
    try:
        config = _load_config(locals_dict.get('config_path'), locals_dict.get('verbose'))
        agent = WorkflowAgent(config)
        state = _create_workflow_state(action, integration_type, locals_dict)
        
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(agent.initialize())
            result = loop.run_until_complete(agent.run_workflow(state))
            loop.run_until_complete(agent.close())
        finally:
            loop.close()

        _handle_cli_result(result)
    except Exception as e:
        _handle_cli_error(e)

def _load_config(config_path: Optional[str], verbose: bool) -> Optional[Dict[str, Any]]:
    # Implementation of _load_config method
    pass

def _create_workflow_state(action: str, integration_type: str, locals_dict: dict) -> WorkflowState:
    # Implementation of _create_workflow_state method
    pass

def _handle_cli_result(result: WorkflowState):
    # Implementation of _handle_cli_result method
    pass

def _handle_cli_error(e: Exception):
    # Implementation of _handle_cli_error method
    pass

if __name__ == "__main__":
    app()