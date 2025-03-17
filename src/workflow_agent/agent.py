import logging
import uuid
import os
from typing import Dict, Any, Optional, List
from .core.agent import AbstractWorkflowAgent, AgentState, AgentResult
from .workflow import WorkflowGraph, WorkflowExecutor
from .config.configuration import ensure_workflow_config
from .config.schemas import parameter_schemas, load_parameter_schemas
from .core.state import WorkflowState
from .storage import HistoryManager
from .scripting import ScriptGenerator, ScriptValidator
from .execution import ScriptExecutor
from .verification import Verifier
from .rollback import RecoveryManager

logger = logging.getLogger(__name__)

class WorkflowAgent(AbstractWorkflowAgent):
    """An agent that orchestrates multi-step workflows with validation and rollback."""
    
    def __init__(self):
        """Initialize the workflow agent."""
        super().__init__("WorkflowAgent", "An agent that orchestrates multi-step workflows with validation and rollback")
        
        # Create components
        self.history_manager = HistoryManager()
        self.script_generator = ScriptGenerator(self.history_manager)
        self.script_validator = ScriptValidator()
        self.script_executor = ScriptExecutor(self.history_manager)
        self.verifier = Verifier()
        self.recovery_manager = RecoveryManager(self.history_manager)
        
        # Set up workflow graph
        self.graph = WorkflowGraph()
        
        # Add workflow nodes
        self.graph.add_node("validate_parameters", self._validate_parameters)
        self.graph.add_node("generate_script", self._generate_script)
        self.graph.add_node("validate_script", self._validate_script)
        self.graph.add_node("run_script", self._run_script)
        self.graph.add_node("verify_result", self._verify_result)
        self.graph.add_node("rollback_changes", self._rollback_changes)
        
        # Set up transitions
        self.graph.add_transition("validate_parameters", "generate_script")
        self.graph.add_transition("generate_script", "validate_script")
        self.graph.add_transition("validate_script", "run_script")
        self.graph.add_transition("run_script", "verify_result")
        self.graph.add_transition("verify_result", None)  # End node
        self.graph.add_transition("rollback_changes", None)  # End node
        
        # Create workflow executor
        self.workflow_executor = WorkflowExecutor(self.graph)
    
    def get_config_schema(self) -> Dict[str, Any]:
        """
        Get the configuration schema for the agent.
        
        Returns:
            Dictionary describing the configuration schema
        """
        return {
            "user_id": "string",
            "model_name": "string",
            "system_prompt": "string",
            "template_dir": "string",
            "custom_template_dir": "string",
            "use_isolation": "boolean",
            "isolation_method": "string",
            "execution_timeout": "number",
            "skip_verification": "boolean",
            "use_llm_optimization": "boolean",
            "rule_based_optimization": "boolean",
            "use_static_analysis": "boolean",
            "db_connection_string": "string",
            "prune_history_days": "number",
            "plugin_dirs": "array",
            "async_execution": "boolean",
            "max_concurrent_tasks": "number",
            "least_privilege_execution": "boolean",
            "sandbox_isolation": "boolean",
            "log_level": "string"
        }
    
    def get_capabilities(self) -> List[str]:
        """
        Get a list of the agent's capabilities.
        
        Returns:
            List of capability strings
        """
        return [
            "template_script_generation",
            "script_optimization",
            "script_validation",
            "script_execution",
            "result_verification",
            "error_handling",
            "automatic_rollback",
            "execution_history",
            "integration_handling"
        ]
    
    async def invoke(self, input_state: AgentState, config: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Invoke the workflow agent.
        
        Args:
            input_state: Initial state dictionary
            config: Optional configuration
            
        Returns:
            Updated state dictionary after workflow execution
            
        Raises:
            ValueError: If input state is invalid
            RuntimeError: If workflow execution fails
        """
        try:
            workflow_config = ensure_workflow_config(config)
            state_dict = dict(input_state)
            
            logger.info(f"Invoking workflow agent for {state_dict.get('action', 'unknown')} on {state_dict.get('target_name', 'unknown')}")
            
            # Generate a transaction ID if not provided
            if "transaction_id" not in state_dict:
                state_dict["transaction_id"] = str(uuid.uuid4())
                logger.info(f"Generated transaction ID: {state_dict['transaction_id']}")
            
            # Apply parameter schema if not provided
            if "target_name" in state_dict and "parameter_schema" not in state_dict:
                target = state_dict["target_name"]
                if target in parameter_schemas:
                    state_dict["parameter_schema"] = parameter_schemas[target]
                    logger.debug(f"Applied parameter schema for target: {target}")
            
            # Validate integration type
            if "integration_type" in state_dict:
                integration_type = state_dict["integration_type"]
                valid_types = ["infra_agent", "aws", "azure", "gcp", "apm", "browser", "custom"]
                if integration_type not in valid_types:
                    error_msg = f"Invalid integration_type: {integration_type}. Valid types are: {', '.join(valid_types)}"
                    logger.error(error_msg)
                    return {"error": error_msg, "messages": input_state.get("messages", [])}
            
            # Handle special commands
            special_command = state_dict.get("special_command")
            if special_command == "retrieve_docs":
                logger.info(f"Handling special command: retrieve_docs for {state_dict.get('target_name')}")
                docs = f"# Documentation for {state_dict.get('action', 'default')} on {state_dict.get('target_name', 'default')}\n"
                docs += "\nThis is a placeholder for more comprehensive documentation that could be generated dynamically."
                return {"docs": docs, "messages": input_state.get("messages", [])}
            elif special_command == "dry_run":
                logger.info(f"Handling special command: dry_run for {state_dict.get('target_name')}")
                partial_result = await self._partial_workflow(state_dict, config)
                return {**partial_result, "messages": input_state.get("messages", [])}
            
            # Auto-prune history if configured
            if workflow_config.prune_history_days:
                await self.history_manager.auto_prune_history(workflow_config.prune_history_days)
            
            # Execute full workflow
            logger.info("Executing full workflow")
            
            result = await self.workflow_executor.execute_workflow(state_dict, config)
            
            agent_result = {**result, "messages": input_state.get("messages", [])}
            return agent_result
            
        except ValueError as e:
            logger.error(f"Invalid input state or configuration: {e}")
            return {"error": str(e), "messages": input_state.get("messages", [])}
        except Exception as e:
            logger.exception("Unexpected error during workflow execution")
            return {"error": f"Workflow execution failed: {str(e)}", "messages": input_state.get("messages", [])}
        finally:
            # Ensure cleanup happens even if there's an error
            await self.cleanup()
    
    async def _partial_workflow(
        self,
        state_dict: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a partial workflow for dry run.
        
        Args:
            state_dict: Initial state dictionary
            config: Optional configuration
            
        Returns:
            Updated state dictionary after partial workflow execution
        """
        logger.info("Executing partial workflow for dry run")
        state = WorkflowState(**state_dict)
        
        # Validate parameters
        try:
            result = await self._validate_parameters(state, config)
            for key, value in result.items():
                setattr(state, key, value)
        except Exception as e:
            logger.exception(f"Parameter validation failed: {e}")
            state.error = f"Parameter validation failed: {str(e)}"
            return state.dict()
        
        if state.error:
            logger.error(f"Parameter validation failed: {state.error}")
            return state.dict()
        
        # Generate script
        try:
            result = await self._generate_script(state, config)
            for key, value in result.items():
                setattr(state, key, value)
        except Exception as e:
            logger.exception(f"Script generation failed: {e}")
            state.error = f"Script generation failed: {str(e)}"
            return state.dict()
        
        if state.error:
            logger.error(f"Script generation failed: {state.error}")
            return state.dict()
        
        # Validate script
        try:
            result = await self._validate_script(state, config)
            for key, value in result.items():
                setattr(state, key, value)
        except Exception as e:
            logger.exception(f"Script validation failed: {e}")
            state.error = f"Script validation failed: {str(e)}"
            return state.dict()
        
        logger.info("Dry run workflow completed")
        return state.dict()
    
    async def _validate_parameters(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate workflow parameters."""
        try:
            from .workflow_agent.nodes.validate_parameters import validate_parameters
            return await validate_parameters(state, config)
        except ImportError:
            logger.warning("Using fallback parameter validation")
            if not state.parameters:
                state.parameters = {}
            
            if not isinstance(state.parameters, dict):
                return {"error": "Invalid parameters: expected a dictionary."}
            
            # Validate parameter types and presence if schema is provided
            warnings = []
            if state.parameter_schema:
                # Check for missing required parameters
                missing = []
                for key, spec in state.parameter_schema.items():
                    if getattr(spec, "required", False) and key not in state.parameters:
                        missing.append(key)
                
                if missing:
                    return {"error": f"Missing required parameters: {', '.join(missing)}"}
            
            logger.info("Parameter validation passed successfully")
            
            if warnings:
                return {"warnings": warnings}
            return {}
    
    async def _generate_script(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate script for the workflow."""
        return await self.script_generator.generate_script(state, config)
    
    async def _validate_script(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate the generated script."""
        return await self.script_validator.validate_script(state, config)
    
    async def _run_script(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the script."""
        return await self.script_executor.run_script(state, config)
    
    async def _verify_result(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Verify the execution results."""
        return await self.verifier.verify_result(state, config)
    
    async def _rollback_changes(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Rollback changes if execution failed."""
        return await self.recovery_manager.rollback_changes(state, config)
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the workflow agent.
        
        Args:
            config: Optional configuration
            
        Raises:
            RuntimeError: If initialization fails
        """
        logger.info(f"{self.name} initializing")
        
        try:
            # Validate configuration if provided
            if config:
                ensure_workflow_config(config)
            
            # Initialize database connection
            await self.history_manager.initialize()
            
            # Load parameter schemas from files
            if config and "configurable" in config and "template_dir" in config["configurable"]:
                schema_dir = os.path.join(config["configurable"]["template_dir"], "schemas")
                if os.path.exists(schema_dir):
                    load_parameter_schemas(schema_dir)
                else:
                    logger.warning(f"Schema directory not found: {schema_dir}")
            
            # Load custom verification commands if available
            if config and "configurable" in config and "template_dir" in config["configurable"]:
                verification_dir = os.path.join(config["configurable"]["template_dir"], "verifications")
                if os.path.exists(verification_dir):
                    from .config.configuration import load_verification_commands
                    load_verification_commands(verification_dir)
                else:
                    logger.warning(f"Verification directory not found: {verification_dir}")
            
            # Initialize script executor
            if hasattr(self, 'script_executor'):
                await self.script_executor.initialize(config)
            
            logger.info(f"{self.name} initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize {self.name}: {e}")
            # Clean up any partially initialized resources
            await self.cleanup()
            raise RuntimeError(f"Agent initialization failed: {str(e)}") from e
    
    async def cleanup(self) -> None:
        """
        Release resources held by the agent.
        
        This method ensures all resources are properly cleaned up, even if there are errors.
        """
        logger.info(f"{self.name} cleaning up resources")
        
        try:
            # Close database connections
            await self.history_manager.close()
            
            # Clean up any temporary files or resources
            if hasattr(self, 'script_executor'):
                await self.script_executor.cleanup()
            
            # Clean up workflow graph
            if hasattr(self, 'graph'):
                self.graph.clear()
            
            logger.info(f"{self.name} cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during {self.name} cleanup: {e}")
            # Don't re-raise the exception as this is cleanup

class WorkflowAgentFactory:
    """Factory class for creating workflow agents."""
    
    @staticmethod
    def create_agent() -> WorkflowAgent:
        """
        Create a new workflow agent instance.
        
        Returns:
            WorkflowAgent instance
        """
        return WorkflowAgent()
    
    @staticmethod
    def get_agent_type() -> str:
        """
        Get the agent type identifier.
        
        Returns:
            String identifying the agent type
        """
        return "workflow"