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

class WorkflowAgent:
    """Orchestrates workflows with enhanced error recovery and monitoring."""
    
    def __init__(self, config: Optional[Union[Dict[str, Any], WorkflowConfiguration]] = None):
        """Initialize with configuration validation."""
        try:
            self.config = ensure_workflow_config(config)
            self._configure_logging()
            self.container = DependencyContainer(self.config)
            self._execution_count = 0
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise ConfigurationError(f"Invalid configuration: {e}") from e

    def _configure_logging(self) -> None:
        """Configure logging with rotation and file handling."""
        log_level = getattr(logging, self.config.log_level, logging.INFO)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            handlers=[
                logging.FileHandler("workflow_agent.log"),
                logging.StreamHandler()
            ]
        )
        logger.info("Logging configured with level: %s", self.config.log_level)
        logger.debug("Full configuration: %s", self.config.__dict__)

    def _initialize_container(self) -> None:
        """Initialize container with required components."""
        from .integrations.manager import IntegrationManager
        from .integrations.registry import IntegrationRegistry
        from .recovery.manager import RecoveryManager
        from .integrations.scripting import ScriptGenerator
        from .integrations.storage import StorageManager
        from .integrations.verification import VerificationManager
        from .integrations.documentation import DocumentationHandler
        
        # Register core components
        self.container.register('integration_registry', IntegrationRegistry())
        self.container.register('integration_manager', IntegrationManager(self.config))
        self.container.register('recovery_manager', RecoveryManager(self.config))
        
        # Register integration components
        self.container.register('script_generator', 
            ScriptGenerator(self.config.get('template_dir', './templates')))
        self.container.register('storage_manager', 
            StorageManager(self.config.get('storage_dir', './storage')))
        self.container.register('verification_manager', VerificationManager())
        self.container.register('documentation_handler', DocumentationHandler())

    async def initialize(self) -> None:
        """Initialize components with connection pooling and retries."""
        try:
            logger.info("Starting WorkflowAgent initialization...")
            await self._initialize_container()
            await self.container.initialize()
            
            logger.info("Validating container initialization...")
            self.container.validate_initialization()
            
            logger.info("WorkflowAgent initialization complete")
        except InitializationError as e:
            logger.error("Component initialization failed: %s", e, exc_info=True)
            logger.info("Cleaning up container due to initialization failure...")
            await self.container.cleanup()
            raise

    async def run_workflow(self, state: WorkflowState) -> WorkflowState:
        """Execute workflow with enhanced monitoring and recovery."""
        try:
            state = self._prepare_execution_state(state)
            logger.info("Starting workflow execution %d: %s", self._execution_count, state.action)

            # Get integration manager
            integration_manager = self.container.get('integration_manager')
            integration = integration_manager.get_integration(state.integration_type)
            if not integration:
                raise WorkflowError(f"Integration {state.integration_type} not found")

            # Execute integration action
            if state.action == "install":
                result = await integration.install(state.parameters)
            elif state.action == "verify":
                result = await integration.verify(state.parameters)
            elif state.action == "uninstall":
                result = await integration.uninstall(state.parameters)
            else:
                raise WorkflowError(f"Unsupported action: {state.action}")

            # Update state with result
            if result:
                if "template_path" in result:
                    state = state.evolve(
                        template_key=result["template_path"],
                        template_data=result.get("template_data", {})
                    )
                elif "status" in result:
                    if result["status"] == "success":
                        state = state.add_message(result.get("message", "Operation completed successfully"))
                        if "details" in result:
                            state = state.evolve(template_data=result["details"])
                    else:
                        state = state.set_error(result.get("message", "Operation failed"))
                else:
                    state = state.set_error("Invalid result format from integration")
            else:
                state = state.set_error("No result returned from integration")

            logger.info("Workflow completed successfully")
            return state
            
        except WorkflowError as e:
            logger.error("Workflow error: %s", e)
            return await self._handle_workflow_failure(state, e)
        except InitializationError as e:
            logger.error("Initialization error: %s", e)
            return await self._handle_workflow_failure(state, e)
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            return await self._handle_workflow_failure(state, e)

    async def close(self) -> None:
        """Closes the agent and releases resources."""
        try:
            await self.container.cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            raise

    def _prepare_execution_state(self, state: WorkflowState) -> WorkflowState:
        """Prepare the execution state."""
        return state.evolve(
            execution_id=str(uuid.uuid4()),
            metrics=self._create_metrics()
        )

    def _create_metrics(self) -> Any:
        """Create execution metrics."""
        from .core.state import ExecutionMetrics
        return ExecutionMetrics()

    async def _handle_workflow_failure(self, state: WorkflowState, e: Exception) -> WorkflowState:
        """Handle workflow failure and perform recovery if needed."""
        error_message = str(e)
        logger.error("Workflow failed: %s", error_message)
        
        # Add error to state
        state = state.set_error(error_message)
        
        # Attempt recovery if needed
        if self.config.use_recovery:
            try:
                recovery_manager = self.container.get('recovery_manager')
                state = await recovery_manager.recover(state)
            except Exception as recovery_error:
                logger.error("Recovery failed: %s", recovery_error)
                state = state.add_warning(f"Recovery failed: {recovery_error}")
        
        return state

# Create CLI app
app = typer.Typer()

@app.command()
def install(
    integration: str,
    license_key: str = typer.Option(..., help="License key for the integration"),
    host: str = typer.Option("localhost", help="Target host for installation")
):
    """Install an integration."""
    try:
        # Create workflow state
        state = WorkflowState(
            action="install",
            target_name=f"{integration}-integration",
            integration_type=integration,
            parameters={
                "license_key": license_key,
                "host": host
            },
            system_context=get_system_context(),
            template_data={}
        )
        
        async def run():
            # Initialize and run workflow
            agent = WorkflowAgent()
            await agent.initialize()
            try:
                return await agent.run_workflow(state)
            finally:
                await agent.close()
                
        result = asyncio.run(run())
        if result.has_error:
            logger.error(f"Installation failed: {result.error}")
            raise typer.Exit(1)
            
    except Exception as e:
        logger.error(f"Installation failed: {e}")
        raise typer.Exit(1)

@app.command()
def verify(
    integration: str,
    host: str = typer.Option("localhost", help="Target host for verification")
):
    """Verify an integration installation."""
    try:
        # Create workflow state
        state = WorkflowState(
            action="verify",
            target_name=f"{integration}-integration",
            integration_type=integration,
            parameters={"host": host},
            system_context=get_system_context(),
            template_data={}
        )
        
        async def run():
            # Initialize and run workflow
            agent = WorkflowAgent()
            await agent.initialize()
            try:
                return await agent.run_workflow(state)
            finally:
                await agent.close()
                
        result = asyncio.run(run())
        if result.has_error:
            logger.error(f"Verification failed: {result.error}")
            raise typer.Exit(1)
            
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise typer.Exit(1)

@app.command()
def remove(
    integration: str,
    host: str = typer.Option("localhost", help="Target host for removal")
):
    """Remove an integration."""
    try:
        # Create workflow state
        state = WorkflowState(
            action="uninstall",
            target_name=f"{integration}-integration",
            integration_type=integration,
            parameters={"host": host},
            system_context=get_system_context(),
            template_data={}
        )
        
        async def run():
            # Initialize and run workflow
            agent = WorkflowAgent()
            await agent.initialize()
            try:
                return await agent.run_workflow(state)
            finally:
                await agent.close()
                
        result = asyncio.run(run())
        if result.has_error:
            logger.error(f"Removal failed: {result.error}")
            raise typer.Exit(1)
            
    except Exception as e:
        logger.error(f"Removal failed: {e}")
        raise typer.Exit(1)

def main():
    """Main entry point for the CLI."""
    try:
        app()
    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()