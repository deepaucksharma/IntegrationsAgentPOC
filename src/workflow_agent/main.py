"""
Main entry point for the workflow agent with enhanced script generation and error handling.
"""
import asyncio
import logging
import sys
import os
import uuid
import traceback
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Type, Union, Tuple
from pathlib import Path

import typer
from typing_extensions import Annotated
from pydantic import ValidationError

from .core.state import WorkflowState, WorkflowStage, WorkflowStatus
from .core.service_container import ServiceContainer
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
from .error.handler import ErrorHandler, handle_safely_async
from .utils.platform_utils import is_windows

logger = logging.getLogger(__name__)

class WorkflowAgent:
    """Orchestrates workflows with enhanced error recovery and monitoring."""
    
    def __init__(self, config: Optional[Union[Dict[str, Any], WorkflowConfiguration]] = None):
        """
        Initialize with configuration validation and dependency injection.
        
        Args:
            config: Optional configuration (dictionary or WorkflowConfiguration)
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        try:
            # Ensure we have a valid configuration
            self.config = ensure_workflow_config(config)
            
            # Configure logging early for better debugging
            self._configure_logging()
            
            # Create service container
            self.container = ServiceContainer()
            self.container.build_default_container(self.config)
            
            # Initialize services
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.container.initialize_services())
            
            logger.info("Workflow agent initialized successfully")
            
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise ConfigurationError(f"Invalid configuration: {e}") from e
        except Exception as e:
            logger.error(f"Initialization failed: {e}", exc_info=True)
            raise InitializationError(f"Failed to initialize workflow agent: {e}") from e

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

    @handle_safely_async
    async def run_workflow(self, state: WorkflowState) -> WorkflowState:
        """
        Execute workflow with enhanced monitoring, checkpointing, and recovery.
        Implements a more structured workflow with clear stages and better error handling.
        
        Args:
            state: Initial workflow state
            
        Returns:
            Final workflow state after execution
        """
        workflow_logger = get_workflow_logger(
            "workflow_agent.workflow",
            workflow_id=state.transaction_id,
            execution_id=state.execution_id,
            integration_type=state.integration_type,
            action=state.action
        )
        
        try:
            workflow_logger.info("Starting workflow execution: %s for %s", state.action, state.target_name)
            
            # Get state manager
            state_manager = self.container.get("state_manager")
            
            # Initialization Phase - checkpoint before starting
            state = state_manager.apply_state_transition(
                state, 
                lambda s: s.create_checkpoint(WorkflowStage.INITIALIZATION)
            )
            workflow_logger.info("Created initialization checkpoint")
            
            # Validate inputs first
            state = await self._validate_workflow_inputs(state)
            if state.has_error:
                workflow_logger.error("Input validation failed: %s", state.error)
                return state
                
            # Get and validate integration
            integration_manager = self.container.get("integration_manager")
            integration = integration_manager.get_integration(state.integration_type)
            if not integration:
                error_msg = f"Integration {state.integration_type} not found"
                workflow_logger.error(error_msg)
                return state.set_error(error_msg)
            
            # Set up action-specific workflow
            if state.action == "install":
                return await self._run_install_workflow(state, workflow_logger)
            elif state.action == "verify":
                return await self._run_verify_workflow(state, workflow_logger)
            elif state.action == "uninstall":
                return await self._run_uninstall_workflow(state, workflow_logger)
            else:
                error_msg = f"Unsupported action: {state.action}"
                workflow_logger.error(error_msg)
                return state.set_error(error_msg)
            
        except WorkflowError as e:
            workflow_logger.error("Workflow error: %s", e)
            return await self._handle_workflow_failure(state, e)
        except InitializationError as e:
            workflow_logger.error("Initialization error: %s", e)
            return await self._handle_workflow_failure(state, e)
        except Exception as e:
            workflow_logger.error("Unexpected error: %s", e, exc_info=True)
            return await self._handle_workflow_failure(state, e)
            
    async def _validate_workflow_inputs(self, state: WorkflowState) -> WorkflowState:
        """
        Validate workflow inputs before execution.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state with validation results
        """
        state = state.mark_validating()
        
        # Check required fields
        if not state.target_name:
            return state.set_error("Target name is required")
            
        if not state.integration_type:
            return state.set_error("Integration type is required")
            
        # Validate integration-specific parameters
        integration_manager = self.container.get("integration_manager")
        integration = integration_manager.get_integration(state.integration_type)
        if integration and hasattr(integration, "validate_parameters"):
            try:
                validation_result = await integration.validate_parameters(state.parameters)
                
                if isinstance(validation_result, dict):
                    # New style: returns dict with valid and errors keys
                    if not validation_result.get("valid", False):
                        errors = validation_result.get("errors", [])
                        error_msg = "; ".join(errors) if errors else "Parameter validation failed"
                        return state.set_error(f"Parameter validation failed: {error_msg}")
                else:
                    # Old style: returns tuple of (valid, message)
                    valid, message = validation_result
                    if not valid:
                        return state.set_error(f"Parameter validation failed: {message}")
                        
            except Exception as e:
                return state.set_error(f"Parameter validation error: {str(e)}")
                
        # Create validation checkpoint
        return state.set_stage(WorkflowStage.VALIDATION).create_checkpoint(WorkflowStage.VALIDATION)
            
    async def _run_install_workflow(self, state: WorkflowState, logger) -> WorkflowState:
        """
        Run installation workflow with checkpointing.
        
        Args:
            state: Current workflow state
            logger: Logger instance for this workflow
            
        Returns:
            Updated workflow state after installation
        """
        logger.info("Starting installation workflow")
        
        # 1. Script Generation Phase
        logger.info("Generating installation script")
        state = state.mark_generating().set_stage(WorkflowStage.GENERATION)
        
        # Generate the script
        script_generator = self.container.get("script_generator")
        state = await script_generator.generate_script(state)
        if state.has_error:
            logger.error("Script generation failed: %s", state.error)
            return state
            
        # Create checkpoint after script generation
        state = state.create_checkpoint(WorkflowStage.GENERATION)
        logger.info("Script generation completed and checkpoint created")
        
        # 2. Script Execution Phase
        logger.info("Executing installation script")
        state = state.mark_executing().set_stage(WorkflowStage.EXECUTION)
        
        # Execute the script
        script_executor = self.container.get("script_executor")
        execution_start_time = datetime.now()
        state = await script_executor.execute(state)
        execution_time = (datetime.now() - execution_start_time).total_seconds()
        logger.info(f"Script execution completed in {execution_time:.2f} seconds")
        
        if state.has_error:
            logger.error("Script execution failed: %s", state.error)
            return await self._handle_workflow_failure(state)
            
        # Create checkpoint after execution
        state = state.create_checkpoint(WorkflowStage.EXECUTION)
        
        # 3. Verification Phase
        if not self.config.skip_verification:
            logger.info("Verifying installation")
            state = state.mark_verifying().set_stage(WorkflowStage.VERIFICATION)
            
            # Verify the installation
            verification_manager = self.container.get("verification_manager")
            state = await verification_manager.verify(state)
            
            if state.has_error:
                logger.error("Verification failed: %s", state.error)
                return await self._handle_workflow_failure(state)
                
            # Create checkpoint after verification
            state = state.create_checkpoint(WorkflowStage.VERIFICATION)
            logger.info("Verification completed and checkpoint created")
        else:
            logger.warning("Verification skipped per configuration")
            
        # 4. Completion Phase
        logger.info("Installation completed successfully")
        state = state.mark_completed().set_stage(WorkflowStage.COMPLETION)
        state = state.create_checkpoint(WorkflowStage.COMPLETION)
        
        return state
        
    async def _run_verify_workflow(self, state: WorkflowState, logger) -> WorkflowState:
        """
        Run verification workflow.
        
        Args:
            state: Current workflow state
            logger: Logger instance for this workflow
            
        Returns:
            Updated workflow state after verification
        """
        logger.info("Starting verification workflow")
        
        # Set verification stage
        state = state.mark_verifying().set_stage(WorkflowStage.VERIFICATION)
        
        # Run verification
        verification_manager = self.container.get("verification_manager")
        state = await verification_manager.verify(state)
        
        # Create checkpoint
        state = state.create_checkpoint(WorkflowStage.VERIFICATION)
        
        logger.info("Verification completed with status: %s", state.status)
        
        # Complete
        if not state.has_error:
            state = state.mark_completed().set_stage(WorkflowStage.COMPLETION)
            state = state.create_checkpoint(WorkflowStage.COMPLETION)
            
        return state
        
    async def _run_uninstall_workflow(self, state: WorkflowState, logger) -> WorkflowState:
        """
        Run uninstallation workflow with checkpointing.
        
        Args:
            state: Current workflow state
            logger: Logger instance for this workflow
            
        Returns:
            Updated workflow state after uninstallation
        """
        logger.info("Starting uninstallation workflow")
        
        # 1. Script Generation Phase
        logger.info("Generating uninstallation script")
        state = state.mark_generating().set_stage(WorkflowStage.GENERATION)
        
        # Generate the script
        script_generator = self.container.get("script_generator")
        state = await script_generator.generate_script(state)
        if state.has_error:
            logger.error("Script generation failed: %s", state.error)
            return state
            
        # Create checkpoint after script generation
        state = state.create_checkpoint(WorkflowStage.GENERATION)
        
        # 2. Script Execution Phase
        logger.info("Executing uninstallation script")
        state = state.mark_executing().set_stage(WorkflowStage.EXECUTION)
        
        # Execute the script
        script_executor = self.container.get("script_executor")
        state = await script_executor.execute(state)
        if state.has_error:
            logger.error("Script execution failed: %s", state.error)
            return await self._handle_workflow_failure(state)
            
        # Create checkpoint after execution
        state = state.create_checkpoint(WorkflowStage.EXECUTION)
        
        # 3. Verification Phase (light verification for uninstall)
        if not self.config.skip_verification:
            logger.info("Verifying uninstallation")
            state = state.mark_verifying().set_stage(WorkflowStage.VERIFICATION)
            
            # Simple verification for uninstall (check key files/services are gone)
            verification_manager = self.container.get("verification_manager")
            state = await verification_manager.verify_uninstall(state)
            
            if state.has_error:
                logger.warning("Uninstall verification had issues: %s", state.error)
                state = state.add_warning(f"Uninstall verification had issues: {state.error}")
                # Don't fail the workflow just for verification warnings during uninstall
                state = state.evolve(error=None)
                
            # Create checkpoint after verification
            state = state.create_checkpoint(WorkflowStage.VERIFICATION)
        else:
            logger.warning("Verification skipped per configuration")
            
        # 4. Completion Phase
        logger.info("Uninstallation completed successfully")
        state = state.mark_completed().set_stage(WorkflowStage.COMPLETION)
        state = state.create_checkpoint(WorkflowStage.COMPLETION)
        
        return state

    async def _handle_workflow_failure(
        self, 
        state: WorkflowState, 
        error: Optional[Exception] = None
    ) -> WorkflowState:
        """
        Handle workflow failure with enhanced recovery and cleanup.
        Includes better error classification and possible retry logic.
        
        Args:
            state: Current workflow state
            error: Optional exception that caused the failure
            
        Returns:
            Updated workflow state after recovery attempts
        """
        error_message = str(error) if error else state.error or "Unknown error"
        logger.error("Workflow failed: %s", error_message)
        
        # Add error to state if not already set
        if not state.error:
            state = state.set_error(error_message)
        
        # Check if this is a retryable failure and retry count not exceeded
        should_retry = self._should_retry_workflow(state, error)
        
        if should_retry:
            logger.info(f"Attempting to retry workflow (attempt {state.retry_count + 1}/{state.max_retries})")
            return await self._retry_workflow(state)
        
        # If not retrying, attempt recovery if configured
        if self.config.use_recovery:
            try:
                logger.info("Attempting recovery")
                recovery_start = datetime.now()
                
                # Use the enhanced recovery manager
                recovery_manager = self.container.get("recovery_manager")
                state = await recovery_manager.recover(state)
                
                recovery_duration = (datetime.now() - recovery_start).total_seconds()
                logger.info(f"Recovery completed in {recovery_duration:.2f} seconds with status: {state.status}")
                
                # Verify recovery if verification is enabled
                if self.config.verify_rollback and state.status == WorkflowStatus.REVERTED:
                    logger.info("Verifying system state after recovery")
                    # Simple verification to ensure system is clean
                    try:
                        verification_manager = self.container.get("verification_manager")
                        verify_result = await verification_manager.verify_system_clean(state)
                        if verify_result.has_error:
                            logger.warning(f"Post-recovery verification had issues: {verify_result.error}")
                            state = state.add_warning(f"Post-recovery verification had issues: {verify_result.error}")
                    except Exception as verify_error:
                        logger.error(f"Error during post-recovery verification: {verify_error}")
                        state = state.add_warning(f"Post-recovery verification error: {str(verify_error)}")
                    
            except Exception as recovery_error:
                logger.error("Recovery failed: %s", recovery_error, exc_info=True)
                state = state.add_warning(f"Recovery failed: {recovery_error}")
        else:
            logger.info("Recovery is disabled, skipping")
            state = state.add_warning("Recovery was not attempted because it is disabled")
        
        # Cleanup any temporary files
        await self._cleanup_temp_files(state)
        
        return state
        
    def _should_retry_workflow(self, state: WorkflowState, error: Optional[Exception] = None) -> bool:
        """
        Determine if a workflow failure should be retried.
        
        Args:
            state: Current workflow state
            error: Optional exception that caused the failure
            
        Returns:
            True if workflow should be retried, False otherwise
        """
        # Don't retry if max retries reached
        if state.retry_count >= state.max_retries:
            logger.info(f"Max retry count reached ({state.retry_count}/{state.max_retries}), not retrying")
            return False
            
        # Use the ErrorHandler to determine if the error is retryable
        from .error.handler import ErrorHandler
        
        if error and ErrorHandler.is_retriable(error):
            logger.info(f"Error type {type(error).__name__} is retryable")
            return True
            
        # Check if error message suggests a retryable issue
        if state.error:
            retryable_patterns = [
                "timeout",
                "connection refused", 
                "network error",
                "temporarily unavailable"
            ]
            
            if any(pattern in state.error.lower() for pattern in retryable_patterns):
                logger.info(f"Error message suggests a retryable issue")
                return True
                
        # Check if we're in a stage that's generally safe to retry
        retryable_stages = [
            WorkflowStage.INITIALIZATION,
            WorkflowStage.VALIDATION,
            WorkflowStage.GENERATION
        ]
        
        if state.current_stage in retryable_stages:
            logger.info(f"Current stage {state.current_stage} is safe to retry")
            return True
            
        # Default to not retrying
        return False
        
    async def _retry_workflow(self, state: WorkflowState) -> WorkflowState:
        """
        Retry a failed workflow from appropriate checkpoint.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state after retry attempt
        """
        # Increment retry count
        state = state.mark_retry()
        logger.info(f"Retrying workflow (attempt {state.retry_count}/{state.max_retries})")
        
        # Determine stage to retry from based on checkpoints
        retry_stage = self._determine_retry_stage(state)
        logger.info(f"Retrying from stage: {retry_stage}")
        
        # Create a new state for retry, maintaining key information
        retry_state = WorkflowState(
            action=state.action,
            target_name=state.target_name,
            integration_type=state.integration_type,
            parameters=state.parameters,
            template_data=state.template_data,
            system_context=state.system_context,
            retry_count=state.retry_count,
            transaction_id=state.transaction_id,
            parent_state_id=state.state_id
        )
        
        # Set appropriate stage
        retry_state = retry_state.set_stage(retry_stage)
        
        # Re-run the workflow
        return await self.run_workflow(retry_state)
        
    def _determine_retry_stage(self, state: WorkflowState) -> WorkflowStage:
        """
        Determine which stage to retry from based on checkpoints.
        
        Args:
            state: Current workflow state
            
        Returns:
            Stage to restart workflow from
        """
        # Try to start from the current stage
        current_stage = state.current_stage
        
        # If execution already happened, start from there to avoid side effects
        if current_stage == WorkflowStage.EXECUTION and WorkflowStage.GENERATION.value in state.checkpoints:
            return WorkflowStage.GENERATION
            
        # If verification failed, try again from verification
        if current_stage == WorkflowStage.VERIFICATION:
            return WorkflowStage.VERIFICATION
            
        # Default to starting from the beginning
        return WorkflowStage.INITIALIZATION
        
    async def _cleanup_temp_files(self, state: WorkflowState) -> None:
        """
        Clean up any temporary files created during the workflow.
        
        Args:
            state: Current workflow state
        """
        # Clean up backup files if they exist
        for backup_file in state.backup_files:
            try:
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                    logger.debug(f"Removed temporary file: {backup_file}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {backup_file}: {e}")
                
    async def install(self, integration_type: str, parameters: Dict[str, Any]) -> WorkflowState:
        """
        Convenience method to install an integration.
        
        Args:
            integration_type: Type of integration to install
            parameters: Installation parameters
            
        Returns:
            Final workflow state
        """
        state_manager = self.container.get("state_manager")
        
        # Create initial state
        state = state_manager.create_state(
            action="install",
            target_name=f"{integration_type}-integration",
            integration_type=integration_type,
            parameters=parameters,
            system_context=get_system_context()
        )
        
        # Run the workflow
        return await self.run_workflow(state)
        
    async def verify(self, integration_type: str, parameters: Dict[str, Any]) -> WorkflowState:
        """
        Convenience method to verify an integration.
        
        Args:
            integration_type: Type of integration to verify
            parameters: Verification parameters
            
        Returns:
            Final workflow state
        """
        state_manager = self.container.get("state_manager")
        
        # Create initial state
        state = state_manager.create_state(
            action="verify",
            target_name=f"{integration_type}-integration",
            integration_type=integration_type,
            parameters=parameters,
            system_context=get_system_context()
        )
        
        # Run the workflow
        return await self.run_workflow(state)
        
    async def uninstall(self, integration_type: str, parameters: Dict[str, Any]) -> WorkflowState:
        """
        Convenience method to uninstall an integration.
        
        Args:
            integration_type: Type of integration to uninstall
            parameters: Uninstallation parameters
            
        Returns:
            Final workflow state
        """
        state_manager = self.container.get("state_manager")
        
        # Create initial state
        state = state_manager.create_state(
            action="uninstall",
            target_name=f"{integration_type}-integration",
            integration_type=integration_type,
            parameters=parameters,
            system_context=get_system_context()
        )
        
        # Run the workflow
        return await self.run_workflow(state)
        
    async def generate_script_with_agent(self, state: WorkflowState) -> WorkflowState:
        """
        Generate a script using the agent-based approach.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state with script
        """
        from .agent.base_agent import AgentContext
        
        # Get the script generation agent
        script_agent = self.container.get("script_generation_agent")
        
        # Create agent context
        context = AgentContext(workflow_state=state)
        
        # Execute agent
        result = await script_agent.execute(context)
        
        # Return the updated state
        return result.workflow_state
        
    async def verify_with_agent(self, state: WorkflowState) -> WorkflowState:
        """
        Verify an integration using the agent-based approach.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state with verification results
        """
        from .agent.base_agent import AgentContext
        
        # Get the verification agent
        verification_agent = self.container.get("verification_agent")
        
        # Create agent context
        context = AgentContext(workflow_state=state)
        
        # Execute agent with retry
        result = await verification_agent.execute_with_retry(context)
        
        # Return the updated state
        return result.workflow_state

# Create CLI app
app = typer.Typer()

@app.command()
def install(
    integration: str,
    license_key: str = typer.Option(..., help="License key for the integration"),
    host: str = typer.Option("localhost", help="Target host for installation"),
    config_file: Optional[str] = typer.Option(None, help="Path to configuration file"),
    install_dir: str = typer.Option("./InfraAgent", help="Installation directory path"),
    config_path: str = typer.Option("./InfraAgent/config", help="Configuration directory path"),
    log_path: str = typer.Option("./InfraAgent/logs", help="Log directory path"),
    port: int = typer.Option(8080, help="Port number for the integration")
):
    """Install an integration."""
    try:
        # Prepare parameters
        parameters = {
            "license_key": license_key,
            "host": host,
            "install_dir": install_dir,
            "config_path": config_path,
            "log_path": log_path,
            "port": port
        }
        
        async def run():
            # Initialize with configuration file if provided
            config = None
            if config_file:
                from .config.configuration import load_configuration_from_file
                config = load_configuration_from_file(config_file)
                
            # Initialize agent and run installation
            agent = WorkflowAgent(config)
            return await agent.install(integration, parameters)
        
        # Initialize with configuration file if provided
        config = None
        if config_file:
            from .config.configuration import load_configuration_from_file
            config = load_configuration_from_file(config_file)
            
        # Initialize the agent and run the workflow
        agent = WorkflowAgent(config)
        result = asyncio.run(run())
        if result.has_error:
            logger.error(f"Installation failed: {result.error}")
            sys.exit(1)
        else:
            logger.info("Installation completed successfully")
            
    except Exception as e:
        logger.error(f"Installation failed: {e}")
        sys.exit(1)

@app.command()
def verify(
    integration: str,
    host: str = typer.Option("localhost", help="Target host for verification"),
    config_file: Optional[str] = typer.Option(None, help="Path to configuration file"),
    install_dir: str = typer.Option("./InfraAgent", help="Installation directory path"),
    config_path: str = typer.Option("./InfraAgent/config", help="Configuration directory path"),
    log_path: str = typer.Option("./InfraAgent/logs", help="Log directory path"),
    port: int = typer.Option(8080, help="Port number for the integration")
):
    """Verify an integration installation."""
    try:
        # Prepare parameters
        parameters = {
            "host": host,
            "install_dir": install_dir,
            "config_path": config_path,
            "log_path": log_path,
            "port": port
        }
        
        async def run():
            # Initialize with configuration file if provided
            config = None
            if config_file:
                from .config.configuration import load_configuration_from_file
                config = load_configuration_from_file(config_file)
                
            # Initialize agent and run verification
            agent = WorkflowAgent(config)
            return await agent.verify(integration, parameters)
        
        async def run():
            # Initialize with configuration file if provided
            config = None
            if config_file:
                from .config.configuration import load_configuration_from_file
                config = load_configuration_from_file(config_file)
                
            # Initialize and run workflow
            agent = WorkflowAgent(config)
            return await agent.run_workflow(state)
                
        result = asyncio.run(run())
        if result.has_error:
            logger.error(f"Verification failed: {result.error}")
            sys.exit(1)
        else:
            logger.info("Verification completed successfully")
            
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        sys.exit(1)

@app.command()
def remove(
    integration: str,
    host: str = typer.Option("localhost", help="Target host for removal"),
    config_file: Optional[str] = typer.Option(None, help="Path to configuration file"),
    install_dir: str = typer.Option("./InfraAgent", help="Installation directory path"),
    config_path: str = typer.Option("./InfraAgent/config", help="Configuration directory path"),
    log_path: str = typer.Option("./InfraAgent/logs", help="Log directory path"),
    port: int = typer.Option(8080, help="Port number for the integration")
):
    """Remove an integration."""
    try:
        # Prepare parameters
        parameters = {
            "host": host,
            "install_dir": install_dir,
            "config_path": config_path,
            "log_path": log_path,
            "port": port
        }
        
        async def run():
            # Initialize with configuration file if provided
            config = None
            if config_file:
                from .config.configuration import load_configuration_from_file
                config = load_configuration_from_file(config_file)
                
            # Initialize agent and run uninstallation
            agent = WorkflowAgent(config)
            return await agent.uninstall(integration, parameters)
        
        async def run():
            # Initialize with configuration file if provided
            config = None
            if config_file:
                from .config.configuration import load_configuration_from_file
                config = load_configuration_from_file(config_file)
                
            # Initialize and run workflow
            agent = WorkflowAgent(config)
            return await agent.run_workflow(state)
                
        result = asyncio.run(run())
        if result.has_error:
            logger.error(f"Removal failed: {result.error}")
            sys.exit(1)
        else:
            logger.info("Removal completed successfully")
            
    except Exception as e:
        logger.error(f"Removal failed: {e}")
        sys.exit(1)

def main():
    """Main entry point for the CLI."""
    try:
        app()
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(130)  # 130 is the standard exit code for SIGINT
    except Exception as e:
        logger.error(f"Command failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
