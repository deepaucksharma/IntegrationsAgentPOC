# IntegrationsAgentPOC

Proof of concept for an agentic integration workflow system using LLMs and multi-agent architectures.

## Overview

This project demonstrates an LLM-powered, multi-agent system for automating the installation, verification, and uninstallation of monitoring integrations. It leverages multiple specialized agents that collaborate to:

1. **Knowledge Retrieval**: Gather integration-specific requirements and procedures
2. **Script Generation**: Create installation/verification/uninstallation scripts
3. **Execution**: Run scripts safely with change tracking and isolation
4. **Verification**: Validate successful integration
5. **Recovery**: Implement fallback mechanisms when operations fail

## Architecture

The system now uses a fully message-based architecture, where all agent communication follows a standardized pattern:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  KnowledgeAgent │     │ ScriptBuilder   │     │ ExecutionAgent  │
│  (Knowledge     │     │ (Script         │     │ (Task           │
│   Management)   │     │  Generation)    │     │  Execution)     │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │                       │                       │
         │     ┌─────────────────┐                       │
         └─────┤                 ├───────────────────────┘
               │  Coordinator    │
         ┌─────┤  (Message      ├───────────────────────┐
         │     │   Routing)     │                       │
         │     └─────────────────┘                       │
         │                       │                       │
┌────────┴────────┐     ┌────────┴────────┐     ┌────────┴────────┐
│ VerificationAgent│     │ ImprovementAgent│     │ WorkflowTracker │
│ (Verification &  │     │ (System         │     │ (State          │
│  Validation)     │     │  Improvement)   │     │  Management)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

Key components:

1. **MultiAgentBase**: Foundation class providing message handling and routing capabilities
2. **Specialized Interfaces**: Defined contracts for each agent type with required methods
3. **Message System**: Standardized format for all inter-agent communication
4. **Coordinator**: Central message routing and workflow orchestration
5. **WorkflowTracker**: Immutable workflow state history and checkpointing
6. **Recovery System**: Sophisticated error handling with multiple recovery strategies

## Getting Started

### Prerequisites

- Python 3.10+
- PowerShell 5.1+ (for Windows scripts)
- Bash (for Linux/Unix scripts)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/IntegrationsAgentPOC.git
   cd IntegrationsAgentPOC
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/MacOS
   venv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install the package in development mode:
   ```bash
   pip install -e .
   ```

### Configuration

Create a `workflow_config.yaml` file or use the provided example:

```yaml
# Basic configuration
log_level: INFO
template_dir: ./templates
script_dir: ./generated_scripts

# Security settings
security:
  least_privilege_execution: true
  verify_recoveries: true

# Execution settings
isolation_method: direct  # Options: direct, docker
use_llm: true
```

## Usage

### Running via PowerShell

```powershell
.\agentic_workflow.ps1 -Action install -IntegrationType infra_agent -LicenseKey "your-license-key"
```

### Running via Python

```bash
python -m workflow_agent install infra_agent --license-key "your-license-key" --host "localhost"
```

### Enhanced Workflow Example

For a demonstration of the new message-based architecture and recovery capabilities:

```bash
python examples/enhanced_workflow_test.py --action install --integration infra_agent --license "your-license-key"
```

## Project Structure

```
IntegrationsAgentPOC/
├── src/workflow_agent/           # Main package
│   ├── core/                     # Core framework components
│   ├── multi_agent/              # Multi-agent system
│   │   ├── base.py               # Base message system
│   │   ├── interfaces.py         # Agent interfaces
│   │   ├── coordinator.py        # Message routing and orchestration
│   │   ├── verification.py       # Verification agent
│   │   ├── recovery.py           # Error recovery system
│   │   └── workflow_tracker.py   # State tracking and checkpoints
│   ├── execution/                # Script execution with isolation
│   ├── templates/                # Template handling
│   ├── storage/                  # Knowledge storage and caching
│   ├── plugins/                  # Plugin system
│   └── utils/                    # Utility functions
├── templates/                    # Script templates
├── plugins/                      # Integration plugins
├── examples/                     # Example scripts
├── docs/                         # Documentation
│   ├── refactoring/              # Refactoring documentation
│   └── message_based_architecture.md # Architecture details
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests
│   └── integration/              # Integration tests
└── generated_scripts/            # Output directory for scripts
```

## Documentation

For more detailed information, refer to:
- [Documentation Index](docs/INDEX.md)
- [Architecture Overview](docs/architecture-readme.md)
- [Message-Based Architecture](docs/message_based_architecture.md)
- [Code Standards](docs/code_standards.md)
- [Refactoring Implementation](README-refactoring.md)
- [API Documentation](docs/INDEX.md)

## Development

### Agent Implementation Example

To implement a new agent using the interface-based design:

```python
from workflow_agent.multi_agent.interfaces import ExecutionAgentInterface
from workflow_agent.multi_agent.base import MessageType, MessagePriority

class CustomExecutionAgent(ExecutionAgentInterface):
    def __init__(self, coordinator):
        super().__init__(coordinator=coordinator, agent_id="custom_execution")
        self.register_message_handler(MessageType.EXECUTION_REQUEST, self._handle_execution_request)
    
    async def execute_task(self, task, context=None):
        # Implementation of required interface method
        return {"success": True, "output": "Task executed successfully"}
        
    async def validate_execution(self, execution_result):
        # Implementation of required interface method
        return {"valid": True}
        
    async def handle_execution_error(self, error, task, context):
        # Implementation of required interface method
        return {"recovery_action": "retry"}
    
    async def _handle_message(self, message):
        # Generic message handler
        self.logger.warning(f"No handler for message type: {message.message_type}")
```

### Message Sending Example

To send messages between agents:

```python
# Send a message and wait for response
response = await agent.send_message(
    recipient="knowledge",
    message_type=MessageType.KNOWLEDGE_REQUEST,
    content={"query": "Get information about monitoring agent"},
    metadata={"workflow_id": workflow_id},
    wait_for_response=True,
    response_timeout=30  # seconds
)

# Process the response
if response and response.content.get("knowledge"):
    knowledge = response.content["knowledge"]
    print(f"Received knowledge: {knowledge}")
```

## Maintenance

To clean up the project directories and archive old files:

```powershell
.\cleanup_script.ps1
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
