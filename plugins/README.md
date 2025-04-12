# Integration Plugins

This directory contains plugins that extend the functionality of the workflow agent with specific integrations.

## Available Plugins
- `infra_agent`: Infrastructure agent integration for New Relic monitoring

## Plugin Architecture

Plugins follow the message-based architecture using the plugin system infrastructure:

1. Each plugin implements the `PluginInterface`
2. Plugins register their capabilities with the `PluginManager`
3. Plugins communicate via standardized messages through the coordinator
4. Plugins can extend any aspect of the system (knowledge, execution, verification)

## Creating a New Plugin

To create a new plugin using the message-based architecture:

1. Create a new directory with your plugin name (e.g., `my_plugin`)
2. Create an `__init__.py` file with your plugin registration
3. Create a main plugin class implementing the `PluginInterface`:

```python
"""
Custom plugin for extending the system.
"""
from typing import Dict, Any, List
from workflow_agent.plugins.interface import PluginInterface
from workflow_agent.multi_agent.base import MessageType, MessagePriority

class MyCustomPlugin(PluginInterface):
    """Custom plugin implementation."""
    
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.plugin_id = "my_custom_plugin"
        self.capabilities = ["knowledge_provider", "script_generator"]
        
    async def initialize(self) -> bool:
        """Initialize the plugin."""
        # Register with coordinator
        result = await self.coordinator.send_message(
            recipient="coordinator",
            message_type=MessageType.REGISTRATION,
            content={
                "plugin_id": self.plugin_id,
                "capabilities": self.capabilities
            },
            metadata={"priority": MessagePriority.HIGH},
            wait_for_response=True
        )
        return result and result.metadata.get("success", False)
        
    async def handle_message(self, message: Any) -> bool:
        """Handle incoming messages."""
        if message.message_type == MessageType.KNOWLEDGE_REQUEST:
            # Handle knowledge requests
            query = message.content.get("query", "")
            if "my_integration" in query:
                # This plugin handles this query
                knowledge = self._retrieve_custom_knowledge()
                
                # Send response
                response = message.create_response(
                    content={"knowledge": knowledge},
                    metadata={"success": True}
                )
                await self.coordinator.route_message(response, message.sender)
                return True
                
        return False  # Message not handled
        
    def _retrieve_custom_knowledge(self) -> Dict[str, Any]:
        """Retrieve custom knowledge for this plugin."""
        return {
            "name": "My Custom Integration",
            "description": "Custom integration plugin",
            "version": "1.0.0",
            "parameters": [
                {"name": "api_key", "type": "string", "required": True},
                {"name": "endpoint", "type": "string", "default": "api.example.com"}
            ]
        }
```

4. Register the plugin with the plugin manager in `__init__.py`:

```python
"""Plugin registration."""
from .plugin import MyCustomPlugin

def register_plugin(plugin_manager):
    """Register this plugin with the plugin manager."""
    plugin_manager.register_plugin("my_custom_plugin", MyCustomPlugin)
```

## Message-Based Integration

Plugins interact with the system through standardized messages:

1. **Registration**: Plugins register with the coordinator on initialization
2. **Message Handling**: Plugins receive and process relevant messages
3. **Response Generation**: Plugins create standardized responses to messages
4. **Capability Declaration**: Plugins declare their capabilities during registration

## Message Types for Plugins

Plugins can handle various message types:

- `MessageType.KNOWLEDGE_REQUEST`: Requests for domain knowledge
- `MessageType.SCRIPT_GENERATION_REQUEST`: Requests for script generation
- `MessageType.VERIFICATION_REQUEST`: Requests for verification operations
- `MessageType.EXECUTION_REQUEST`: Requests for execution operations
- `MessageType.IMPROVEMENT_SUGGESTION`: Suggestions for system improvement

## Testing Plugins

To test your plugin:

1. Register it with the plugin manager
2. Send test messages to validate behavior
3. Verify proper responses are generated

Example test:

```python
async def test_my_plugin():
    # Create coordinator mock
    coordinator_mock = CoordinatorMock()
    
    # Create and initialize plugin
    plugin = MyCustomPlugin(coordinator_mock)
    await plugin.initialize()
    
    # Create test message
    test_message = MultiAgentMessage(
        sender="test",
        message_type=MessageType.KNOWLEDGE_REQUEST,
        content={"query": "Get information about my_integration"}
    )
    
    # Process message
    handled = await plugin.handle_message(test_message)
    
    # Verify results
    assert handled is True
    assert len(coordinator_mock.sent_messages) == 1
    response = coordinator_mock.sent_messages[0]
    assert "knowledge" in response.content
```

See the [PluginInterface](../src/workflow_agent/plugins/interface.py) for more details on implementing plugins.
