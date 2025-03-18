# Workflow Agent

A Python framework for orchestrating multi-step workflows with AI-driven adaptation and self-improvement capabilities, featuring dynamic documentation-based integration.

## Quick Start

```bash
# Install the package
git clone https://github.com/yourusername/workflow-agent.git
cd workflow-agent
pip install -e .

# Run a basic installation workflow
workflow-agent install infra_agent --license-key=YOUR_LICENSE_KEY --host=YOUR_HOST
```

## Installation

### Prerequisites
- Python 3.8 or higher
- Docker (optional, for isolated execution)

### Installation Steps
```bash
# Clone the repository
git clone https://github.com/yourusername/workflow-agent.git
cd workflow-agent

# Install the package and dependencies
pip install -e .

# Install optional dependencies
pip install -e ".[llm]"  # For LLM integration
pip install -e ".[dev]"  # For development tools
pip install -e ".[doc]"  # For documentation tools
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

# Specify a custom configuration file
workflow-agent install infra_agent --license-key=KEY --config-path=./custom_config.yaml
```

### Programmatic Usage

```python
import asyncio
from workflow_agent.core.message_bus import MessageBus
from workflow_agent.multi_agent.coordinator import CoordinatorAgent
from workflow_agent.knowledge.integration import DynamicIntegrationKnowledge
from workflow_agent.documentation.parser import DocumentationParser
from workflow_agent.strategy.installation import InstallationStrategyAgent

async def run_workflow():
    # Set up multi-agent system
    message_bus = MessageBus()
    coordinator = CoordinatorAgent(message_bus)
    await coordinator.initialize()
    
    # Initialize dynamic components
    doc_parser = DocumentationParser()
    knowledge = DynamicIntegrationKnowledge(doc_parser)
    strategy = InstallationStrategyAgent()
    
    # Define workflow state
    from workflow_agent.core.state import WorkflowState
    from workflow_agent.utils.system import get_system_context
    
    state = WorkflowState(
        action="install",
        target_name="monitoring_agent",
        integration_type="infra_agent",
        parameters={
            "license_key": "YOUR_LICENSE_KEY",
            "host": "your.host.com"
        },
        system_context=get_system_context()
    )
    
    # Execute dynamic workflow
    try:
        # Enhance state with documentation knowledge
        state = await knowledge.enhance_workflow_state(state)
        
        # Determine best installation strategy
        state = await strategy.determine_best_approach(state)
        
        # Start the workflow execution
        result = await coordinator.start_workflow(state.dict())
        workflow_id = result.get("workflow_id")
        
        if workflow_id:
            final_result = await coordinator.wait_for_completion(workflow_id, timeout=60)
            print(f"Workflow completed: {final_result}")
    except Exception as e:
        print(f"Workflow failed: {e}")

# Run the workflow
asyncio.run(run_workflow())
```

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

## Troubleshooting

### Common Issues

**1. No such file or directory errors**

```
Error: No such file or directory: './integrations/common_templates'
```

**Solution:** Check that the template directory exists and is correctly referenced in your configuration.

```bash
# Create the template directory
mkdir -p ./integrations/common_templates

# Or specify a custom template directory in config
echo 'configurable:
  template_dir: "/path/to/your/templates"' > workflow_config.yaml
```

**2. Docker isolation failures**

```
Error: Docker not available, falling back to direct execution
```

**Solution:** Ensure Docker is installed and running, or disable Docker isolation:

```yaml
# In workflow_config.yaml
configurable:
  use_isolation: false
  isolation_method: "direct"
```

**3. Documentation parsing errors**

```
Error: Failed to fetch documentation for [integration_type]
```

**Solution:** Check your network connection and verify the integration type is correct. You can also provide local YAML definitions:

1. Create directory: `src/workflow_agent/integrations/[integration_type]/[target_name]/`
2. Add files: `definition.yaml`, `parameters.yaml`, and `verification.yaml`

**4. Permission denied errors during script execution**

```
Error: Permission denied
```

**Solution:** The script may need elevated privileges. Use one of these approaches:

```yaml
# In workflow_config.yaml, enable least privilege execution
configurable:
  least_privilege_execution: true
```

**5. Timeouts during execution**

```
Error: Script execution timed out after [X]s
```

**Solution:** Increase the execution timeout in configuration:

```yaml
configurable:
  execution_timeout: 60000  # 60 seconds (in milliseconds)
```

### Debugging

To enable more detailed logging:

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or in configuration file
configurable:
  log_level: "DEBUG"
```

Log files are stored in the current directory by default. To inspect execution history:

```python
import sqlite3

# Connect to the history database
conn = sqlite3.connect("workflow_history.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Query recent executions
cursor.execute("SELECT * FROM execution_history ORDER BY timestamp DESC LIMIT 5")
for row in cursor.fetchall():
    print(f"ID: {row['id']}, Status: {row['success']}, Error: {row['error_message']}")
```

## Advanced Troubleshooting

### Generating Test Scripts

You can generate a script without executing it:

```python
import asyncio
from workflow_agent.scripting.dynamic_generator import DynamicScriptGenerator
from workflow_agent.knowledge.integration import DynamicIntegrationKnowledge
from workflow_agent.documentation.parser import DocumentationParser
from workflow_agent.core.state import WorkflowState
from workflow_agent.utils.system import get_system_context

async def generate_test_script():
    # Create a test state
    state = WorkflowState(
        action="install",
        target_name="monitoring_agent",
        integration_type="infra_agent",
        parameters={"license_key": "test", "host": "test"},
        system_context=get_system_context()
    )
    
    # Fetch documentation and enhance state
    doc_parser = DocumentationParser()
    knowledge = DynamicIntegrationKnowledge(doc_parser)
    state = await knowledge.enhance_workflow_state(state)
    
    # Generate script
    generator = DynamicScriptGenerator()
    result = await generator.generate_from_knowledge(state)
    
    if "script" in result:
        with open("test_script.sh", "w") as f:
            f.write(result["script"])
        print("Script generated: test_script.sh")
    else:
        print(f"Error: {result.get('error')}")

asyncio.run(generate_test_script())
```

### Checking System Integration

Verify system resources and integration compatibility:

```bash
# Create a Python script to check system compatibility
cat > check_system.py << EOF
import asyncio
from workflow_agent.utils.system import get_system_context
from workflow_agent.integrations.registry import IntegrationRegistry

async def check_system():
    system_context = get_system_context()
    print("System Information:")
    print(f"- OS: {system_context['platform']['system']}")
    print(f"- Docker available: {system_context['docker_available']}")
    print(f"- Package managers: {', '.join([k for k, v in system_context['package_managers'].items() if v])}")
    
    print("\\nAvailable integrations:")
    for integration_type in IntegrationRegistry._integrations:
        targets = IntegrationRegistry.get_integrations_for_target(integration_type)
        if targets:
            print(f"- {integration_type}: {', '.join(targets)}")

asyncio.run(check_system())
EOF

# Run the check
python check_system.py
```

If all else fails, check the documentation at [https://github.com/yourusername/workflow-agent](https://github.com/yourusername/workflow-agent) or file an issue with your error logs attached.