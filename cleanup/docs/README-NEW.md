# Workflow Agent for Integrations

A robust platform for managing infrastructure and software integrations with enhanced security, resilient execution, and comprehensive recovery capabilities.

## Overview

The Workflow Agent provides a framework for automating the installation, verification, and removal of various infrastructure components and software integrations. It features:

- **Enhanced Security**: Comprehensive security validation with static analysis
- **Script Generation**: Template and LLM-based script generation
- **Robust Execution**: Reliable script execution with validation and isolation
- **Comprehensive Recovery**: Multiple recovery strategies for handling failures
- **Cross-Platform Support**: Works on Windows, Linux, and macOS

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Operating System: Windows 10+, Ubuntu 18.04+, or macOS 10.15+

### Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd IntegrationsAgentPOC
   ```

2. Install the package with all dependencies:
   ```
   pip install -e .
   ```

   For development or LLM features, include extras:
   ```
   pip install -e ".[dev,llm]"
   ```

### Configuration

Create a `workflow_config.yaml` file in your working directory or specify a path with the `--config-file` option:

```yaml
# Basic settings
version: "1.0.0"
log_level: "INFO"
log_file: "workflow_agent.log"

# Path settings
template_dir: "./templates"
script_dir: "./generated_scripts"
backup_dir: "./backup"

# Security settings
security:
  least_privilege_execution: true
  script_execution_timeout: 600
  allow_sudo: false
  
# Execution settings
isolation_method: "direct"  # Options: direct, docker
execution_timeout: 300
max_retries: 3

# Features
use_recovery: true
skip_verification: false
```

Environment variables with the prefix `WORKFLOW_` can override configuration settings (e.g., `WORKFLOW_LOG_LEVEL=DEBUG`).

## Usage

### Basic Commands

Install an integration:
```
python -m workflow_agent install <integration-type> --license-key <key> --host <target-host>
```

Verify an integration:
```
python -m workflow_agent verify <integration-type> --host <target-host>
```

Remove an integration:
```
python -m workflow_agent remove <integration-type> --host <target-host>
```

### Custom Configuration

Specify a custom configuration file:
```
python -m workflow_agent install <integration-type> --config-file my_config.yaml
```

## Creating Integrations

Custom integrations can be created by extending the `IntegrationBase` class:

```python
from workflow_agent.integrations.base import IntegrationBase

class MyCustomIntegration(IntegrationBase):
    """My custom integration implementation."""
    
    name = "my_integration"
    version = "1.0.0"
    description = "Description of my integration"
    required_parameters = ["license_key", "host"]
    
    async def install(self, parameters):
        """Install the integration."""
        # Implementation
        return {
            "template_data": {
                "key": "value"
            }
        }
    
    async def verify(self, parameters):
        """Verify the integration."""
        # Implementation
        return {
            "status": "success"
        }
    
    async def uninstall(self, parameters):
        """Uninstall the integration."""
        # Implementation
        return {
            "status": "success"
        }
```

Place your integration module in the `plugins` directory or set the `WORKFLOW_PLUGIN_PATH` environment variable.

## Templates

Templates use Jinja2 and should be organized in the following structure:

```
templates/
├── install/
│   ├── default.sh.j2
│   └── my_integration/
│       └── target_name.sh.j2
├── verify/
│   └── default.sh.j2
└── uninstall/
    └── default.sh.j2
```

Template resolution follows a clear precedence:
1. `action/integration_type/target_name`
2. `action/integration_type`
3. `action/integration_type/default`
4. `action/default`

## Recovery System

The workflow agent includes a sophisticated recovery system that can revert changes in case of failures. The recovery system:

1. Tracks all changes made during execution
2. Creates a detailed rollback plan
3. Implements multiple recovery strategies:
   - Full rollback: Single comprehensive rollback script
   - Staged rollback: Group changes by type for more controlled rollback
   - Individual rollback: Roll back changes one by one for maximum precision
4. Verifies system state after recovery

## Advanced Features

### Docker Isolation

For enhanced security, scripts can be executed in a Docker container:

```yaml
isolation_method: "docker"
security:
  docker_image: "ubuntu:latest"
```

### LLM-Assisted Script Generation

Enable LLM assistance for script generation:

```yaml
script_generator: "llm"
use_llm: true
```

## Architecture

The system consists of the following key components:

- **WorkflowAgent**: Main orchestrator
- **ScriptGenerator**: Generates scripts using templates or LLMs
- **ScriptExecutor**: Executes scripts with isolation and change tracking
- **VerificationManager**: Verifies successful operation
- **RecoveryManager**: Handles recovery from failures
- **IntegrationManager**: Manages integration plugins

## Troubleshooting

### Common Issues

1. **Script execution fails**: Check script permissions and dependencies
2. **Verification fails**: Examine logs for specific verification failures
3. **Recovery issues**: Check backup directory permissions

### Logs

Logs are stored in the specified log file or `workflow_agent.log` by default. Set `log_level: "DEBUG"` for more detailed logs.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## Security

Security vulnerabilities should be reported to security@example.com.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
