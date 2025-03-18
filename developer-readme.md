# Developer Setup & Troubleshooting

This guide provides instructions for setting up a development environment, common issues, and troubleshooting tips for the Workflow Agent framework.

## Navigation

-   [Overview](overview-readme.md)
-   [Architecture Overview](architecture-readme.md)
-   [LLM & Agent System](llm-agents-readme.md)
-   [Component Hierarchy](component-hierarchy-readme.md)
-   [Data Flow](data-flow-readme.md)

## Development Environment Setup

### Prerequisites

Before setting up the development environment, ensure you have:

-   **Python 3.8 or higher**
    -   Windows: \[Download from python.org](https://www.python.org/downloads/windows/) and check "Add Python to PATH" during installation
    -   macOS: `brew install python@3.10` or download from python.org
    -   Linux: `sudo apt-get install python3 python3-pip python3-venv` (Ubuntu/Debian)

-   **pip and venv** (usually included with Python installation)

-   **Docker** (optional, for isolated execution testing)
    -   Follow \[Docker installation instructions](https://docs.docker.com/get-docker/) for your OS

-   **Git** for version control

### Setup Steps

```
+-------------------------------+
| 1. Clone Repository           |
+-------------------------------+
              |
              v
+-------------------------------+
| 2. Create Virtual Environment |
+-------------------------------+
              |
              v
+-------------------------------+
| 3. Install Dependencies       |
+-------------------------------+
              |
              v
+-------------------------------+
| 4. Configure Environment      |
+-------------------------------+
              |
              v
+-------------------------------+
| 5. Run Tests                  |
+-------------------------------+
```

#### 1. Clone the Repository

```bash
# Clone the repository
git clone https://github.com/yourusername/workflow-agent.git
cd workflow-agent
```

#### 2. Create a Virtual Environment

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies

```bash
# Install in development mode with all extras
pip install -e ".[dev,doc,llm]"
```

#### 4. Configure Development Environment

Create a development configuration file:

```bash
# Copy the development configuration template
cp custom_config_no_docker.yaml workflow_config.yaml

# Modify as needed for your environment
```

#### 5. Run Tests

```bash
# Run the development bootstrap script
# Windows
.\dev_bootstrap.ps1

# Linux/macOS
bash dev_bootstrap.sh
```

## Project Structure for Development

```
workflow-agent/                   # Project root
│
├── src/                          # Source code
│   └── workflow_agent/           # Main package
│       ├── __init__.py           # Package initialization
│       ├── main.py               # Entry point
│       └── ... (component dirs)  # Module subdirectories
│
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests
│   └── integration/              # Integration tests
│
├── examples/                     # Example scripts
│   └── test_workflow.py          # Test workflow script
│
├── docs/                         # Documentation
│
├── setup.py                      # Package setup
├── requirements.txt              # Dependencies
├── dev_bootstrap.ps1             # Development setup (Windows)
├── dev_bootstrap.sh              # Development setup (Unix)
└── workflow_config.yaml          # Configuration file
```

## Common Issues and Troubleshooting

### Initial Setup Issues

#### Python Not Found or Incorrect Version

**Symptom:**

```
Python was not found; run without arguments to install from the Microsoft Store
```

**Solution:**

-   Install Python from python.org
-   Check "Add Python to PATH" during installation
-   Restart your terminal
-   Verify with `python --version` or `python3 --version`

#### Virtual Environment Activation Issues

**Symptom:**

```
Cannot activate venv: execution of scripts is disabled on this system
```

**Solution:**

```powershell
# Windows: Run in PowerShell as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Package Not Found

**Symptom:**

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

### Running Issues

#### Template Directory Not Found

**Symptom:**

```
Error: No such file or directory: './integrations/common_templates'
```

**Solution:**

```bash
# Create required directories
mkdir -p integrations/common_templates/install
mkdir -p integrations/common_templates/remove
mkdir -p integrations/common_templates/verify
mkdir -p integrations/common_templates/macros

# Set the template directory in your config
# In workflow_config.yaml:
configurable:
  template_dir: "./integrations/common_templates"
```

#### Docker Isolation Failures

**Symptom:**

```
Error: Docker not available, falling back to direct execution
```

**Solution:**

-   Ensure Docker is installed and running
-   Use the no-Docker configuration if Docker is not available:

```bash
cp custom_config_no_docker.yaml workflow_config.yaml
```

#### Permission Issues

**Symptom:**

```
Permission denied: '/etc/monitoring'
```

**Solution:**

-   Run with administrative privileges
    -   Windows: Run PowerShell as Administrator
    -   Linux/macOS: Use `sudo`
-   Or modify the configuration to use user-accessible paths:

```yaml
# In workflow_config.yaml
configurable:
  least_privilege_execution: true
```

## Debugging Techniques

### 1. Enable Debug Logging

```bash
# Set environment variable before running
set LOG_LEVEL=DEBUG  # Windows
export LOG_LEVEL=DEBUG  # macOS/Linux

# Or in config file
configurable:
  log_level: "DEBUG"
```

### 2. Check Execution History

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

### 3. Run System Compatibility Check

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
```

### 4. Testing Individual Components

You can test individual components by creating targeted scripts:

#### Test Script Generator

```python
# test_generator.py
import asyncio
from workflow_agent.scripting.generator import ScriptGenerator
from workflow_agent.core.state import WorkflowState

async def test_generator():
    generator = ScriptGenerator()
    state = WorkflowState(
        action="install",
        target_name="monitoring_agent",
        integration_type="infra_agent",
        template_path="./integrations/common_templates/install/monitoring_agent.sh.j2",
        parameters={"license_key": "test123", "host": "localhost"}
    )
    result = await generator.generate_script(state)
    print(result.get("script", result.get("error")))

if __name__ == "__main__":
    asyncio.run(test_generator())
```

#### Test Documentation Parser

```python
# test_parser.py
import asyncio
from workflow_agent.documentation.parser import DocumentationParser

async def test_parser():
    parser = DocumentationParser()
    docs = await parser.fetch_integration_docs("infra_agent")
    print(docs)

if __name__ == "__main__":
    asyncio.run(test_parser())
```

## Development Workflow

For contributing to the project, follow this workflow:

1.  **Create a Feature Branch**

```bash
git checkout -b feature/my-new-feature
```

2.  **Make Changes and Test**

```bash
# After making changes, run tests
pytest tests/

# Test the example workflow
python examples/test_workflow.py
```

3.  **Commit Changes**

```bash
git add .
git commit -m "Add new feature: description"
```

4.  **Submit Pull Request**

    -   Push changes to your fork
    -   Create a pull request with a clear description

## Best Practices

1.  **Follow the Project Structure**
    -   Place new components in appropriate directories
    -   Maintain separation of concerns

2.  **Use Asynchronous Programming**
    -   Use `async`/`await` for I/O-bound operations
    -   Avoid blocking calls in async functions

3.  **Maintain Immutability**
    -   Use the evolve pattern for state changes
    -   Avoid directly modifying state objects

4.  **Document Your Code**
    -   Add docstrings to classes and methods
    -   Document public interfaces thoroughly

5.  **Write Tests**
    -   Create unit tests for new components
    -   Add integration tests for workflows

## Extending the Framework

### Adding a New Integration

1.  Create a new directory in `integrations/`:

```
src/workflow_agent/integrations/new_integration_type/
```

2.  Add YAML definition files:

```
new_integration_type/target_name/definition.yaml
new_integration_type/target_name/parameters.yaml
new_integration_type/target_name/verification.yaml
```

3.  Create templates in common\_templates or a custom directory

4.  Register the integration in `__init__.py` or let auto-discovery find it

### Adding a New Agent

1.  Create a new agent class in `multi_agent/`:

```python
# src/workflow_agent/multi_agent/new_agent.py
class NewAgent:
    def __init__(self, message_bus):
        self.message_bus = message_bus

    async def initialize(self):
        # Subscribe to relevant topics
        await self.message_bus.subscribe("topic", self._handle_topic)

    async def _handle_topic(self, message):
        # Handle messages
```

2.  Register the agent in the `CoordinatorAgent`

For more details on the system architecture and component relationships, refer to the [Architecture Overview](architecture-readme.md).