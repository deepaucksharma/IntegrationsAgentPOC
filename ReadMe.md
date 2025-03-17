# Workflow Agent: Comprehensive Documentation

## Table of Contents

1. [Introduction](#introduction)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Usage](#usage)
   - [Command Line Interface](#command-line-interface)
   - [API Reference](#api-reference)
   - [Creating Templates](#creating-templates)
   - [Custom Integrations](#custom-integrations)
7. [Data Storage](#data-storage)
8. [Isolation Methods](#isolation-methods)
9. [Script Optimization](#script-optimization)
10. [Verification Strategies](#verification-strategies)
11. [Error Handling and Rollback](#error-handling-and-rollback)
12. [Security Considerations](#security-considerations)
13. [Performance Optimization](#performance-optimization)
14. [Troubleshooting](#troubleshooting)
15. [Development](#development)
16. [Contributing](#contributing)
17. [License](#license)

## Introduction

Workflow Agent is a Python framework for orchestrating complex multi-step workflows with AI-driven adaptation. It's designed to generate, validate, execute, and verify scripts for various types of system integrations while providing automatic error recovery and rollback capabilities.

The framework is particularly useful for DevOps, system administration, and infrastructure as code scenarios where reliable, repeatable operations are essential, and where the ability to adapt to different environments and recover from failures is crucial.

## Features

- **Templated Script Generation**: Uses Jinja2 templates to generate system integration scripts
- **Multiple Script Optimization Methods**:
  - LLM-based optimization with OpenAI GPT models
  - Rule-based optimization with predefined patterns
  - Static analysis with ShellCheck
- **Comprehensive Validation**: Security and functionality checks for scripts
- **Execution Isolation**:
  - Docker containerization
  - Chroot environments
  - Python virtual environments
  - Sandbox isolation with nsjail
- **Verification Strategies**: Confirmation of successful integrations
- **Automatic Rollback**: Recovery from failed operations
- **Execution History**: Detailed record-keeping of all operations
- **Pluggable Architecture**: Easy extension with custom integrations
- **Multi-Database Support**: SQLite, PostgreSQL, and MySQL backends
- **Asynchronous Workflows**: Concurrent execution for improved performance
- **User-Friendly CLI**: Rich command-line interface with intuitive commands

## Architecture

The Workflow Agent is built on a modular architecture with clearly defined components:

### Core Components

1. **WorkflowAgent**: The main agent class that coordinates all operations
2. **WorkflowGraph**: Directed graph that defines the execution flow of workflow nodes
3. **WorkflowState**: Pydantic model that holds all state information during workflow execution

### Key Modules

- **scripting**: Script generation and optimization
- **execution**: Script execution with various isolation methods
- **verification**: Result verification strategies
- **rollback**: Error recovery and change rollback
- **storage**: History tracking and persistence
- **integrations**: Pluggable integration handlers
- **config**: Configuration management
- **utils**: Utility functions for system operations and logging

### Workflow Steps

1. **Parameter Validation**: Ensure all required parameters are present and valid
2. **Script Generation**: Create scripts from templates or AI generation
3. **Script Validation**: Check for security issues and best practices
4. **Script Execution**: Run scripts with appropriate isolation
5. **Result Verification**: Confirm successful integration
6. **Rollback (if needed)**: Revert changes on failure

## Installation

### Prerequisites

- **Operating System**: Linux, macOS, or Windows (Linux/macOS recommended)
- **Python**: 3.8 or higher
- **Optional Dependencies**:
  - Docker (for container isolation)
  - ShellCheck (for script validation)
  - nsjail (for sandbox isolation)

### Standard Installation

```bash
pip install workflow-agent
```

### Development Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/workflow-agent.git
cd workflow-agent

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with all extras
pip install -e ".[llm,dev,doc]"
```

### Installation Verification

```bash
# Verify installation and see available commands
workflow-agent --help
```

## Configuration

Workflow Agent can be configured through:
1. Configuration files (YAML/JSON)
2. Environment variables
3. Command-line arguments

### Configuration File

Create a configuration file at one of these locations:
- `./workflow_config.yaml`
- `./workflow_config.yml`
- `./workflow_config.json`
- `~/.workflow_agent/config.yaml`

Example configuration:

```yaml
configurable:
  user_id: "user1"
  template_dir: "./templates"
  custom_template_dir: "./custom_templates"
  use_isolation: true
  isolation_method: "docker"
  execution_timeout: 30000
  skip_verification: false
  use_llm_optimization: false
  rule_based_optimization: true
  use_static_analysis: true
  db_connection_string: null
  prune_history_days: 90
  plugin_dirs:
    - "./plugins"
  async_execution: false
  max_concurrent_tasks: 5
  least_privilege_execution: true
  sandbox_isolation: false
  log_level: "INFO"
```

### Environment Variables

All configuration options can be set using environment variables with the `WORKFLOW_` prefix:

```bash
export WORKFLOW_USER_ID="user1"
export WORKFLOW_TEMPLATE_DIR="./templates"
export WORKFLOW_USE_ISOLATION=true
export WORKFLOW_ISOLATION_METHOD="docker"
export WORKFLOW_OPENAI_API_KEY="your-openai-api-key"  # For LLM optimization
```

### Interactive Configuration

```bash
workflow-agent configure
```

This will guide you through the configuration options interactively and save them to a configuration file.

## Usage

### Command Line Interface

#### Initializing a Project

```bash
# Initialize a new project with directory structure and sample files
workflow-agent init ./my-workflow-project

# Initialize with sample configurations
workflow-agent init ./my-workflow-project --samples
```

#### Running Workflows

Basic usage:

```bash
# Install a PostgreSQL monitoring agent
workflow-agent run --action install --target postgres --param db_host=localhost --param db_port=5432
```

With isolation:

```bash
# Run in a Docker container
workflow-agent run --action install --target mysql --use-isolation --isolation-method docker
```

With optimization:

```bash
# Use rule-based optimization
workflow-agent run --action install --target nginx --optimize

# Use LLM optimization (requires OpenAI API key)
workflow-agent run --action install --target nginx --llm-optimize
```

Dry run (generate script without executing):

```bash
workflow-agent run --action install --target redis --dry-run
```

Save generated script to file:

```bash
workflow-agent run --action install --target nginx --dry-run --output ./scripts/install-nginx.sh
```

Load parameters from file:

```bash
# Create a parameters file (JSON)
echo '{"db_host": "localhost", "db_port": 5432, "user": "postgres"}' > params.json

# Run with parameters from file
workflow-agent run --action install --target postgres --file params.json
```

Integration with cloud services:

```bash
# AWS integration
workflow-agent run --target aws --integration-type aws --param aws_access_key=KEY --param aws_secret_key=SECRET
```

#### Viewing and Managing History

View execution history:

```bash
workflow-agent history --target postgres --action install
```

Detailed history:

```bash
workflow-agent history --target mysql --action install --verbose
```

Export history:

```bash
workflow-agent history --target nginx --action install --export history.json
```

Clear history:

```bash
# Clear specific history
workflow-agent clear-history --target postgres --action install

# Clear old history
workflow-agent clear-history --days 30

# Clear all history
workflow-agent clear-history --all
```

#### Creating Templates

```bash
workflow-agent template --action install --target custom-app --output ./templates/custom-app-install.sh.j2
```

#### Listing Available Options

```bash
# List available targets and actions
workflow-agent list

# List integration types with details
workflow-agent integrations --verbose

# Show version information
workflow-agent version
```

### API Reference

#### Basic Script Execution

```python
import asyncio
from workflow_agent import WorkflowAgent

async def run_workflow():
    # Create agent
    agent = WorkflowAgent()
    
    # Initialize
    await agent.initialize()
    
    # Define input state
    input_state = {
        "action": "install",
        "target_name": "postgres",
        "integration_type": "infra_agent",
        "parameters": {
            "db_host": "localhost",
            "db_port": 5432
        }
    }
    
    # Define configuration
    config = {
        "configurable": {
            "use_isolation": True,
            "isolation_method": "docker"
        }
    }
    
    # Execute workflow
    result = await agent.invoke(input_state, config)
    
    # Print result
    print(f"Execution completed: {'Success' if 'error' not in result else 'Failed'}")
    if "error" in result:
        print(f"Error: {result['error']}")
    
    # Cleanup
    await agent.cleanup()

# Run workflow
asyncio.run(run_workflow())
```

#### Custom Integration Implementation

```python
from workflow_agent import IntegrationBase, WorkflowState
from workflow_agent.integrations import IntegrationRegistry

class CustomIntegration(IntegrationBase):
    @classmethod
    def get_name(cls) -> str:
        return "custom"
    
    @classmethod
    def get_supported_targets(cls) -> list:
        return ["my-target"]
    
    async def handle(self, state: WorkflowState, config: dict = None) -> dict:
        # Custom integration logic
        script = f"""#!/usr/bin/env bash
set -e
echo "Custom integration for {state.target_name}"
"""
        return {
            "script": script,
            "source": "custom_integration"
        }

# Register the integration
IntegrationRegistry.register(CustomIntegration)
```

### Creating Templates

Templates use Jinja2 syntax and are stored in the `templates` directory with the naming pattern `{target}-{action}.sh.j2`.

Example template for nginx installation:

```jinja
#!/usr/bin/env bash
# Template for installing Nginx
set -e

# Error handling
error_exit() {
    echo "ERROR: $1" >&2
    exit 1
}

# Logging function
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_message "Starting installation for nginx"

# Check for required tools
command -v curl >/dev/null 2>&1 || error_exit "curl is required but not installed"

# Example of parameter usage
{% if parameters.port is defined %}
NGINX_PORT="{{ parameters.port }}"
log_message "Using custom port: $NGINX_PORT"
{% else %}
NGINX_PORT="80"
log_message "Using default port: $NGINX_PORT"
{% endif %}

# Installation
log_message "Installing nginx"
if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y nginx
elif command -v yum >/dev/null 2>&1; then
    yum install -y nginx
else
    error_exit "Unsupported package manager"
fi

# Configuration
log_message "Configuring nginx"
cat > /etc/nginx/conf.d/default.conf <<EOF
server {
    listen       $NGINX_PORT;
    server_name  localhost;

    location / {
        root   /usr/share/nginx/html;
        index  index.html;
    }
}
EOF

# Start service
log_message "Starting nginx service"
systemctl enable nginx
systemctl start nginx

log_message "Nginx installation completed successfully"
```

### Parameter Schemas

Define parameter requirements in YAML files in the `templates/schemas` directory:

```yaml
# templates/schemas/nginx.yaml
port:
  type: number
  description: HTTP port to listen on
  required: false
  default: 80

ssl_enabled:
  type: boolean
  description: Enable SSL/TLS
  required: false
  default: false

domain:
  type: string
  description: Domain name for the server
  required: true
```

### Verification Commands

Define verification commands in YAML files in the `templates/verifications` directory:

```yaml
# templates/verifications/nginx.yaml
nginx-verify: systemctl is-active nginx && curl -s http://localhost:80/
```

### Custom Integrations

Create plugins in the `plugins` directory:

```python
# plugins/my_integration.py
from workflow_agent import IntegrationBase, WorkflowState

class MyCustomIntegration(IntegrationBase):
    @classmethod
    def get_name(cls) -> str:
        return "mycustom"
    
    @classmethod
    def get_supported_targets(cls) -> list:
        return ["target1", "target2"]
    
    async def handle(self, state: WorkflowState, config: dict = None) -> dict:
        # Custom integration logic
        script = f"""#!/usr/bin/env bash
set -e
echo "Custom integration for {state.target_name}"
# Your custom logic here
"""
        return {
            "script": script,
            "source": "my_custom_integration"
        }
```

## Data Storage

Workflow Agent supports multiple database backends for history storage:

### SQLite (Default)

```bash
# Set SQLite as the database backend
export WORKFLOW_HISTORY_DB="workflow_history.db"
export WORKFLOW_HISTORY_DB_TYPE="sqlite"
```

### PostgreSQL

```bash
# Set PostgreSQL as the database backend
export WORKFLOW_HISTORY_DB_TYPE="postgresql"
export WORKFLOW_HISTORY_DB_HOST="localhost"
export WORKFLOW_HISTORY_DB_PORT="5432"
export WORKFLOW_HISTORY_DB_USER="postgres"
export WORKFLOW_HISTORY_DB_PASS="password"
export WORKFLOW_HISTORY_DB_NAME="workflow_history"

# Or use a connection string in configuration
# db_connection_string: "postgresql://postgres:password@localhost:5432/workflow_history"
```

### MySQL

```bash
# Set MySQL as the database backend
export WORKFLOW_HISTORY_DB_TYPE="mysql"
export WORKFLOW_HISTORY_DB_HOST="localhost"
export WORKFLOW_HISTORY_DB_PORT="3306"
export WORKFLOW_HISTORY_DB_USER="root"
export WORKFLOW_HISTORY_DB_PASS="password"
export WORKFLOW_HISTORY_DB_NAME="workflow_history"

# Or use a connection string in configuration
# db_connection_string: "mysql+pymysql://root:password@localhost:3306/workflow_history"
```

## Isolation Methods

Workflow Agent supports multiple isolation methods for script execution:

### Direct Execution

Executes scripts directly on the host system. Fastest but least isolated.

```bash
workflow-agent run --target nginx --isolation-method direct
```

### Docker Isolation

Executes scripts in a Docker container. Requires Docker to be installed.

```bash
workflow-agent run --target nginx --use-isolation --isolation-method docker
```

### Chroot Isolation

Executes scripts in a chroot environment. Requires root privileges.

```bash
sudo workflow-agent run --target nginx --use-isolation --isolation-method chroot
```

### Python Virtual Environment

Executes scripts in a Python virtual environment. Useful for Python-based integrations.

```bash
workflow-agent run --target django-app --use-isolation --isolation-method venv
```

### Sandbox Isolation

Executes scripts in a restricted sandbox using nsjail. Requires nsjail to be installed.

```bash
workflow-agent run --target nginx --use-isolation --isolation-method sandbox
```

## Script Optimization

Workflow Agent supports multiple script optimization methods:

### Rule-Based Optimization

Applies predefined rules to improve scripts.

```bash
workflow-agent run --target nginx --optimize
```

### LLM Optimization (OpenAI)

Uses OpenAI's GPT models to optimize scripts. Requires an OpenAI API key.

```bash
export OPENAI_API_KEY="your-api-key"
workflow-agent run --target nginx --llm-optimize
```

### ShellCheck Static Analysis

Uses ShellCheck to validate and improve shell scripts. Requires shellcheck-py.

```bash
workflow-agent run --target nginx --shell-check
```

## Verification Strategies

Workflow Agent uses multiple strategies to verify successful integration:

1. **Custom Verification Commands**: User-defined commands to verify integration
2. **Predefined Verification Commands**: Built-in commands for common targets
3. **Service Checks**: Verifies service status for infrastructure agents
4. **Health Checks**: HTTP/TCP probes for web services

## Error Handling and Rollback

### Error Types

- **Validation Errors**: Parameter or script validation failures
- **Execution Errors**: Script execution failures
- **Verification Failures**: Failed integration verification

### Rollback Strategy

When an error occurs, Workflow Agent performs the following steps:

1. Captures error details and context
2. Identifies the changes made before the error
3. Generates a targeted rollback script based on changes
4. Executes the rollback script with appropriate isolation
5. Records the rollback execution in history

### Configuring Rollback

Custom rollback templates can be defined using the naming pattern `{target}-rollback.sh.j2` or `{target}-remove.sh.j2`.

## Security Considerations

### Script Validation

Workflow Agent checks scripts for potentially dangerous commands using regular expressions defined in `dangerous_patterns`. You can add additional patterns in a `dangerous_patterns.txt` file in your template directory.

### Least Privilege Execution

When `least_privilege_execution` is enabled, scripts run with minimal permissions:

- Docker containers run with dropped capabilities
- Limited resource access
- Network isolation
- Read-only file systems where possible

### Sensitive Parameter Handling

Parameters containing sensitive data (passwords, keys, tokens) are handled with care:
- Not logged in plaintext
- Warnings displayed when detected
- Masked in output displays

## Performance Optimization

### Asynchronous Execution

Enable asynchronous workflow execution for better performance:

```yaml
# In configuration
configurable:
  async_execution: true
  max_concurrent_tasks: 5
```

### Database Connection Pooling

For PostgreSQL and MySQL backends, connection pooling is used to improve performance:

```yaml
# In configuration
configurable:
  db_connection_string: "postgresql://user:pass@host/db?pool_size=10&max_overflow=20"
```

### History Pruning

Automatically prune old history records:

```yaml
# In configuration
configurable:
  prune_history_days: 90
```

## Troubleshooting

### Common Issues and Solutions

#### Script Execution Failures

**Issue**: Scripts fail to execute with permission errors.

**Solution**: Check the script file permissions:
```bash
chmod +x script.sh
```

#### Docker Isolation Errors

**Issue**: Docker isolation fails with "Docker not available".

**Solution**: Ensure Docker is installed and running:
```bash
docker --version
systemctl status docker
```

#### Database Connection Issues

**Issue**: Database connection errors.

**Solution**: Verify connection details and database server status:
```bash
# For PostgreSQL
pg_isready -h hostname -p port

# For MySQL
mysqladmin ping -h hostname -P port
```

#### Missing Templates

**Issue**: "No template found for target-action".

**Solution**: Create the required template or use a different target/action:
```bash
workflow-agent template --action install --target your-target
```

### Debug Mode

Enable debug logging for more detailed information:

```bash
export LOG_LEVEL=DEBUG
workflow-agent run --target nginx
```

### Examining Logs

Logs are written to the standard output and can be redirected to a file:

```bash
workflow-agent run --target nginx > workflow.log 2>&1
```

### Inspecting History

Use the history command to examine past executions:

```bash
workflow-agent history --target nginx --action install --verbose
```

### Recovery Mode

If a workflow fails and automatic rollback also fails, you can:

1. Get the transaction ID from the error output
2. View the transaction history:
   ```bash
   workflow-agent history --transaction-id YOUR_TRANSACTION_ID --verbose
   ```
3. Generate a manual rollback script:
   ```bash
   workflow-agent run --action rollback --target nginx --param transaction_id=YOUR_TRANSACTION_ID
   ```

## Development

### Directory Structure

```
workflow-agent/
├── src/
│   └── workflow_agent/
│       ├── __init__.py
│       ├── agent.py
│       ├── core/
│       ├── config/
│       ├── execution/
│       ├── scripting/
│       ├── storage/
│       ├── verification/
│       ├── rollback/
│       ├── integrations/
│       ├── workflow/
│       ├── utils/
│       └── cli/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── examples/
├── templates/
├── plugins/
├── docs/
├── setup.py
└── README.md
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test suites
pytest tests/unit
pytest tests/integration
pytest tests/e2e

# Run with coverage
pytest --cov=workflow_agent tests/
```

### Building Documentation

```bash
cd docs
make html
```

### Code Style and Quality

```bash
# Format code
black src tests

# Sort imports
isort src tests

# Lint code
pylint src

# Type checking
mypy src
```

## Dependencies

### Core Dependencies

- **jinja2**: Template rendering
- **pydantic**: Data validation
- **SQLAlchemy**: Database ORM
- **asyncio/aiosqlite/aiohttp**: Async I/O operations
- **typer/rich/InquirerPy**: CLI interface
- **PyYAML**: Configuration parsing
- **psutil**: System metrics

### Optional Dependencies

- **shellcheck-py**: Script validation
- **langchain-openai**: LLM optimization
- **asyncpg**: PostgreSQL async support
- **aiomysql**: MySQL async support

## Version Compatibility

- **Python**: 3.8 or higher
- **Operating Systems**: Linux (recommended), macOS, Windows (limited support)
- **Databases**: SQLite 3.x, PostgreSQL 10+, MySQL 5.7+

## Upgrading

When upgrading to a new version:

1. Back up your configuration and templates
2. Update the package: `pip install -U workflow-agent`
3. Run the migration tool if available: `workflow-agent migrate`
4. Test with a dry run: `workflow-agent run --target test --dry-run`

## Contributing

We welcome contributions to the Workflow Agent project:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

Please follow our coding standards and include tests for new features.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

For more information, visit our website or contact support.