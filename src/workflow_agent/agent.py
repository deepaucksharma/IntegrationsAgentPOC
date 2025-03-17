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
from .error.exceptions import WorkflowError, ValidationError, ExecutionError
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class WorkflowAgentConfig:
    """Configuration for WorkflowAgent components."""
    history_manager: Optional[HistoryManager] = None
    script_generator: Optional[ScriptGenerator] = None
    script_validator: Optional[ScriptValidator] = None
    script_executor: Optional[ScriptExecutor] = None
    verifier: Optional[Verifier] = None
    recovery_manager: Optional[RecoveryManager] = None
    max_concurrent_tasks: int = 5
    use_isolation: bool = True
    isolation_method: str = "sandbox"
    execution_timeout: int = 300
    skip_verification: bool = False
    use_llm_optimization: bool = True
    rule_based_optimization: bool = True
    use_static_analysis: bool = True

class WorkflowAgent(AbstractWorkflowAgent):
    """An agent that orchestrates multi-step workflows with validation and rollback."""
    
    def __init__(self, config: Optional[WorkflowAgentConfig] = None):
        """Initialize the workflow agent with dependency injection."""
        super().__init__("WorkflowAgent", "An agent that orchestrates multi-step workflows with validation and rollback")
        
        self.config = config or WorkflowAgentConfig()
        
        # Initialize components with dependency injection
        self.history_manager = self.config.history_manager or HistoryManager()
        self.script_generator = self.config.script_generator or ScriptGenerator(self.history_manager)
        self.script_validator = self.config.script_validator or ScriptValidator()
        self.script_executor = self.config.script_executor or ScriptExecutor(self.history_manager)
        self.verifier = self.config.verifier or Verifier()
        self.recovery_manager = self.config.recovery_manager or RecoveryManager(self.history_manager)
        
        # Set up workflow graph
        self.graph = self._create_workflow_graph()
        
        # Create workflow executor with concurrency control
        self.workflow_executor = WorkflowExecutor(
            self.graph,
            max_concurrent_tasks=self.config.max_concurrent_tasks
        )
    
    def _create_workflow_graph(self) -> WorkflowGraph:
        """Create and configure the workflow graph."""
        graph = WorkflowGraph()
        
        # Add workflow nodes
        graph.add_node("validate_parameters", self._validate_parameters)
        graph.add_node("generate_script", self._generate_script)
        graph.add_node("validate_script", self._validate_script)
        graph.add_node("run_script", self._run_script)
        graph.add_node("verify_result", self._verify_result)
        graph.add_node("rollback_changes", self._rollback_changes)
        
        # Set up transitions
        graph.add_transition("validate_parameters", "generate_script")
        graph.add_transition("generate_script", "validate_script")
        graph.add_transition("validate_script", "run_script")
        graph.add_transition("run_script", "verify_result")
        graph.add_transition("verify_result", None)  # End node
        graph.add_transition("rollback_changes", None)  # End node
        
        return graph
    
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
        """Invoke the workflow agent with improved error handling and validation."""
        try:
            workflow_config = ensure_workflow_config(config)
            state_dict = dict(input_state)
            
            logger.info(f"Invoking workflow agent for {state_dict.get('action', 'unknown')} on {state_dict.get('target_name', 'unknown')}")
            
            # Generate transaction ID if not provided
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
                    raise ValidationError(f"Invalid integration_type: {integration_type}. Valid types are: {', '.join(valid_types)}")
            
            # Handle special commands
            special_command = state_dict.get("special_command")
            if special_command == "retrieve_docs":
                return await self._handle_retrieve_docs(state_dict)
            elif special_command == "dry_run":
                return await self._handle_dry_run(state_dict, config)
            
            # Auto-prune history if configured
            if workflow_config.prune_history_days:
                await self.history_manager.auto_prune_history(workflow_config.prune_history_days)
            
            # Execute full workflow
            logger.info("Executing full workflow")
            result = await self.workflow_executor.execute_workflow(state_dict, config)
            
            return {**result, "messages": input_state.get("messages", [])}
            
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            return {"error": str(e), "messages": input_state.get("messages", [])}
        except ExecutionError as e:
            logger.error(f"Execution error: {e}")
            return {"error": str(e), "messages": input_state.get("messages", [])}
        except Exception as e:
            logger.exception("Unexpected error during workflow execution")
            return {"error": f"Workflow execution failed: {str(e)}", "messages": input_state.get("messages", [])}
        finally:
            await self.cleanup()
    
    async def _handle_retrieve_docs(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Handle documentation retrieval command."""
        logger.info(f"Handling special command: retrieve_docs for {state_dict.get('target_name')}")
        docs = f"# Documentation for {state_dict.get('action', 'default')} on {state_dict.get('target_name', 'default')}\n"
        docs += "\nThis is a placeholder for more comprehensive documentation that could be generated dynamically."
        return {"docs": docs, "messages": state_dict.get("messages", [])}
    
    async def _handle_dry_run(self, state_dict: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle dry run command."""
        logger.info(f"Handling special command: dry_run for {state_dict.get('target_name')}")
        partial_result = await self._partial_workflow(state_dict, config)
        return {**partial_result, "messages": state_dict.get("messages", [])}
    
    async def _partial_workflow(self, state_dict: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a partial workflow for dry run with improved error handling."""
        logger.info("Executing partial workflow for dry run")
        state = WorkflowState(**state_dict)
        
        try:
            # Validate parameters
            result = await self._validate_parameters(state, config)
            for key, value in result.items():
                setattr(state, key, value)
            
            if state.error:
                raise ValidationError(f"Parameter validation failed: {state.error}")
            
            # Generate script
            result = await self._generate_script(state, config)
            for key, value in result.items():
                setattr(state, key, value)
            
            if state.error:
                raise ExecutionError(f"Script generation failed: {state.error}")
            
            # Validate script
            result = await self._validate_script(state, config)
            for key, value in result.items():
                setattr(state, key, value)
            
            if state.error:
                raise ValidationError(f"Script validation failed: {state.error}")
            
            logger.info("Dry run workflow completed")
            return state.dict()
            
        except (ValidationError, ExecutionError) as e:
            logger.error(f"Dry run failed: {e}")
            state.error = str(e)
            return state.dict()
        except Exception as e:
            logger.exception("Unexpected error during dry run")
            state.error = f"Dry run failed: {str(e)}"
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
        """Clean up resources."""
        try:
            await self.history_manager.close()
            await self.script_executor.cleanup()
            await self.recovery_manager.cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

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