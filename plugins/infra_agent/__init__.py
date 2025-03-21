"""
Basic integration plugin for infrastructure agent.
"""
from typing import Dict, Any, Optional, List
from workflow_agent.integrations.base import IntegrationBase

class InfraAgentIntegration(IntegrationBase):
    """Integration for infrastructure agent."""
    
    def __init__(self):
        super().__init__()
        self.name = "infra_agent"
        self.version = "1.0.0"
        self.description = "Basic infrastructure agent integration for testing"
        
    @classmethod
    def get_name(cls) -> str:
        """Get the integration name."""
        return "infra_agent"
        
    @classmethod
    def get_supported_targets(cls) -> List[str]:
        """Get list of supported targets."""
        return ["infrastructure-agent", "monitoring-agent"]
        
    @classmethod
    def get_category(cls) -> str:
        """Get the integration category."""
        return "monitoring"
        
    async def install(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Install the infrastructure agent."""
        license_key = parameters.get("license_key")
        host = parameters.get("host", "localhost")
        port = parameters.get("port", "8080")
        install_dir = parameters.get("install_dir")
        config_dir = parameters.get("config_path")
        
        return {
            "template_path": "install.yaml",
            "template_data": {
                "version": self.version,
                "name": self.name,
                "license_key": license_key,
                "host": host,
                "port": port,
                "install_dir": install_dir,
                "config_dir": config_dir
            }
        }
        
    async def verify(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Verify the infrastructure agent installation."""
        host = parameters.get("host", "localhost")
        port = parameters.get("port", "8080")
        install_dir = parameters.get("install_dir")
        config_dir = parameters.get("config_path")
        
        return {
            "template_path": "verify.yaml",
            "template_data": {
                "version": self.version,
                "name": self.name,
                "host": host,
                "port": port,
                "install_dir": install_dir,
                "config_dir": config_dir
            }
        }
        
    async def uninstall(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Uninstall the infrastructure agent."""
        install_dir = parameters.get("install_dir")
        config_dir = parameters.get("config_path")
        
        return {
            "template_path": "uninstall.yaml",
            "template_data": {
                "version": self.version,
                "name": self.name,
                "install_dir": install_dir,
                "config_dir": config_dir
            }
        } 