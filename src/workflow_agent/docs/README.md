# Workflow Agent Framework

A Python framework for orchestrating multi-step workflows with error recovery and rollback capabilities, particularly in infrastructure as code scenarios.

## Features

- **Workflow Orchestration**: Define and execute multi-step workflows with dependencies
- **Error Recovery**: Automatic retry and recovery mechanisms with exponential backoff
- **Transaction Management**: ACID-compliant transaction handling with rollback support
- **Security**: Secure secrets management and parameter sanitization
- **Configuration Management**: Flexible configuration system with environment variable support
- **Logging**: Structured logging with JSON support and log rotation
- **Testing**: Comprehensive testing framework with mocking support
- **Dependency Injection**: Clean dependency management with a DI container

## Installation

```bash
pip install workflow-agent
```

## Quick Start

```python
from workflow_agent import WorkflowAgent, WorkflowConfig
from workflow_agent.error.recovery import with_recovery
from workflow_agent.di.container import inject

# Define a workflow
@inject(WorkflowConfig)
class MyWorkflow(WorkflowAgent):
    def __init__(self, workflow_config):
        super().__init__(workflow_config)
        
    @with_recovery("database_operation")
    async def execute(self):
        # Define workflow steps
        await self.add_step("step1", self.step1)
        await self.add_step("step2", self.step2)
        
        # Execute workflow
        return await self.run()
        
    async def step1(self):
        # Step 1 implementation
        pass
        
    async def step2(self):
        # Step 2 implementation
        pass

# Create and run workflow
workflow = MyWorkflow()
result = await workflow.execute()
```

## Configuration

Configuration can be provided through YAML files or environment variables:

```yaml
# config.yaml
name: my-workflow
version: 1.0.0
parameters:
  database_url:
    type: string
    required: true
    description: Database connection URL
targets:
  postgresql:
    type: database
    parameters:
      host: localhost
      port: 5432
timeout: 300
max_retries: 3
retry_delay: 5
log_level: INFO
log_file: workflow.log
history_enabled: true
history_retention_days: 30
```

Environment variables can override configuration values:

```bash
export WORKFLOW_TIMEOUT=600
export WORKFLOW_MAX_RETRIES=5
```

## Error Recovery

The framework provides automatic error recovery with exponential backoff:

```python
from workflow_agent.error.recovery import with_recovery

@with_recovery("database_operation", max_retries=3, retry_delay=1.0)
async def database_operation():
    # Operation implementation
    pass
```

## Transaction Management

Transactions are managed automatically with rollback support:

```python
from workflow_agent.storage.transaction import TransactionContext

async with TransactionContext(session) as transaction:
    # Add operations to transaction
    transaction.add_operation(create_table, drop_table)
    
    # Commit transaction
    transaction.commit()
```

## Security

Secrets are managed securely with encryption:

```python
from workflow_agent.security.secrets import SecretsManager

secrets_manager = SecretsManager()
encrypted_value = secrets_manager.encrypt("sensitive_data")
decrypted_value = secrets_manager.decrypt(encrypted_value)
```

## Logging

Structured logging with JSON support:

```python
from workflow_agent.logging.config import LogConfig

log_config = LogConfig(
    log_level="INFO",
    log_file="workflow.log",
    json_logging=True
)
log_config.configure()
```

## Testing

The framework includes a comprehensive testing framework:

```python
from workflow_agent.testing.framework import test_case, TestCase

@test_case
class MyWorkflowTest(TestCase):
    def setUp(self):
        super().setUp()
        # Test setup
        
    def test_workflow_execution(self):
        # Test implementation
        pass
```

## Dependency Injection

Dependencies are managed through a DI container:

```python
from workflow_agent.di.container import inject

@inject(ConfigManager)
class MyService:
    def __init__(self, config_manager):
        self.config_manager = config_manager
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- SQLAlchemy for database operations
- Cryptography for security features
- PyYAML for configuration management 