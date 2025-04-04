"""
Data-driven IntegrationBase: reads YAML files for install, remove, and verify.
"""
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

from ..core.state import WorkflowState

logger = logging.getLogger(__name__)

class IntegrationBase(ABC):
    """Base class for all integration plugins."""
    
    def __init__(self):
        self.name: str = self.get_name()
        self.version: str = "1.0.0"
        self.description: str = "Base integration class"
        
    @classmethod
    def get_name(cls) -> str:
        """Get the integration name."""
        return cls.__name__.lower().replace("integration", "")
    
    @classmethod
    def get_supported_targets(cls) -> List[str]:
        """Get list of supported targets."""
        root = Path(__file__).parent
        integration_name = cls.get_name()
        integration_dir = root / integration_name
        if not integration_dir.exists():
            return []
        return [d.name for d in integration_dir.iterdir() if d.is_dir()]
        
    @classmethod
    def get_category(cls) -> str:
        """Get the integration category."""
        return "custom"
    
    @classmethod
    def _integration_folder(cls, state: WorkflowState) -> Path:
        """Get the integration folder path."""
        root = Path(__file__).parent
        return root / state.integration_type.lower() / state.target_name.lower()

    @classmethod
    def get_integration_definition(cls, state: WorkflowState) -> Dict[str, Any]:
        """Get the integration definition from YAML."""
        folder = cls._integration_folder(state)
        path = folder / "definition.yaml"
        if not path.exists():
            logger.warning(f"No definition.yaml found at {path}")
            return {}
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML in {path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return {}

    @classmethod
    def get_parameter_schema(cls, state: WorkflowState) -> Dict[str, Any]:
        """Get the parameter schema from YAML."""
        folder = cls._integration_folder(state)
        path = folder / "parameters.yaml"
        if not path.exists():
            logger.warning(f"No parameters.yaml found at {path}")
            return {}
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML in {path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return {}

    @classmethod
    def get_verification_data(cls, state: WorkflowState) -> Dict[str, Any]:
        """Get the verification data from YAML."""
        folder = cls._integration_folder(state)
        path = folder / "verification.yaml"
        if not path.exists():
            logger.warning(f"No verification.yaml found at {path}")
            return {}
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML in {path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return {}

    async def handle(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle the workflow state."""
        validation_result = await self.validate(state)
        if not validation_result.get("valid", False):
            return {"error": validation_result.get("error", "Parameter validation failed")}
            
        definition_data = self.get_integration_definition(state)
        param_schema = self.get_parameter_schema(state)
        verification = self.get_verification_data(state)
        
        action_map = {
            "install": "install/base.sh",
            "remove": "remove/base.sh",
            "verify": "verify/base.sh",
        }
        
        if state.action not in action_map:
            return {"error": f"Unsupported action: {state.action}"}
            
        template_rel = action_map[state.action]
        template_path = Path(__file__).parent / "common_templates" / template_rel
        
        if not template_path.with_suffix(".j2").exists():
            # Try to look in common directories
            alt_paths = [
                Path(__file__).parent.parent / "integrations" / "common_templates" / template_rel,
                Path.cwd() / "src" / "workflow_agent" / "integrations" / "common_templates" / template_rel
            ]
            for alt_path in alt_paths:
                if alt_path.with_suffix(".j2").exists():
                    template_path = alt_path
                    break
            else:
                return {"error": f"Template not found: {template_path}.j2"}
                
        return {
            "template_path": str(template_path.with_suffix(".j2")),
            "template_data": definition_data,
            "parameter_schema": param_schema,
            "verification_data": verification,
            "source": "IntegrationBase"
        }

    async def validate(self, state: WorkflowState) -> Dict[str, bool]:
        """Validate the workflow state."""
        return {"valid": True}

    async def install(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Install the integration."""
        try:
            # TODO: Implement installation
            return {
                "success": True,
                "message": "Installation successful"
            }
        except Exception as e:
            logger.error(f"Installation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def verify(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Verify the integration."""
        try:
            # TODO: Implement verification
            return {
                "success": True,
                "message": "Verification successful"
            }
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def uninstall(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Uninstall the integration."""
        try:
            # TODO: Implement uninstallation
            return {
                "success": True,
                "message": "Uninstallation successful"
            }
        except Exception as e:
            logger.error(f"Uninstallation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_info(self) -> Dict[str, str]:
        """Get integration information."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description
        }