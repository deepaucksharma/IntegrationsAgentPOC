"""Module for managing dynamic integration knowledge based on documentation."""
from typing import Dict, Any, List
import logging
from ..documentation.parser import DocumentationParser

logger = logging.getLogger(__name__)

class DynamicIntegrationKnowledge:
    """Enhances workflow state with documentation-based knowledge."""
    
    def __init__(self, doc_parser: DocumentationParser = None):
        """Initialize the knowledge manager."""
        self.parser = doc_parser or DocumentationParser()

    async def enhance_workflow_state(self, state: Any) -> Any:
        """Updates the workflow state with documentation data."""
        try:
            logger.info(f"Enhancing workflow state for integration: {state.integration_type}")
            docs = await self.parser.fetch_integration_docs(state.integration_type)
            
            # Get platform information from system context (with defensive check)
            platform = self._get_platform_info(state.system_context or {})
            
            # Filter and enhance the documentation data
            platform_specific_docs = self._filter_for_platform(docs, platform)
            
            # Get installation methods
            installation_methods = self._get_installation_methods(docs, platform)
            
            # Update the state with documentation and installation data
            if not hasattr(state, 'template_data') or state.template_data is None:
                state.template_data = {}
                
            state.template_data.update({
                "docs": docs,
                "platform_specific": platform_specific_docs,
                "platform_info": platform,
                "installation_methods": installation_methods
            })
            
            logger.info("Successfully enhanced workflow state with documentation data")
            return state
            
        except Exception as e:
            logger.error(f"Failed to enhance workflow state: {e}")
            raise

    def _get_platform_info(self, system_context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract platform information from system context."""
        platform_info = system_context.get("platform", {})
        return {
            "system": platform_info.get("system", "unknown").lower(),
            "release": platform_info.get("release", "unknown"),
            "version": platform_info.get("version", "unknown"),
            "architecture": platform_info.get("architecture", "unknown").lower()
        }

    def _filter_for_platform(self, docs: Dict[str, Any], platform: Dict[str, Any]) -> Dict[str, Any]:
        """Filter documentation for specific platform."""
        platform_docs = {}
        system = platform["system"]
        
        for section, content in docs.items():
            if isinstance(content, dict):
                if system in content:
                    platform_docs[section] = content[system]
                elif "common" in content:
                    platform_docs[section] = content["common"]
            else:
                platform_docs[section] = content
                
        return platform_docs

    def _get_installation_methods(self, docs: Dict[str, Any], platform: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract installation methods from documentation."""
        methods = []
        system = platform["system"]
        
        # Get installation methods from docs
        install_data = docs.get("installation", {})
        
        # Add platform-specific methods
        if system in install_data:
            methods.extend(self._parse_installation_methods(install_data[system]))
            
        # Add common methods
        if "common" in install_data:
            methods.extend(self._parse_installation_methods(install_data["common"]))
            
        # If no methods found, add default method
        if not methods:
            methods.append({
                "name": "default",
                "type": "script",
                "description": "Default installation method",
                "template": "install/base.sh.j2" if system == "linux" else "install/base.ps1.j2"
            })
            
        return methods

    def _parse_installation_methods(self, data: Any) -> List[Dict[str, Any]]:
        """Parse installation methods from documentation data."""
        methods = []
        
        if isinstance(data, dict):
            for method_name, method_data in data.items():
                if isinstance(method_data, dict):
                    methods.append({
                        "name": method_name,
                        "type": method_data.get("type", "script"),
                        "description": method_data.get("description", ""),
                        "template": method_data.get("template", ""),
                        "requirements": method_data.get("requirements", [])
                    })
                    
        return methods