"""Infrastructure agent integration implementation."""
import logging
import os
from pathlib import Path
from typing import Dict, Any, List
from ..base import IntegrationBase

logger = logging.getLogger(__name__)

class InfraAgentIntegration(IntegrationBase):
    """Infrastructure agent integration handler."""
    
    def __init__(self):
        super().__init__()
        self.name = "infra_agent"
        self.version = "1.0.0"
        self.description = "Infrastructure agent integration"
        self.template_dir = Path(__file__).parent.parent / "common_templates"
    
    @classmethod
    def get_name(cls) -> str:
        return "infra_agent"
    
    @classmethod
    def get_supported_targets(cls) -> List[str]:
        return ["infrastructure-agent", "monitoring-agent"]
    
    @classmethod
    def get_category(cls) -> str:
        return "monitoring"
    
    def get_template_path(self, action: str) -> str:
        """Get the template path for the given action."""
        template_map = {
            "install": "install/infra_agent.sh.j2",
            "verify": "verify/infra_agent.sh.j2",
            "uninstall": "remove/infra_agent.sh.j2"
        }
        template_path = template_map.get(action)
        if not template_path:
            raise ValueError(f"No template found for action: {action}")
        
        full_path = self.template_dir / template_path
        if not full_path.exists():
            raise FileNotFoundError(f"Template file not found: {full_path}")
        
        return str(full_path)
    
    async def install(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Install the infrastructure agent."""
        template_path = self.get_template_path("install")
        return {
            "template_data": {
                "template_path": template_path,
                "version": self.version,
                "name": self.name,
                "license_key": parameters.get("license_key"),
                "host": parameters.get("host", "localhost"),
                "port": parameters.get("port", "8080"),
                "install_dir": parameters.get("install_dir"),
                "config_dir": parameters.get("config_dir")
            }
        }
    
    async def verify(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Verify the infrastructure agent installation."""
        template_path = self.get_template_path("verify")
        return {
            "template_data": {
                "template_path": template_path,
                "version": self.version,
                "name": self.name,
                "host": parameters.get("host", "localhost"),
                "port": parameters.get("port", "8080"),
                "install_dir": parameters.get("install_dir"),
                "config_dir": parameters.get("config_dir")
            }
        }
    
    async def uninstall(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Uninstall the infrastructure agent."""
        template_path = self.get_template_path("uninstall")
        return {
            "template_data": {
                "template_path": template_path,
                "version": self.version,
                "name": self.name,
                "install_dir": parameters.get("install_dir", "/opt/newrelic-infra"),
                "config_dir": parameters.get("config_dir", "/etc/newrelic-infra")
            }
        } 