"""Main workflow agent implementation."""
import logging
import uuid
import os
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .core.state import WorkflowState, Change, OutputData, ExecutionMetrics
from .config.configuration import ensure_workflow_config
from .config.templates import reload_templates
from .storage.history import HistoryManager
from .scripting.generator import ScriptGenerator
from .scripting.validator import ScriptValidator
from .execution.executor import ScriptExecutor, ResourceLimiter
from .verification.verifier import Verifier
from .rollback.recovery import RecoveryManager
from .integrations.registry import IntegrationRegistry
from .utils.system import get_system_context
from .error.exceptions import WorkflowError, ValidationError, ExecutionError

logger = logging.getLogger(__name__)

@dataclass
class AgentConfig:
    """Base configuration for all agents."""
    name: str
    description: str
    max_concurrent_tasks: int = 5
    use_isolation: bool = True
    isolation_method: str = "docker"
    execution_timeout: int = 300

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
    isolation_method: str = "docker"
    execution_timeout: int = 300000
    skip_verification: bool = False
    rule_based_optimization: bool = True
    use_static_analysis: bool = True
    resource_limiter: Optional[ResourceLimiter] = None

class WorkflowAgent:
    """An agent that orchestrates multi-step workflows with validation and rollback."""
    
    def __init__(self, config: Optional[WorkflowAgentConfig] = None):
        """Initialize the workflow agent with dependency injection."""
        self.workflow_config = config or WorkflowAgentConfig()
        
        # Create agent config
        self.config = AgentConfig(
            name="WorkflowAgent",
            description="An agent that orchestrates multi-step workflows with validation and rollback",
            max_concurrent_tasks=self.workflow_config.max_concurrent_tasks,
            use_isolation=self.workflow_config.use_isolation,
            isolation_method=self.workflow_config.isolation_method,
            execution_timeout=self.workflow_config.execution_timeout
        )
        
        # Set up resource limiter
        resource_limiter = self.workflow_config.resource_limiter or ResourceLimiter(
            max_concurrent=self.workflow_config.max_concurrent_tasks
        )
        
        # Initialize components with dependency injection
        self.history_manager = self.workflow_config.history_manager or HistoryManager()
        self.script_generator = self.workflow_config.script_generator or ScriptGenerator(self.history_manager)
        self.script_validator = self.workflow_config.script_validator or ScriptValidator()
        self.script_executor = self.workflow_config.script_executor or ScriptExecutor(
            self.history_manager, 
            timeout=self.workflow_config.execution_timeout // 1000,  # Convert ms to seconds
            max_concurrent=self.workflow_config.max_concurrent_tasks,
            resource_limiter=resource_limiter
        )
        self.verifier = self.workflow_config.verifier or Verifier()
        self.recovery_manager = self.workflow_config.recovery_manager or RecoveryManager(self.history_manager)
    
    def get_capabilities(self) -> List[str]:
        """Get a list of the agent's capabilities."""
        return [
            "template_script_generation",
            "script_validation",
            "script_execution",
            "result_verification",
            "error_handling",
            "automatic_rollback",
            "execution_history"
        ]
    
    async def invoke(self, input_state: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Invoke the workflow agent with full workflow execution."""
        try:
            workflow_config = ensure_workflow_config(config or {})
            state_dict = dict(input_state)
            
            # Generate transaction ID if not provided
            if "transaction_id" not in state_dict:
                state_dict["transaction_id"] = str(uuid.uuid4())
            
            # Create workflow state
            state = WorkflowState(**state_dict)
            
            # Get system context if not provided
            if not state.system_context:
                state.system_context = get_system_context()
            
            # Auto-prune history if configured
            if workflow_config.prune_history_days:
                await self.history_manager.auto_prune_history(workflow_config.prune_history_days)
            
            # 1. Validate parameters
            result = await self._validate_parameters(state, config)
            if "error" in result:
                state.error = result["error"]
                return state.dict()
            
            # 2. Generate script
            result = await self.script_generator.generate_script(state, config)
            if "error" in result:
                state.error = result["error"]
                return state.dict()
            
            state.script = result.get("script")
            state.template_key = result.get("template_key")
            
            # 3. Validate script
            result = await self.script_validator.validate_script(state, config)
            if "error" in result:
                state.error = result["error"]
                return state.dict()
            
            if "warnings" in result:
                state.warnings = result["warnings"]
            
            # 4. Execute script
            result = await self.script_executor.run_script(state, config)
            if "error" in result:
                state.error = result["error"]
                
                # Attempt rollback on error
                rollback_result = await self.recovery_manager.rollback_changes(state, config)
                if "error" in rollback_result:
                    state.warnings.append(f"Rollback failed: {rollback_result['error']}")
                
                return state.dict()
            
            # Update state with execution results
            if "output" in result:
                if isinstance(result["output"], OutputData):
                    state.output = result["output"]
                else:
                    state.output = OutputData(**result["output"])
            
            if "metrics" in result:
                if isinstance(result["metrics"], ExecutionMetrics):
                    state.metrics = result["metrics"]
                else:
                    state.metrics = ExecutionMetrics(**result["metrics"])
            
            if "changes" in result:
                state.changes = result["changes"]
            
            if "legacy_changes" in result:
                state.legacy_changes = result["legacy_changes"]
            
            if "transaction_id" in result:
                state.transaction_id = result["transaction_id"]
            
            if "execution_id" in result:
                state.execution_id = result["execution_id"]
            
            # 5. Verify results (unless skip_verification is True)
            if not workflow_config.skip_verification:
                verify_result = await self.verifier.verify_result(state, config)
                if "error" in verify_result:
                    state.error = verify_result["error"]
                    
                    # Attempt rollback on verification error
                    rollback_result = await self.recovery_manager.rollback_changes(state, config)
                    if "error" in rollback_result:
                        state.warnings.append(f"Rollback failed: {rollback_result['error']}")
                    
                    return state.dict()
                
                if "warning" in verify_result:
                    state.warnings.append(verify_result["warning"])
            
            return state.dict()
            
        except ValidationError as e:
            return {"error": str(e), "messages": input_state.get("messages", [])}
        except ExecutionError as e:
            return {"error": str(e), "messages": input_state.get("messages", [])}
        except Exception as e:
            return {"error": f"Workflow execution failed: {str(e)}", "messages": input_state.get("messages", [])}
        finally:
            await self.cleanup()
    
    async def _validate_parameters(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate workflow parameters."""
        try:
            if not state.parameters:
                state.parameters = {}
            
            if not isinstance(state.parameters, dict):
                return {"error": "Invalid parameters: expected a dictionary."}
            
            # Validate parameter schema if present
            if state.parameter_schema:
                missing = []
                for key, spec in state.parameter_schema.items():
                    if spec.required and key not in state.parameters:
                        missing.append(key)
                
                if missing:
                    return {"error": f"Missing required parameters: {', '.join(missing)}"}
            
            return {}
        except Exception as e:
            return {"error": f"Parameter validation failed: {str(e)}"}
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the workflow agent."""
        try:
            # Initialize database connection
            await self.history_manager.initialize(config)
            
            # Initialize recovery manager
            await self.recovery_manager.initialize(config)
            
            # Initialize script executor
            await self.script_executor.initialize(config)
            
            # Reload templates
            reload_templates()
            
        except Exception as e:
            await self.cleanup()
            raise RuntimeError(f"Agent initialization failed: {str(e)}") from e
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if hasattr(self, 'history_manager'):
                await self.history_manager.cleanup()
            
            if hasattr(self, 'script_executor'):
                await self.script_executor.cleanup()
            
            if hasattr(self, 'recovery_manager'):
                await self.recovery_manager.cleanup()
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

class WorkflowAgentFactory:
    """Factory class for creating workflow agents."""
    
    @staticmethod
    def create_agent() -> WorkflowAgent:
        """Create a new workflow agent instance."""
        return WorkflowAgent()