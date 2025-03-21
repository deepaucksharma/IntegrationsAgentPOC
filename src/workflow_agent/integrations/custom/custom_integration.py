"""Custom integration implementation."""
import logging
import os
from pathlib import Path
from typing import Dict, Any, List
from ..base import IntegrationBase

logger = logging.getLogger(__name__)

class CustomIntegration(IntegrationBase):
    """Custom integration handler."""
    
    def __init__(self):
        super().__init__()
        self.name = "custom"
        self.version = "1.0.0"
        self.description = "Custom integration"
        self.template_dir = Path(__file__).parent.parent / "common_templates"
    
    @classmethod
    def get_name(cls) -> str:
        return "custom"
    
    @classmethod
    def get_supported_targets(cls) -> List[str]:
        return ["custom-integration"]
    
    @classmethod
    def get_category(cls) -> str:
        return "custom"
    
    def get_template_path(self, action: str) -> str:
        """Get the template path for the given action."""
        template_map = {
            "install": "install/custom_integration.sh.j2",
            "verify": "verify/custom_integration.sh.j2",
            "uninstall": "remove/custom_integration.sh.j2"
        }
        template_path = template_map.get(action)
        if not template_path:
            raise ValueError(f"No template found for action: {action}")
        
        full_path = self.template_dir / template_path
        if not full_path.exists():
            raise FileNotFoundError(f"Template file not found: {full_path}")
        
        return str(full_path)
    
    async def install(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Install the custom integration."""
        template_path = self.get_template_path("install")
        return {
            "success": True,
            "message": "Custom integration installation template generated",
            "template_path": template_path,
            "template_data": {
                "version": self.version,
                "name": self.name,
                "integration_url": parameters.get("integration_url"),
                "config_path": parameters.get("config_path"),
                "is_windows": "win" in os.name.lower()
            },
            "parameter_schema": {
                "type": "object",
                "properties": {
                    "integration_url": {
                        "type": "string",
                        "description": "URL to download the integration from"
                    },
                    "config_path": {
                        "type": "string",
                        "description": "Path to store integration configuration"
                    }
                },
                "required": ["integration_url", "config_path"]
            },
            "verification_data": {
                "checks": [
                    {
                        "type": "file_exists",
                        "path": parameters.get("config_path"),
                        "description": "Check if config directory exists"
                    }
                ]
            }
        }
    
    async def verify(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Verify the custom integration installation."""
        template_path = self.get_template_path("verify")
        return {
            "success": True,
            "message": "Custom integration verification template generated",
            "template_path": template_path,
            "template_data": {
                "version": self.version,
                "name": self.name,
                "config_path": parameters.get("config_path"),
                "is_windows": "win" in os.name.lower()
            },
            "parameter_schema": {
                "type": "object",
                "properties": {
                    "config_path": {
                        "type": "string",
                        "description": "Path to integration configuration"
                    }
                },
                "required": ["config_path"]
            },
            "verification_data": {
                "checks": [
                    {
                        "type": "file_exists",
                        "path": parameters.get("config_path"),
                        "description": "Check if config directory exists"
                    }
                ]
            }
        }
    
    async def uninstall(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Uninstall the custom integration."""
        template_path = self.get_template_path("uninstall")
        return {
            "success": True,
            "message": "Custom integration uninstallation template generated",
            "template_path": template_path,
            "template_data": {
                "version": self.version,
                "name": self.name,
                "config_path": parameters.get("config_path"),
                "is_windows": "win" in os.name.lower()
            },
            "parameter_schema": {
                "type": "object",
                "properties": {
                    "config_path": {
                        "type": "string",
                        "description": "Path to integration configuration"
                    }
                },
                "required": ["config_path"]
            },
            "verification_data": {
                "checks": [
                    {
                        "type": "file_not_exists",
                        "path": parameters.get("config_path"),
                        "description": "Check if config directory was removed"
                    }
                ]
            }
        } 