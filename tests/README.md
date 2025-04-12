# Test Suite

This directory contains automated tests for the IntegrationsAgentPOC project.

## Test Structure

The tests are organized in parallel with the main project structure:

```
tests/
├── unit/                  # Unit tests for individual components
│   ├── agent/             # Tests for agent implementations
│   ├── core/              # Tests for core framework components
│   ├── execution/         # Tests for script execution
│   └── ...
├── integration/           # Integration tests across components
│   ├── agent_coordination/
│   ├── end_to_end/
│   └── ...
├── fixtures/              # Test fixtures and sample data
└── conftest.py            # Pytest configuration and fixtures
```

## Running Tests

To run all tests:

```bash
pytest
```

To run specific test categories:

```bash
pytest tests/unit/          # Run all unit tests
pytest tests/integration/   # Run all integration tests
```

To generate a coverage report:

```bash
pytest --cov=workflow_agent tests/
```

## Writing Tests

### Test Guidelines

1. **One assertion per test**: Keep tests focused on a single behavior
2. **Descriptive test names**: Use `test_<function_name>_<expected_behavior>` format
3. **Arrange-Act-Assert**: Structure tests with clear setup, action, and verification
4. **Use fixtures**: Create reusable test fixtures in `conftest.py`
5. **Mock external dependencies**: Use `unittest.mock` or `pytest-mock`

### Example Test

```python
import pytest
from workflow_agent.templates.utils import render_template

def test_render_template_with_valid_context():
    # Arrange
    template_path = "test_template.j2"
    context = {"name": "Test", "value": 123}
    expected_output = "Name: Test, Value: 123"
    
    # Create mock template system that returns expected output
    template_utils = mocker.patch("workflow_agent.templates.utils.TemplateUtils")
    template_utils.return_value.render_template.return_value = expected_output
    
    # Act
    result = render_template(template_path, context)
    
    # Assert
    assert result == expected_output
    template_utils.return_value.render_template.assert_called_once_with(template_path, context)
```

### Test Fixtures

Create fixtures in `conftest.py` for reusable test components:

```python
import pytest
from workflow_agent.core.state import WorkflowState

@pytest.fixture
def sample_workflow_state():
    """Return a sample workflow state for testing."""
    return WorkflowState(
        action="install",
        integration_type="test_integration",
        target_name="test-target",
        parameters={
            "host": "localhost",
            "port": "8080",
            "install_dir": "/tmp/test"
        }
    )
```

## Mocking Dependencies

For components with external dependencies, use mocking:

```python
def test_execute_with_successful_script(mocker):
    # Arrange
    mock_subprocess = mocker.patch("workflow_agent.execution.executor.async_secure_shell_execute")
    mock_subprocess.return_value = mocker.Mock(
        exit_code=0,
        stdout="Installation successful",
        stderr=""
    )
    
    script_executor = ScriptExecutor(config)
    
    # Act
    result = await script_executor.execute(sample_state_with_script)
    
    # Assert
    assert result.status == WorkflowStatus.COMPLETED
    assert not result.has_error
```

## Adding New Tests

When adding new functionality, create corresponding tests that:

1. Test both successful and error cases
2. Test edge cases and boundary conditions
3. Validate expected interactions between components
4. Cover all public methods and important private methods

A good target is to maintain at least 80% code coverage.
