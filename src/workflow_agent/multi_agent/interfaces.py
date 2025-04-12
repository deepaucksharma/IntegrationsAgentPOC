"""
Interfaces for specific agent types in the multi-agent system.
These interfaces define the specialized capabilities of different agent types.
"""
import logging
from abc import abstractmethod
from typing import Dict, Any, List, Optional, Union, Set

from .base import MultiAgentBase, MultiAgentMessage, MessageType
from ..core.state import WorkflowState

logger = logging.getLogger(__name__)

class ScriptBuilderAgentInterface(MultiAgentBase):
    """
    Interface for script generation and validation agents.
    
    ScriptBuilder agents are responsible for:
    1. Generating scripts based on workflow state
    2. Validating scripts for correctness and safety
    3. Optimizing scripts for specific environments
    """
    
    @abstractmethod
    async def generate_script(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a script based on workflow state.
        
        Args:
            state: Current workflow state
            config: Additional configuration options
            
        Returns:
            Dictionary containing the generated script and related metadata
        """
        pass
    
    @abstractmethod
    async def validate_script(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate a script for correctness and safety.
        
        Args:
            state: Current workflow state containing script
            config: Additional configuration options
            
        Returns:
            Validation results
        """
        pass
    
    @abstractmethod
    async def optimize_script(self, state: WorkflowState, target_env: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize a script for a specific environment.
        
        Args:
            state: Current workflow state containing script
            target_env: Target environment details
            
        Returns:
            Optimization results including optimized script
        """
        pass

class KnowledgeAgentInterface(MultiAgentBase):
    """
    Interface for knowledge gathering and processing agents.
    
    Knowledge agents are responsible for:
    1. Retrieving and managing domain knowledge
    2. Answering queries from other agents
    3. Monitoring and updating knowledge as needed
    """
    
    @abstractmethod
    async def retrieve_knowledge(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Retrieve knowledge based on a query.
        
        Args:
            query: Knowledge query string
            context: Additional context for the query
            
        Returns:
            Dictionary containing retrieved knowledge
        """
        pass
    
    @abstractmethod
    async def update_knowledge_base(self, new_knowledge: Dict[str, Any], source: Optional[str] = None) -> bool:
        """
        Update the knowledge base with new information.
        
        Args:
            new_knowledge: Knowledge to add to the knowledge base
            source: Source of the knowledge
            
        Returns:
            True if knowledge was successfully added
        """
        pass
    
    @abstractmethod
    async def validate_knowledge(self, knowledge: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate knowledge for accuracy and consistency.
        
        Args:
            knowledge: Knowledge to validate
            
        Returns:
            Validation results with confidence scores
        """
        pass

class ExecutionAgentInterface(MultiAgentBase):
    """
    Interface for execution and task management agents.
    
    Execution agents are responsible for:
    1. Executing tasks and workflows
    2. Monitoring execution progress
    3. Handling errors and retries
    4. Reporting execution results
    """
    
    @abstractmethod
    async def execute_task(self, task: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a specific task and return results.
        
        Args:
            task: Task specification
            context: Additional execution context
            
        Returns:
            Execution results
        """
        pass
    
    @abstractmethod
    async def validate_execution(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the results of an execution.
        
        Args:
            execution_result: Results to validate
            
        Returns:
            Validation results
        """
        pass
    
    @abstractmethod
    async def handle_execution_error(self, error: Exception, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle errors during task execution.
        
        Args:
            error: Exception that occurred
            task: Task that failed
            context: Execution context
            
        Returns:
            Error handling results including recovery action
        """
        pass

class VerificationAgentInterface(MultiAgentBase):
    """
    Interface for verification and validation agents.
    
    Verification agents are responsible for:
    1. Verifying execution results
    2. Validating system state
    3. Ensuring security and compliance
    """
    
    @abstractmethod
    async def verify_execution(self, execution_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify execution results.
        
        Args:
            execution_result: Results to verify
            context: Verification context
            
        Returns:
            Verification results
        """
        pass
    
    @abstractmethod
    async def verify_system_state(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Verify the system state.
        
        Args:
            state: Current system state
            
        Returns:
            Verification results
        """
        pass
    
    @abstractmethod
    async def verify_security(self, artifact: Any, artifact_type: str) -> Dict[str, Any]:
        """
        Verify security aspects of an artifact.
        
        Args:
            artifact: Artifact to verify (script, config, etc.)
            artifact_type: Type of artifact
            
        Returns:
            Security verification results
        """
        pass

class ImprovementAgentInterface(MultiAgentBase):
    """
    Interface for agents that improve system performance over time.
    
    Improvement agents are responsible for:
    1. Analyzing system performance
    2. Suggesting improvements
    3. Learning from past executions
    """
    
    @abstractmethod
    async def analyze_performance(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze system performance and identify areas for improvement.
        
        Args:
            metrics: Performance metrics to analyze
            
        Returns:
            Analysis results
        """
        pass
    
    @abstractmethod
    async def generate_improvements(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate specific improvement suggestions based on analysis.
        
        Args:
            analysis: Performance analysis
            
        Returns:
            List of improvement suggestions
        """
        pass
    
    @abstractmethod
    async def learn_from_execution(self, execution_data: Dict[str, Any]) -> bool:
        """
        Learn from execution data to improve future performance.
        
        Args:
            execution_data: Data from a completed execution
            
        Returns:
            True if learning was successful
        """
        pass
