# Developer Setup & Troubleshooting

This guide provides instructions for setting up a development environment, common issues, and troubleshooting tips for the enhanced Workflow Agent framework with improved security, recovery, and reliability features.

## Navigation

-   [Overview](README.md)
-   [Architecture Overview](architecture-readme.md)
-   [LLM & Agent System](llm-agents-readme.md)
-   [Component Hierarchy](component-hierarchy-readme.md)
-   [Data Flow](data-flow-readme.md)
-   [Recent Fixes & Improvements](FIXED.md)

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

-   **Static Analysis Tools** (recommended for enhanced security features)
    -   shellcheck: For shell script validation
    -   pylint: For Python script validation

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

# For enhanced security features, install static analysis tools
# Windows (using choco)
choco install shellcheck

# macOS
brew install shellcheck

# Linux
apt-get install shellcheck
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

## Enhanced Project Structure for Development

```
workflow-agent/                   # Project root
│
├── src/                          # Source code
│   └── workflow_agent/           # Main package
│       ├── __init__.py           # Package initialization
│       ├── main.py               # Enhanced main entry point
│       ├── core/                 # Core components
│       │   ├── state.py          # Enhanced state management
│       │   ├── message_bus.py    # Message communication
│       │   └── container.py      # Dependency injection
│       ├── config/               # Enhanced configuration
│       ├── scripting/            # Enhanced script generation and validation
│       ├── execution/            # Enhanced script execution
│       ├── recovery/             # Enhanced recovery system
│       └── verification/         # Enhanced verification system
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

### Enhanced Security Features Issues

#### Static Analysis Tools Not Found

**Symptom:**

```
Warning: Enhanced security validation disabled - shellcheck not found
```

**Solution:**

```bash
# Install shellcheck for shell script validation
# Windows (using choco)
choco install shellcheck

# macOS
brew install shellcheck

# Linux
apt-get install shellcheck

# Configure the path in workflow_config.yaml
security:
  static_analysis:
    shellcheck_path: "/path/to/shellcheck"
```

#### Script Validation Failures

**Symptom:**

```
SecurityError: Script failed security validation: [Dangerous pattern detected: rm -rf /]
```

**Solution:**

-   Review the script for security issues
-   Modify the script to use safer alternatives
-   If you're sure the script is safe, you can disable least privilege execution in the config:

```yaml
# In workflow_config.yaml
configurable:
  least_privilege_execution: false  # USE WITH CAUTION
```

### Enhanced Recovery Features Issues

#### Rollback Failures

**Symptom:**

```
Error: Rollback failed: Unable to revert change [file_created]
```

**Solution:**

-   Check the rolled-back path for permissions issues
-   Review the recovery log for specific errors
-   Try using a different recovery strategy:

```yaml
# In workflow_config.yaml
recovery:
  strategy: "individual_actions"  # Options: full_rollback, staged_rollback, individual_actions
```

#### Change Tracking Issues

**Symptom:**

```
Warning: No changes detected during execution
```

**Solution:**

-   Ensure your scripts use the proper change tracking format
-   Add explicit change markers to your scripts:

```bash
# For shell scripts
echo "CHANGE_JSON_BEGIN {\"type\":\"file_created\",\"target\":\"/path/to/file\",\"revertible\":true} CHANGE_JSON_END"
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

## Enhanced Debugging Techniques

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

### 3. Check Recovery History

```python
# Save as view_recovery.py
import sqlite3

conn = sqlite3.connect("workflow_history.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM recovery_history ORDER BY timestamp DESC LIMIT 5")
for row in cursor.fetchall():
    print(f"ID: {row['id']}, Strategy: {row['strategy']}, Success: {row['success']}, Changes: {row['changes_count']}")

# Run with:
# python view_recovery.py
```

### 4. Run System Compatibility Check

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
    print(f"- Static analysis tools:")
    print(f"  - shellcheck: {system_context.get('static_analysis', {}).get('shellcheck_available', False)}")
    print(f"  - pylint: {system_context.get('static_analysis', {}).get('pylint_available', False)}")

if __name__ == "__main__":
    asyncio.run(check_system())
```

### 5. Test Security Validation

```python
# test_security.py
import asyncio
from workflow_agent.config.configuration import validate_script_security

async def test_security():
    test_script = """#!/bin/bash
set -e
echo "Installing test package"
apt-get update
apt-get install -y test-package
echo "CHANGE:PACKAGE_INSTALLED:test-package"
"""
    
    result = validate_script_security(test_script)
    print("Security Validation Results:")
    print(f"- Valid: {result['valid']}")
    if "warnings" in result:
        print("- Warnings:")
        for warning in result["warnings"]:
            print(f"  - {warning}")
    if "errors" in result:
        print("- Errors:")
        for error in result["errors"]:
            print(f"  - {error}")

if __name__ == "__main__":
    asyncio.run(test_security())
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

4.  **Use Enhanced Security Features**
    -   Implement proper script validation
    -   Use static analysis tools when available
    -   Follow the principle of least privilege

5.  **Implement Proper Change Tracking**
    -   Use structured formats for change tracking
    -   Include revert commands for all changes
    -   Verify changes can be successfully rolled back

6.  **Document Your Code**
    -   Add docstrings to classes and methods
    -   Document public interfaces thoroughly

7.  **Write Tests**
    -   Create unit tests for new components
    -   Add integration tests for workflows
    -   Include security and recovery tests

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

### Adding a New Recovery Strategy

1. Create a new strategy in `recovery/strategies/`:

```python
# src/workflow_agent/recovery/strategies/my_strategy.py
from ..base import RecoveryStrategyBase

class MyRecoveryStrategy(RecoveryStrategyBase):
    """Custom recovery strategy implementation."""
    
    name = "my_strategy"
    
    async def recover(self, state):
        """Implement custom recovery logic."""
        # Your recovery logic here
        return updated_state
```

2. Register the strategy in the `RecoveryManager`:

```python
# In src/workflow_agent/recovery/manager.py
from .strategies.my_strategy import MyRecoveryStrategy

# Register in the manager
self.strategies[MyRecoveryStrategy.name] = MyRecoveryStrategy()
```

For more details on the system architecture and component relationships, refer to the [Architecture Overview](architecture-readme.md) and [Recent Fixes & Improvements](FIXED.md).