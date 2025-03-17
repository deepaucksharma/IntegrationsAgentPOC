import logging
import uuid
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from ..agent_core.interfaces import BaseAgent, AgentState, AgentResult
from .graph import graph
from .configuration import ensure_workflow_config, parameter_schemas, load_parameter_schemas
from .state import WorkflowState
from .history import Session as HistorySession, auto_prune_history

logger = logging.getLogger(__name__)

class WorkflowAgent(BaseAgent):
    """An agent that orchestrates multi-step workflows with validation and rollback."""
    
    def __init__(self):
        """Initialize the workflow agent."""
        super().__init__("WorkflowAgent", "An agent that orchestrates multi-step workflows with validation and rollback")
        self._db_session = None
    
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
        """
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
            result = await self._partial_workflow(state_dict, config)
            return {**result, "messages": input_state.get("messages", [])}
        
        # Auto-prune history if configured
        if workflow_config.prune_history_days:
            auto_prune_history(workflow_config.prune_history_days)
        
        # Execute full workflow
        logger.info("Executing full workflow")
        result = await graph.invoke(state_dict, config={"configurable": workflow_config.dict()})
        
        agent_result = {**result, "messages": input_state.get("messages", [])}
        return agent_result
    
    async def _partial_workflow(self, state_dict: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        
        # Parameter validation
        node = await graph.get_node("validate_parameters")
        result = await node(state, config)
        for key, value in result.items():
            setattr(state, key, value)
        
        if state.error:
            logger.error(f"Parameter validation failed: {state.error}")
            return state.dict()
        
        # Script generation
        node = await graph.get_node("generate_script")
        result = await node(state, config)
        for key, value in result.items():
            setattr(state, key, value)
        
        if state.error:
            logger.error(f"Script generation failed: {state.error}")
            return state.dict()
        
        # Script validation
        node = await graph.get_node("validate_script")
        result = await node(state, config)
        for key, value in result.items():
            setattr(state, key, value)
        
        logger.info("Dry run workflow completed")
        return state.dict()
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the workflow agent.
        
        Args:
            config: Optional configuration
        """
        logger.info(f"{self.name} initializing")
        
        # Initialize database session
        try:
            self._db_session = HistorySession()
            logger.info("Database session initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database session: {e}")
        
        # Load parameter schemas from files
        if config and "configurable" in config and "template_dir" in config["configurable"]:
            schema_dir = os.path.join(config["configurable"]["template_dir"], "schemas")
            if os.path.exists(schema_dir):
                load_parameter_schemas(schema_dir)
        
        # Load custom verification commands if available
        if config and "configurable" in config and "template_dir" in config["configurable"]:
            verification_dir = os.path.join(config["configurable"]["template_dir"], "verifications")
            if os.path.exists(verification_dir):
                from .configuration import load_verification_commands
                load_verification_commands(verification_dir)
    
    async def cleanup(self) -> None:
        """Release resources held by the agent."""
        logger.info(f"{self.name} cleaning up resources")
        if self._db_session:
            try:
                self._db_session.close()
                logger.info("Database session closed successfully")
            except Exception as e:
                logger.error(f"Error closing database session: {e}")

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