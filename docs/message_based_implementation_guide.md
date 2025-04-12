# Message-Based Architecture Implementation Guide

This guide provides detailed instructions and best practices for working with the message-based architecture in the IntegrationsAgentPOC system.

## Overview

The system uses a standardized message-based architecture where all agent communication follows a consistent pattern:

1. Agents inherit from `MultiAgentBase` 
2. Messages use the `MultiAgentMessage` format
3. The `CoordinatorAgent` handles message routing
4. Agents register message handlers for specific message types
5. Messages are processed asynchronously through message queues

## Core Components

### MultiAgentMessage

The standard message format used for all communication:

```python
class MultiAgentMessage:
    def __init__(
        self, 
        sender: str,               # Agent that sent the message
        message_type: str,         # Type of message (from MessageType)
        content: Any,              # Message payload
        metadata: Dict[str, Any],  # Additional context information
        priority: str = "medium",  # Message priority
        message_id: str = None,    # Unique identifier (auto-generated if None)
        in_response_to: str = None # ID of message this is responding to
    )
```

### MessageType

Standard message types for different operations:

```python
class MessageType:
    KNOWLEDGE_REQUEST = "knowledge_request"
    KNOWLEDGE_RESPONSE = "knowledge_response"
    EXECUTION_REQUEST = "execution_request"
    EXECUTION_RESPONSE = "execution_response"
    VERIFICATION_REQUEST = "verification_request"
    VERIFICATION_RESPONSE = "verification_response"
    SCRIPT_GENERATION_REQUEST = "script_generation_request"
    SCRIPT_GENERATION_RESPONSE = "script_generation_response"
    SCRIPT_VALIDATION_REQUEST = "script_validation_request"
    SCRIPT_VALIDATION_RESPONSE = "script_validation_response"
    ERROR_REPORT = "error_report"
    STATUS_UPDATE = "status_update"
    IMPROVEMENT_SUGGESTION = "improvement_suggestion"
    WORKFLOW_STATUS_UPDATE = "workflow_status_update"
```

### MultiAgentBase

Base class that all agents inherit from, providing message handling capabilities:

```python
class MultiAgentBase(ABC):
    def __init__(self, coordinator, agent_id):
        # Initialize message handling infrastructure
        
    async def send_message(
        self, 
        recipient: str,
        message_type: str,
        content: Any,
        metadata: Dict[str, Any] = None,
        priority: str = "medium",
        wait_for_response: bool = False,
        response_timeout: float = None
    ) -> Union[bool, MultiAgentMessage]:
        # Send a message to another agent
        
    async def receive_message(self, message: MultiAgentMessage) -> bool:
        # Process an incoming message
        
    def register_message_handler(self, message_type: str, handler: callable) -> None:
        # Register a handler for a specific message type
        
    async def _handle_message(self, message: MultiAgentMessage) -> None:
        # Abstract method that must be implemented by subclasses
```

## Implementation Guide

### 1. Creating a New Agent

To create a new agent that uses the message-based architecture:

```python
from workflow_agent.multi_agent.base import MultiAgentBase, MessageType
from workflow_agent.multi_agent.interfaces import ExecutionAgentInterface

class CustomExecutionAgent(ExecutionAgentInterface):
    def __init__(self, coordinator):
        super().__init__(coordinator=coordinator, agent_id="custom_execution")
        
        # Register message handlers
        self.register_message_handler(MessageType.EXECUTION_REQUEST, self._handle_execution_request)
    
    # Implement required interface methods
    async def execute_task(self, task, context=None):
        # Implementation details
        return {"result": "Success"}
        
    async def validate_execution(self, execution_result):
        # Implementation details
        return {"valid": True}
        
    async def handle_execution_error(self, error, task, context):
        # Implementation details
        return {"recovery": "retry"}
    
    # Implement message handlers
    async def _handle_execution_request(self, message):
        try:
            # Extract content
            content = message.content
            task = content.get("task", {})
            
            # Process the request
            result = await self.execute_task(task)
            
            # Create response
            response = message.create_response(
                content={"result": result},
                metadata={"success": True}
            )
            
            # Send response
            await self.coordinator.route_message(response, message.sender)
            
        except Exception as e:
            # Create error response
            error_response = message.create_response(
                content={"error": str(e)},
                metadata={"success": False}
            )
            await self.coordinator.route_message(error_response, message.sender)
    
    # Implement the abstract method
    async def _handle_message(self, message):
        logger.warning(f"No specific handler for message type: {message.message_type}")
```

### 2. Sending Messages

To send messages between agents:

```python
# Simple message without waiting for response
await agent.send_message(
    recipient="knowledge",
    message_type=MessageType.KNOWLEDGE_REQUEST,
    content={"query": "Get information about monitoring agent"},
    metadata={"workflow_id": workflow_id}
)

# Send message and wait for response
try:
    response = await agent.send_message(
        recipient="execution",
        message_type=MessageType.EXECUTION_REQUEST,
        content={"task": task_data},
        metadata={"workflow_id": workflow_id},
        wait_for_response=True,
        response_timeout=60  # seconds
    )
    
    if response.metadata.get("success", False):
        # Process successful response
        result = response.content.get("result")
        print(f"Execution successful: {result}")
    else:
        # Handle error
        error = response.content.get("error", "Unknown error")
        print(f"Execution failed: {error}")
        
except MultiAgentError as e:
    # Handle timeout or routing error
    print(f"Message error: {e}")
```

### 3. Responding to Messages

To respond to received messages:

```python
# Create a response to a received message
response = message.create_response(
    content={
        "result": execution_result,
        "metrics": performance_metrics
    },
    metadata={
        "success": True,
        "execution_time": 5.2
    }
)

# Send the response
await self.coordinator.route_message(response, message.sender)
```

### 4. Error Handling

For proper error handling in message processing:

```python
try:
    # Process the message
    result = await self._process_request(message.content)
    
    # Create success response
    response = message.create_response(
        content={"result": result},
        metadata={"success": True}
    )
    
except ValidationError as e:
    # Handle validation errors
    response = message.create_response(
        content={"error": f"Validation error: {str(e)}"},
        metadata={"success": False, "error_type": "validation"}
    )
    
except TimeoutError as e:
    # Handle timeout errors
    response = message.create_response(
        content={"error": f"Operation timed out: {str(e)}"},
        metadata={"success": False, "error_type": "timeout"}
    )
    
except Exception as e:
    # Handle unexpected errors
    logger.exception(f"Error processing message: {e}")
    response = message.create_response(
        content={"error": f"Unexpected error: {str(e)}"},
        metadata={"success": False, "error_type": "unexpected"}
    )
    
finally:
    # Always send a response
    await self.coordinator.route_message(response, message.sender)
```

### 5. Message Priorities

To use message priorities effectively:

```python
# High priority message (for critical operations)
await agent.send_message(
    recipient="coordinator",
    message_type=MessageType.ERROR_REPORT,
    content={"error": "Critical execution failure"},
    metadata={"workflow_id": workflow_id},
    priority=MessagePriority.HIGH
)

# Medium priority message (default, for normal operations)
await agent.send_message(
    recipient="knowledge",
    message_type=MessageType.KNOWLEDGE_REQUEST,
    content={"query": "Get information about monitoring agent"},
    metadata={"workflow_id": workflow_id},
    priority=MessagePriority.MEDIUM
)

# Low priority message (for background operations)
await agent.send_message(
    recipient="improvement",
    message_type=MessageType.IMPROVEMENT_SUGGESTION,
    content={"metrics": performance_metrics},
    metadata={"workflow_id": workflow_id},
    priority=MessagePriority.LOW
)
```

## Best Practices

### 1. Message Structure

- Keep message content concise and relevant
- Include all necessary context in the metadata
- Use consistent key names across similar messages
- Include workflow IDs in metadata for traceability

### 2. Error Handling

- Always handle exceptions in message handlers
- Send error responses with descriptive messages
- Include error types in metadata for better classification
- Log detailed error information for troubleshooting

### 3. Message Handlers

- Register specific handlers for each message type
- Keep handlers focused on a single responsibility
- Extract common functionality into helper methods
- Use the generic `_handle_message` method as a fallback

### 4. Performance Considerations

- Keep message content serializable
- Don't include large objects in messages
- Use references to shared resources when possible
- Add timeouts to prevent blocking operations

### 5. Testing

- Create mock coordinator for testing message handling
- Test both successful and error scenarios
- Verify proper response generation
- Check message routing and priority handling

## Example Implementation

Complete example of an agent using the message-based architecture:

```python
import logging
import asyncio
from typing import Dict, Any, Optional

from workflow_agent.multi_agent.base import MultiAgentBase, MessageType, MessagePriority
from workflow_agent.multi_agent.interfaces import VerificationAgentInterface
from workflow_agent.error.exceptions import VerificationError

logger = logging.getLogger(__name__)

class EnhancedVerificationAgent(VerificationAgentInterface):
    """
    Enhanced verification agent using the message-based architecture.
    """
    
    def __init__(self, coordinator):
        super().__init__(coordinator=coordinator, agent_id="verification")
        
        # Register message handlers
        self.register_message_handler(MessageType.VERIFICATION_REQUEST, self._handle_verification_request)
        self.register_message_handler(MessageType.STATUS_UPDATE, self._handle_status_update)
    
    # Interface implementations
    async def verify_execution(self, execution_result, context):
        """Verify execution results."""
        try:
            # Extract expected values
            expected_exit_code = context.get("expected_exit_code", 0)
            expected_output = context.get("expected_output")
            
            # Get actual results
            exit_code = execution_result.get("exit_code")
            output = execution_result.get("output", "")
            
            # Verify results
            exit_code_match = exit_code == expected_exit_code
            output_match = True
            
            if expected_output and expected_output not in output:
                output_match = False
                
            # Return verification result
            return {
                "passed": exit_code_match and output_match,
                "details": {
                    "exit_code_match": exit_code_match,
                    "output_match": output_match,
                    "expected_exit_code": expected_exit_code,
                    "actual_exit_code": exit_code
                }
            }
        except Exception as e:
            raise VerificationError(f"Error verifying execution: {str(e)}")
    
    async def verify_system_state(self, state):
        """Verify the system state."""
        # Implementation details...
        return {"passed": True, "details": {"checks_passed": 5, "total_checks": 5}}
    
    async def verify_security(self, artifact, artifact_type):
        """Verify security aspects of an artifact."""
        # Implementation details...
        return {"passed": True, "vulnerabilities": []}
    
    # Message handlers
    async def _handle_verification_request(self, message):
        """Handle verification request messages."""
        try:
            content = message.content
            verification_type = content.get("verification_type", "execution")
            
            result = None
            
            if verification_type == "execution":
                # Verify execution
                execution_result = content.get("execution_result", {})
                context = content.get("context", {})
                result = await self.verify_execution(execution_result, context)
                
            elif verification_type == "system_state":
                # Verify system state
                state = content.get("state")
                result = await self.verify_system_state(state)
                
            elif verification_type == "security":
                # Verify security
                artifact = content.get("artifact")
                artifact_type = content.get("artifact_type", "unknown")
                result = await self.verify_security(artifact, artifact_type)
                
            else:
                # Unknown verification type
                raise VerificationError(f"Unknown verification type: {verification_type}")
            
            # Create response
            response = message.create_response(
                content={"result": result, "verification_type": verification_type},
                metadata={"success": True, "passed": result.get("passed", False)}
            )
            
            # Send response
            await self.coordinator.route_message(response, message.sender)
            
        except Exception as e:
            logger.error(f"Error handling verification request: {e}", exc_info=True)
            
            # Send error response
            error_response = message.create_response(
                content={"error": str(e)},
                metadata={"success": False, "passed": False}
            )
            await self.coordinator.route_message(error_response, message.sender)
    
    async def _handle_status_update(self, message):
        """Handle status update messages."""
        logger.info(f"Received status update: {message.content}")
        
        # No response needed for status updates
    
    async def _handle_message(self, message):
        """Handle messages without specific handlers."""
        logger.warning(f"No specific handler for message type: {message.message_type}")
        
        # Create a generic response
        response = message.create_response(
            content={"error": f"No handler for message type: {message.message_type}"},
            metadata={"success": False}
        )
        await self.coordinator.route_message(response, message.sender)
```

For more details, refer to the [Message-Based Architecture](message_based_architecture.md) documentation.
