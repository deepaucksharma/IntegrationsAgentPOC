"""
Main entry point for the workflow agent.
"""
import asyncio
import logging
import sys
from typing import Any, Dict, Optional

from .core.state import WorkflowState
from .core.message_bus import MessageBus
from .execution import ScriptExecutor
from .scripting import ScriptGenerator, ScriptValidator, DynamicScriptGenerator
from .verification import DynamicVerificationBuilder
from .knowledge import DynamicIntegrationKnowledge
from .strategy import InstallationStrategyAgent
from .rollback import RollbackManager
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
        self.integration_knowledge = DynamicIntegrationKnowledge()
        self.installation_strategy = InstallationStrategyAgent()
        self.rollback_manager = RollbackManager(executor=self.executor)
        
        # Initialize template environment and load templates
        initialize_template_environment([self.config.template_dir])
        load_templates()
        
        # Initialize executor
        asyncio.run(self.executor.initialize())
    
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
                    script_generation_result = await self.script_generator.generate_script(state, config=self.config)
                elif state.action in ["install", "setup", "remove", "uninstall"]:
                    script_generation_result = await self.dynamic_script_generator.generate_from_knowledge(state)
                else:
                    script_generation_result = {"error": "No template or dynamic script generation available for this action."}
                
                if script_generation_result.get("error"):
                    return script_generation_result
                state.script = script_generation_result["script"]
            
            # Validate script
            validation_result = await self.script_validator.validate_script(state, config=self.config)
            if validation_result.get("warnings"):
                for warning in validation_result["warnings"]:
                    logger.warning(f"Script validation warning: {warning}")
            if validation_result.get("error"):
                return validation_result
            
            # Run script
            execution_result = await self.executor.run_script(state, config=self.config)
            if execution_result.get("error"):
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
                verification_result = await self.executor.run_script(verification_state, config=self.config)
                if verification_result.get("error"):
                    logger.error(f"Verification failed: {verification_result['error']}")
                    # Rollback if verification fails
                    await self.rollback_manager.perform_rollback(state, config=self.config)
                    return verification_result
                
            return execution_result
        
        except Exception as e:
            logger.exception(f"Unexpected error during workflow execution: {e}")
            return {"error": str(e)}
    
    async def close(self) -> None:
        """Closes the agent and releases resources."""
        await self.executor.cleanup()
        logger.info("Workflow agent closed.")