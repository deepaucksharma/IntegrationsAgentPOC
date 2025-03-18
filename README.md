# Workflow Agent

A Python framework for orchestrating multi-step workflows with AI-driven adaptation and self-improvement capabilities, featuring dynamic documentation-based integration.

## Prerequisites

Before installing, ensure you have:

- **Python 3.8 or higher**
  - Windows: [Download from python.org](https://www.python.org/downloads/windows/) and check "Add Python to PATH" during installation
  - macOS: `brew install python@3.10` or download from python.org
  - Linux: `sudo apt-get install python3 python3-pip python3-venv` (Ubuntu/Debian)

- **pip and venv** (usually included with Python installation)

- **Docker** (optional, for isolated execution)

## Installation

### Windows Setup

```powershell
# Verify Python is installed and in PATH
python --version
# Should display Python 3.8 or higher; if not, install from python.org

# Clone the repository
git clone https://github.com/yourusername/workflow-agent.git
cd workflow-agent

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install the package and dependencies
pip install -e .
```

### macOS/Linux Setup

```bash
# Verify Python is installed
python3 --version
# Should display Python 3.8 or higher

# Clone the repository
git clone https://github.com/yourusername/workflow-agent.git
cd workflow-agent

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the package and dependencies
pip install -e .
```

### Optional Dependencies

```bash
# For LLM integration
pip install -e ".[llm]"

# For development tools
pip install -e ".[dev]"

# For documentation tools
pip install -e ".[doc]"
```

## First-Time Setup

1. **Verify the installation**:
   ```bash
   # Check that workflow-agent is available
   workflow-agent --help
   ```

2. **Create a basic configuration file**:
   ```bash
   # Create a minimal configuration without Docker
   cp custom_config_no_docker.yaml workflow_config.yaml
   ```

3. **Verify permissions**:
   - Windows: Run PowerShell as Administrator if necessary
   - macOS/Linux: Ensure you have write access to the installation directory

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
from workflow_agent.core.state import WorkflowState
from workflow_agent.utils.system import get_system_context

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
if __name__ == "__main__":
    asyncio.run(run_workflow())
```

## Configuration

Configuration is managed through YAML files. Default locations:
- `./workflow_config.yaml` (current directory)
- `~/.workflow_agent/config.yaml` (user's home directory)

### Basic Configuration (No Docker)

```yaml
configurable:
  user_id: "test_user"
  template_dir: "./integrations/common_templates"
  use_isolation: false
  isolation_method: "direct"
  execution_timeout: 300
  skip_verification: false
  log_level: "DEBUG"
```

### Full Configuration Options

```yaml
configurable:
  user_id: "test_user"
  template_dir: "./integrations/common_templates"
  custom_template_dir: null
  use_isolation: true
  isolation_method: "docker"  # Options: "docker", "direct", "none"
  execution_timeout: 30000    # In milliseconds
  skip_verification: false
  rule_based_optimization: true
  use_static_analysis: true
  db_connection_string: "workflow_history.db"
  prune_history_days: 90
  plugin_dirs:
    - "./plugins"
  max_concurrent_tasks: 5
  least_privilege_execution: true
  log_level: "INFO"  # Options: "DEBUG", "INFO", "WARNING", "ERROR"
```

## Troubleshooting

### Initial Setup Issues

**Python not found or incorrect version**

```
Python was not found; run without arguments to install from the Microsoft Store
```

**Solution:** Install Python from python.org, check "Add Python to PATH", and restart your terminal.

```bash
# Verify Python is in PATH after installation
python --version  # Windows
python3 --version  # macOS/Linux
```

**Virtual environment activation issues**

```
Cannot activate venv: execution of scripts is disabled on this system
```

**Solution:** On Windows, run in PowerShell as Administrator:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Running Issues

**Package not found**

```
ModuleNotFoundError: No module named 'workflow_agent'
```

**Solution:** 
```bash
# Make sure you're in the project directory
cd workflow-agent

# Verify venv is activated (you should see (venv) in your prompt)
# If not, activate it:
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# Install in development mode
pip install -e .
```

**Template directory not found**

```
Error: No such file or directory: './integrations/common_templates'
```

**Solution:** Create the template directory structure:

```bash
# Create required directories
mkdir -p integrations/common_templates/install
mkdir -p integrations/common_templates/remove
mkdir -p integrations/common_templates/verify
mkdir -p integrations/common_templates/macros

# Set the template directory in your config
configurable:
  template_dir: "./integrations/common_templates"
```

**Docker isolation failures**

```
Error: Docker not available, falling back to direct execution
```

**Solution:** Ensure Docker is installed and running, or use the no-Docker configuration:

```bash
# Copy the no-Docker configuration 
cp custom_config_no_docker.yaml workflow_config.yaml
```

### Diagnostic Commands

**Check system compatibility**

```python
# Save as check_system.py
import asyncio
from workflow_agent.utils.system import get_system_context

async def check_system():
    system_context = get_system_context()
    print("System Information:")
    print(f"- OS: {system_context['platform']['system']}")
    print(f"- Docker available: {system_context['docker_available']}")
    print(f"- Package managers: {', '.join([k for k, v in system_context['package_managers'].items() if v])}")

if __name__ == "__main__":
    asyncio.run(check_system())

# Run with:
# python check_system.py
```

**Enable debug logging**

```bash
# Set environment variable before running
set LOG_LEVEL=DEBUG  # Windows
export LOG_LEVEL=DEBUG  # macOS/Linux

# Or in config file
configurable:
  log_level: "DEBUG"
```

**Check execution history**

```python
# Save as view_history.py
import sqlite3

conn = sqlite3.connect("workflow_history.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM execution_history ORDER BY timestamp DESC LIMIT 5")
for row in cursor.fetchall():
    print(f"ID: {row['id']}, Action: {row['action']}, Success: {row['success']}, Error: {row['error_message']}")

# Run with:
# python view_history.py
```

## Example Workflows

### Basic Installation Workflow

```bash
# Step 1: Create and activate virtual environment (if not already done)
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# Step 2: Install the package
pip install -e .

# Step 3: Create minimal configuration
cp custom_config_no_docker.yaml workflow_config.yaml

# Step 4: Run a test installation
workflow-agent install infra_agent --license-key=test_key --host=localhost
```

### Running the Example Script

```bash
# Run the test workflow script
cd examples
python test_workflow.py
```
