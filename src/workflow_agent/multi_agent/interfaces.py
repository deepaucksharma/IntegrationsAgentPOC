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
    
    async def _handle_message(self, message: MultiAgentMessage) -> None:
        """
        Handle messages for the knowledge agent.
        
        Args:
            message: Message to process
        """
        # Handle knowledge requests
        if message.message_type == MessageType.KNOWLEDGE_REQUEST:
            try:
                # Extract query and context
                content = message.content
                query = content.get("query", "")
                context = content.get("context", {})
                
                # Retrieve knowledge
                knowledge = await self.retrieve_knowledge(query, context)
                
                # Create response
                response = message.create_response(
                    content={"knowledge": knowledge, "query": query},
                    metadata={"confidence": knowledge.get("confidence", 0.0)}
                )
                
                # Send response
                recipient = message.sender
                await self.coordinator.route_message(response, recipient)
                
            except Exception as e:
                logger.error(f"Error handling knowledge request: {e}", exc_info=True)
                
                # Send error response
                error_response = message.create_response(
                    content={"error": str(e), "query": message.content.get("query", "")},
                    metadata={"success": False}
                )
                await self.coordinator.route_message(error_response, message.sender)

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
    
    async def _handle_message(self, message: MultiAgentMessage) -> None:
        """
        Handle messages for the execution agent.
        
        Args:
            message: Message to process
        """
        # Handle execution requests
        if message.message_type == MessageType.EXECUTION_REQUEST:
            try:
                # Extract task and context
                content = message.content
                task = content.get("task", {})
                context = content.get("context", {})
                
                # Execute task
                result = await self.execute_task(task, context)
                
                # Create response
                response = message.create_response(
                    content={"result": result, "task": task},
                    metadata={"success": True}
                )
                
                # Send response
                recipient = message.sender
                await self.coordinator.route_message(response, recipient)
                
            except Exception as e:
                logger.error(f"Error handling execution request: {e}", exc_info=True)
                
                # Try to handle the error
                content = message.content
                task = content.get("task", {})
                context = content.get("context", {})
                
                try:
                    # Attempt error recovery
                    recovery_result = await self.handle_execution_error(e, task, context)
                    
                    # Send recovery response
                    recovery_response = message.create_response(
                        content={
                            "error": str(e),
                            "recovery": recovery_result,
                            "task": task
                        },
                        metadata={"success": False, "recovered": True}
                    )
                    await self.coordinator.route_message(recovery_response, message.sender)
                    
                except Exception as e2:
                    # Send error response if recovery fails
                    logger.error(f"Error recovery failed: {e2}", exc_info=True)
                    error_response = message.create_response(
                        content={"error": str(e), "task": task},
                        metadata={"success": False, "recovered": False}
                    )
                    await self.coordinator.route_message(error_response, message.sender)

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
    
    async def _handle_message(self, message: MultiAgentMessage) -> None:
        """
        Handle messages for the verification agent.
        
        Args:
            message: Message to process
        """
        # Handle verification requests
        if message.message_type == MessageType.VERIFICATION_REQUEST:
            try:
                # Extract content
                content = message.content
                verification_type = content.get("verification_type", "execution")
                
                # Different verification types
                if verification_type == "execution":
                    execution_result = content.get("execution_result", {})
                    context = content.get("context", {})
                    result = await self.verify_execution(execution_result, context)
                elif verification_type == "state":
                    state = content.get("state")
                    if not isinstance(state, WorkflowState):
                        raise ValueError("State verification requires a WorkflowState object")
                    result = await self.verify_system_state(state)
                elif verification_type == "security":
                    artifact = content.get("artifact")
                    artifact_type = content.get("artifact_type", "unknown")
                    result = await self.verify_security(artifact, artifact_type)
                else:
                    raise ValueError(f"Unknown verification type: {verification_type}")
                
                # Create response
                response = message.create_response(
                    content={"result": result, "verification_type": verification_type},
                    metadata={"success": True, "passed": result.get("passed", False)}
                )
                
                # Send response
                recipient = message.sender
                await self.coordinator.route_message(response, recipient)
                
            except Exception as e:
                logger.error(f"Error handling verification request: {e}", exc_info=True)
                
                # Send error response
                error_response = message.create_response(
                    content={
                        "error": str(e), 
                        "verification_type": message.content.get("verification_type", "unknown")
                    },
                    metadata={"success": False}
                )
                await self.coordinator.route_message(error_response, message.sender)

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
    
    async def _handle_message(self, message: MultiAgentMessage) -> None:
        """
        Handle messages for the improvement agent.
        
        Args:
            message: Message to process
        """
        # Handle improvement suggestion requests
        if message.message_type == MessageType.IMPROVEMENT_SUGGESTION:
            try:
                # Extract content
                content = message.content
                metrics = content.get("metrics", {})
                
                # Analyze performance
                analysis = await self.analyze_performance(metrics)
                
                # Generate improvement suggestions
                suggestions = await self.generate_improvements(analysis)
                
                # Create response
                response = message.create_response(
                    content={
                        "analysis": analysis,
                        "suggestions": suggestions
                    },
                    metadata={"success": True}
                )
                
                # Send response
                recipient = message.sender
                await self.coordinator.route_message(response, recipient)
                
            except Exception as e:
                logger.error(f"Error handling improvement suggestion request: {e}", exc_info=True)
                
                # Send error response
                error_response = message.create_response(
                    content={"error": str(e)},
                    metadata={"success": False}
                )
                await self.coordinator.route_message(error_response, message.sender)
