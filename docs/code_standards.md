# Code Standards

This document outlines the code standards for the IntegrationsAgentPOC project, including documentation, error handling, and architecture guidelines.

## Documentation Standards

### Module Documentation

Every module should have a docstring that includes:

1. A one-line summary
2. A more detailed description of the module's purpose
3. Important usage information or examples

Example:
```python
"""
Configuration loading module for the workflow agent.

This module provides a unified way to load configuration from files and environment
variables for use by both the framework and example scripts. It supports merging
configurations from multiple sources with a clear precedence order.

Usage:
    from workflow_agent.config.loader import load_config
    config = load_config(config_path="path/to/config.yaml")
"""
```

### Class Documentation

Class docstrings should follow this pattern:

```python
class ExampleClass:
    """
    One-line class description.
    
    Detailed multi-line description of the class functionality,
    usage examples, and important implementation details.
    """
```

### Method Documentation

Method docstrings should include:

1. A brief description
2. Parameter descriptions
3. Return value description
4. Exceptions raised

Example:
```python
def example_method(self, param1: str, param2: int) -> bool:
    """
    Brief description of what the method does.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: When and why this exception is raised
    """
```

## Error Handling Standards

### Using the Error Handler

All error-prone code should use the standardized error handlers:

1. For synchronous code:
```python
@handle_safely
def my_function():
    # Function implementation
```

2. For asynchronous code:
```python
@handle_safely_async
async def my_async_function():
    # Async function implementation
```

### Exception Hierarchy

- Use specific exceptions from the exception module
- Catch exceptions at appropriate levels
- Log exceptions with appropriate severity
- Include context in exception information

## Architecture Guidelines

### Single Responsibility Principle

Each class should have a single responsibility. Break large classes into smaller, focused ones:

- **Good**: `TemplateRenderer`, `ScriptExecutor`, `OutputProcessor`
- **Bad**: `WorkflowRunner` that does rendering, execution, and output processing

### Dependency Injection

Use dependency injection for better testability and flexibility:

```python
class Service:
    def __init__(self, dependency1, dependency2=None):
        self.dependency1 = dependency1
        self.dependency2 = dependency2 or DefaultDependency()
```

### Service Lifecycle

Services should implement lifecycle methods:

```python
async def initialize(self):
    # Initialization logic
    
async def cleanup(self):
    # Cleanup logic
```

## Template Pattern

Use the following template for new classes:

```python
"""
Brief module description.

Detailed module description and usage examples.
"""
import logging
from typing import Dict, Any, Optional

from ..error.handler import handle_safely, handle_safely_async

logger = logging.getLogger(__name__)

class NewComponent:
    """
    Brief component description.
    
    Detailed component description and functionality explanation.
    """
    
    def __init__(self, dependency1, dependency2=None):
        """
        Initialize the component.
        
        Args:
            dependency1: Description of dependency1
            dependency2: Description of dependency2
        """
        self.dependency1 = dependency1
        self.dependency2 = dependency2
        logger.debug(f"Initialized {self.__class__.__name__}")
    
    async def initialize(self) -> None:
        """Initialize the component resources."""
        logger.info(f"Initializing {self.__class__.__name__}")
        # Initialization logic
    
    async def cleanup(self) -> None:
        """Clean up component resources."""
        logger.info(f"Cleaning up {self.__class__.__name__}")
        # Cleanup logic
    
    @handle_safely
    def sync_method(self, arg1: str) -> Any:
        """
        Synchronous method with error handling.
        
        Args:
            arg1: Description of arg1
            
        Returns:
            Description of return value
        """
        # Method implementation
    
    @handle_safely_async
    async def async_method(self, arg1: str) -> Any:
        """
        Asynchronous method with error handling.
        
        Args:
            arg1: Description of arg1
            
        Returns:
            Description of return value
        """
        # Method implementation
```
