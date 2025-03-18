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
            
            # Update the state with both full and filtered documentation (with defensive check)
            if not hasattr(state, 'template_data') or state.template_data is None:
                state.template_data = {}
                
            state.template_data.update({
                "docs": docs,
                "platform_specific": platform_specific_docs,
                "platform_info": platform
            })
            
            logger.info("Successfully enhanced workflow state with documentation data")
            return state
            
        except Exception as e:
            logger.error(f"Failed to enhance workflow state: {e}")
            raise

    def _get_platform_info(self, system_context: Dict[str, Any]) -> Dict[str, str]:
        """Extracts platform information from system context."""
        platform_info = {
            "system": system_context.get("platform", {}).get("system", "").lower(),
            "distribution": system_context.get("platform", {}).get("distribution", "").lower(),
            "version": system_context.get("platform", {}).get("version", "")
        }
        
        # Normalize platform names
        if platform_info["system"] == "linux":
            if "ubuntu" in platform_info["distribution"]:
                platform_info["distribution"] = "ubuntu"
            elif any(dist in platform_info["distribution"] for dist in ["rhel", "centos", "fedora"]):
                platform_info["distribution"] = "rhel"
        elif "win" in platform_info["system"]:
            platform_info["system"] = "windows"
        elif "darwin" in platform_info["system"] or "mac" in platform_info["system"]:
            platform_info["system"] = "macos"
        
        return platform_info

    def _filter_for_platform(self, docs: Dict[str, Any], platform: Dict[str, str]) -> Dict[str, Any]:
        """Filters documentation based on the platform."""
        filtered_docs = {
            "prerequisites": [],
            "installation_methods": [],
            "configuration_options": docs.get("configuration_options", {}),
            "verification_steps": docs.get("verification_steps", [])
        }
        
        # Filter prerequisites
        for prereq in docs.get("prerequisites", []):
            if self._is_relevant_for_platform(prereq, platform):
                filtered_docs["prerequisites"].append(prereq)
        
        # Filter installation methods
        for method in docs.get("installation_methods", []):
            if self._is_method_compatible(method, platform):
                filtered_docs["installation_methods"].append(method)
        
        return filtered_docs

    def _is_relevant_for_platform(self, text: str, platform: Dict[str, str]) -> bool:
        """Determines if a text snippet is relevant for the current platform."""
        text_lower = text.lower()
        
        # If no platform-specific markers are found, consider it relevant
        if not any(os in text_lower for os in ["windows", "linux", "macos"]):
            return True
            
        # Check if text mentions current platform
        if platform["system"] in text_lower:
            return True
            
        # Check distribution-specific relevance
        if platform["system"] == "linux" and platform["distribution"] in text_lower:
            return True
            
        return False

    def _is_method_compatible(self, method: Dict[str, Any], platform: Dict[str, str]) -> bool:
        """Checks if an installation method is compatible with the platform."""
        platform_compat = method.get("platform_compatibility", [])
        
        # If no platform compatibility is specified, consider it compatible
        if not platform_compat:
            return True
            
        # Check system compatibility
        if platform["system"] in platform_compat:
            return True
            
        # Check distribution compatibility for Linux
        if platform["system"] == "linux" and platform["distribution"] in platform_compat:
            return True
            
        # If the method explicitly mentions another platform, it's incompatible
        if any(other_platform in platform_compat for other_platform in ["windows", "linux", "macos"] 
               if other_platform != platform["system"]):
            return False
            
        # Default to compatible if no definitive incompatibility
        return True