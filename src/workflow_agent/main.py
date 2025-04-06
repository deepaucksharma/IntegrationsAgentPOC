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
from .verification.dynamic import DynamicVerificationBuilder
from .config.configuration import WorkflowConfiguration, ensure_workflow_config
from .error.exceptions import (
    WorkflowError,
    ConfigurationError,
    InitializationError,
    ExecutionError,
    StateError
)
from .utils.system import get_system_context
from .utils.logging import configure_logging, get_workflow_logger
from .templates.manager import TemplateManager
from .scripting.generator import ScriptGenerator
from .execution.executor import ScriptExecutor
from .verification.manager import VerificationManager
from .recovery.manager import RecoveryManager
from .integrations.manager import IntegrationManager
from .integrations.registry import IntegrationRegistry

logger = logging.getLogger(__name__)

class WorkflowAgent:
    """Orchestrates workflows with enhanced error recovery and monitoring."""
    
    def __init__(self, config: Optional[Union[Dict[str, Any], WorkflowConfiguration]] = None):
        """Initialize with configuration validation."""
        try:
            self.config = ensure_workflow_config(config)
            self._configure_logging()
            self._initialize_components()
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise ConfigurationError(f"Invalid configuration: {e}") from e

    def _configure_logging(self) -> None:
        """Configure logging with rotation and structured formatting."""
        configure_logging({
            "log_level": self.config.log_level,
            "log_file": self.config.log_file or "workflow_agent.log",
            "structured_logging": True,
            "version": getattr(self.config, "version", "1.0.0")
        })
        
        logger.info("Logging configured with level: %s", self.config.log_level)
        logger.debug("Full configuration: %s", self.config.model_dump())

    def _initialize_components(self) -> None:
        """Initialize components with dependency injection."""
        # Create template manager
        self.template_manager = TemplateManager(self.config)
        
        # Create integration registry and manager
        self.integration_registry = IntegrationRegistry()
        self.integration_manager = IntegrationManager(self.config, self.integration_registry)
        
        # Create script generator and executor
        self.script_generator = ScriptGenerator(self.config, self.template_manager)
        self.script_executor = ScriptExecutor(self.config)
        
        # Create verification manager
        self.verification_manager = VerificationManager(self.config, self.template_manager)
        
        # Create recovery manager
        self.recovery_manager = RecoveryManager(self.config)

    async def run_workflow(self, state: WorkflowState) -> WorkflowState:
        """Execute workflow with enhanced monitoring and recovery."""
        workflow_logger = get_workflow_logger(
            "workflow_agent.workflow",
            workflow_id=state.transaction_id,
            execution_id=state.execution_id,
            integration_type=state.integration_type,
            action=state.action
        )
        
        try:
            workflow_logger.info("Starting workflow execution: %s", state.action)
            
            # Get integration
            integration = self.integration_manager.get_integration(state.integration_type)
            if not integration:
                raise WorkflowError(f"Integration {state.integration_type} not found")
            
            # Execute based on action
            if state.action == "install":
                # Generate installation script
                state = await self.script_generator.generate_script(state)
                if state.has_error:
                    return state
                
                # Execute the script
                state = await self.script_executor.execute(state)
                if state.has_error:
                    return await self._handle_workflow_failure(state)
                
                workflow_logger.info("Installation completed successfully")
                
            elif state.action == "verify":
                # Run verification
                state = await self.verification_manager.verify(state)
                
                workflow_logger.info("Verification completed with status: %s", state.status)
                
            elif state.action == "uninstall":
                # Generate uninstallation script
                state = await self.script_generator.generate_script(state)
                if state.has_error:
                    return state
                
                # Execute the script
                state = await self.script_executor.execute(state)
                if state.has_error:
                    return await self._handle_workflow_failure(state)
                
                workflow_logger.info("Uninstallation completed successfully")
                
            else:
                raise WorkflowError(f"Unsupported action: {state.action}")
            
            return state.mark_completed()
            
        except WorkflowError as e:
            workflow_logger.error("Workflow error: %s", e)
            return await self._handle_workflow_failure(state, e)
        except InitializationError as e:
            workflow_logger.error("Initialization error: %s", e)
            return await self._handle_workflow_failure(state, e)
        except Exception as e:
            workflow_logger.error("Unexpected error: %s", e, exc_info=True)
            return await self._handle_workflow_failure(state, e)

    async def _handle_workflow_failure(
        self, 
        state: WorkflowState, 
        error: Optional[Exception] = None
    ) -> WorkflowState:
        """Handle workflow failure and perform recovery if needed."""
        error_message = str(error) if error else state.error or "Unknown error"
        logger.error("Workflow failed: %s", error_message)
        
        # Add error to state if not already set
        if not state.error:
            state = state.set_error(error_message)
        
        # Attempt recovery if needed
        if self.config.use_recovery:
            try:
                logger.info("Attempting recovery")
                state = await self.recovery_manager.recover(state)
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
            return await agent.run_workflow(state)
                
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
            return await agent.run_workflow(state)
                
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
            return await agent.run_workflow(state)
                
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
