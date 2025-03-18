# Workflow Agent

A Python framework for orchestrating multi-step workflows with AI-driven adaptation and self-improvement capabilities.

## Overview

The Workflow Agent provides a robust system for managing complex installation, removal, and verification workflows using a multi-agent architecture. It features:

- Data-driven integration using YAML definitions
- Safe script execution with Docker isolation
- Automatic failure analysis and self-improvement
- Comprehensive logging and execution history

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/workflow-agent.git
cd workflow-agent

# Install the package
pip install -e .
```

## Usage

### Command Line Interface

```bash
# Install an integration
workflow-agent install infra_agent --license-key=YOUR_LICENSE_KEY --host=YOUR_HOST

# Remove an integration
workflow-agent remove infra_agent

# Verify an integration
workflow-agent verify infra_agent
```

### Programmatic Usage

```python
import asyncio
from workflow_agent.core.message_bus import MessageBus
from workflow_agent.multi_agent.coordinator import CoordinatorAgent
from workflow_agent.multi_agent.knowledge import KnowledgeAgent
from workflow_agent.multi_agent.script_builder import ScriptBuilderAgent
from workflow_agent.multi_agent.execution import ExecutionAgent
from workflow_agent.multi_agent.improvement import ImprovementAgent

async def run_workflow():
    # Set up multi-agent system
    message_bus = MessageBus()
    coordinator = CoordinatorAgent(message_bus)
    knowledge_agent = KnowledgeAgent(message_bus)
    script_builder = ScriptBuilderAgent(message_bus)
    execution_agent = ExecutionAgent(message_bus)
    improvement_agent = ImprovementAgent(message_bus)
    
    # Initialize agents
    await coordinator.initialize()
    await knowledge_agent.initialize()
    await script_builder.initialize()
    await execution_agent.initialize()
    await improvement_agent.initialize()
    
    # Define workflow state
    state = {
        "action": "install",
        "target_name": "monitoring_agent",
        "integration_type": "infra_agent",
        "parameters": {
            "license_key": "YOUR_LICENSE_KEY",
            "host": "your.host.com"
        }
    }
    
    # Execute workflow
    result = await coordinator.start_workflow(state)
    workflow_id = result["workflow_id"]
    final_result = await coordinator.wait_for_completion(workflow_id, timeout=60)
    
    # Clean up
    await execution_agent.cleanup()

# Run the workflow
asyncio.run(run_workflow())
```

## Architecture

The system uses a multi-agent architecture:

- **CoordinatorAgent**: Orchestrates the workflow and manages state
- **KnowledgeAgent**: Retrieves integration documentation and metadata
- **ScriptBuilderAgent**: Generates and validates scripts
- **ExecutionAgent**: Executes scripts with isolation and handles verification
- **ImprovementAgent**: Analyzes failures and improves templates

## Configuration

Configuration is managed through YAML files. Default locations:
- `./workflow_config.yaml`
- `~/.workflow_agent/config.yaml`

```yaml
configurable:
  user_id: "test_user"
  template_dir: "./integrations/common_templates"
  use_isolation: true
  isolation_method: "docker"  # or "direct"
  execution_timeout: 30000
  skip_verification: false
  rule_based_optimization: true
  use_static_analysis: true
  db_connection_string: "workflow_history.db"
  prune_history_days: 90
  max_concurrent_tasks: 5
  least_privilege_execution: true
  log_level: "INFO"
```

## Adding New Integrations

Create YAML files in the appropriate directories:

```
workflow-agent/
└── src/
    └── workflow_agent/
        └── integrations/
            └── [integration_type]/
                └── [target_name]/
                    ├── definition.yaml  # Commands for install/remove
                    ├── parameters.yaml  # Required parameters
                    └── verification.yaml  # Verification commands
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run the example workflow
python examples/test_workflow.py
```

## License

MIT License