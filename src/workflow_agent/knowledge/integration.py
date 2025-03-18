import logging
from typing import Dict, Any
from ..documentation.parser import DocumentationParser

logger = logging.getLogger(__name__)

class DynamicIntegrationKnowledge:
    """Enhances workflow state with documentation-based knowledge."""
    def __init__(self, doc_parser: DocumentationParser = None):
        self.parser = doc_parser or DocumentationParser()

    async def enhance_workflow_state(self, state: Any) -> Any:
        logger.info(f"Enhancing state for integration: {state.integration_type}")
        docs = await self.parser.fetch_integration_docs(state.integration_type)
        platform = self._get_platform_info(state.system_context)
        filtered_docs = self._filter_for_platform(docs, platform)
        if not hasattr(state, 'template_data'):
            state.template_data = {}
        state.template_data.update({
            "docs": docs,
            "platform_specific": filtered_docs,
            "platform_info": platform
        })
        return state

    def _get_platform_info(self, system_context: Dict[str, Any]) -> Dict[str, str]:
        platform_info = {
            "system": system_context.get("platform", {}).get("system", "").lower(),
            "distribution": system_context.get("platform", {}).get("distribution", "").lower(),
            "version": system_context.get("platform", {}).get("version", "")
        }
        if platform_info["system"] == "linux" and "ubuntu" in platform_info["distribution"]:
            platform_info["distribution"] = "ubuntu"
        return platform_info

    def _filter_for_platform(self, docs: Dict[str, Any], platform: Dict[str, str]) -> Dict[str, Any]:
        filtered = {
            "prerequisites": [pr for pr in docs.get("prerequisites", []) if platform["system"] in pr.lower()],
            "installation_methods": [m for m in docs.get("installation_methods", []) if platform["system"] in " ".join(m.get("platform_compatibility", [])).lower()],
            "configuration_options": docs.get("configuration_options", {}),
            "verification_steps": docs.get("verification_steps", [])
        }
        return filtered