# Integration Plugins

This directory contains plugins that extend the functionality of the workflow agent with specific integrations.

## Available Plugins
- `infra_agent`: Infrastructure agent integration for New Relic monitoring

## Plugin Architecture

Plugins are dynamically discovered and loaded by the `IntegrationRegistry` component. Each plugin:

1. Implements the `IntegrationBase` interface
2. Has a unique integration name and supported targets
3. Provides implementation for at least the `install`, `verify`, and `uninstall` operations
4. Returns template paths and data for rendering scripts

## Creating a New Plugin

To create a new integration plugin:

1. Create a new directory with your integration name (e.g., `my_integration`)
2. Create an `__init__.py` file with your integration class:

```python
"""
Integration plugin for my custom integration.
"""
from typing import Dict, Any, Optional, List
from workflow_agent.integrations.base import IntegrationBase

class MyIntegration(IntegrationBase):
    """Integration for my custom service."""
    
    def __init__(self):
        super().__init__()
        self.name = "my_integration"
        self.version = "1.0.0"
        self.description = "My custom integration plugin"
        
    @classmethod
    def get_name(cls) -> str:
        """Get the integration name."""
        return "my_integration"
        
    @classmethod
    def get_supported_targets(cls) -> List[str]:
        """Get list of supported targets."""
        return ["my-service", "my-application"]
        
    @classmethod
    def get_category(cls) -> str:
        """Get the integration category."""
        return "custom"
        
    async def install(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Install the integration."""
        # Extract parameters
        install_dir = parameters.get("install_dir")
        
        # Return template information
        return {
            "template_path": "install.yaml",  # Path relative to templates directory
            "template_data": {
                "version": self.version,
                "name": self.name,
                "install_dir": install_dir,
                # Add any other template variables
            }
        }
        
    async def verify(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Verify the integration installation."""
        # Implementation...
        
    async def uninstall(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Uninstall the integration."""
        # Implementation...
```

3. Create templates in the `templates/[integration_name]/` directory:
   - `install.ps1.j2` or `install.sh.j2` for installation scripts
   - `verify.ps1.j2` or `verify.sh.j2` for verification scripts
   - `uninstall.ps1.j2` or `uninstall.sh.j2` for uninstallation scripts

## Registration

Plugins are automatically registered when the application starts by the `IntegrationRegistry`. The registry scans the plugins directory for any modules containing classes that implement the `IntegrationBase` interface.

## Testing Plugins

To test your plugin, run:

```bash
python -m workflow_agent install my_integration --host localhost --install_dir /path/to/install
```

See the `infra_agent` plugin for a complete example implementation.
