"""Error handling for integrations."""

class IntegrationError(Exception):
    """Base class for integration errors."""
    pass

class ConfigurationError(IntegrationError):
    """Configuration error."""
    pass

class ValidationError(IntegrationError):
    """Validation error."""
    pass

class ExecutionError(IntegrationError):
    """Execution error."""
    pass 