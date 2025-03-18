"""Enhanced workflow state knowledge integration with platform-aware filtering."""
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError
from ..documentation.parser import DocumentationParser, DocumentationFetchError
from ..error.exceptions import KnowledgeEnhancementError

logger = logging.getLogger(__name__)

class IntegrationContext(BaseModel):
    """Normalized platform context model with validation."""
    system: str = Field(default="unknown", description="Normalized OS name")
    distribution: str = Field(default="", description="Linux distribution family")
    version: str = Field(default="", description="OS version")
    architecture: str = Field(default="", description="System architecture")

    @classmethod
    def from_raw_data(cls, data: Dict[str, Any]) -> 'IntegrationContext':
        """Create context from raw system data with normalization."""
        try:
            return cls(
                system=cls._normalize_system(data.get("system", "")),
                distribution=cls._normalize_distribution(data.get("distribution", "")),
                version=data.get("version", ""),
                architecture=data.get("architecture", "")
            )
        except ValidationError as e:
            logger.warning("Failed to validate platform context: %s", e)
            return cls()

    @staticmethod
    def _normalize_system(system: str) -> str:
        """Normalize system names to consistent values."""
        system_lower = system.lower()
        if 'linux' in system_lower:
            return 'linux'
        if 'win' in system_lower:
            return 'windows'
        if 'darwin' in system_lower or 'mac' in system_lower:
            return 'macos'
        return system_lower

    @staticmethod
    def _normalize_distribution(distribution: str) -> str:
        """Normalize Linux distributions to families."""
        dist_lower = distribution.lower()
        for family in ['debian', 'rhel', 'suse']:
            if family in dist_lower:
                return family
        return dist_lower

class DocumentationEnhancer:
    """Enhanced documentation processor with platform-aware filtering."""
    
    def __init__(self, parser: DocumentationParser):
        self.parser = parser
        self.cache: Dict[str, Dict] = {}

    async def enhance_state(self, state: Any) -> Any:
        """Enhance workflow state with validated documentation data."""
        try:
            ctx = self._extract_context(state)
            docs = await self._get_documentation(state.integration_type)
            
            filtered_docs = {
                'prerequisites': self._filter_items(docs.get('prerequisites', []), ctx),
                'installation_methods': self._filter_installation_methods(docs.get('installation_methods', []), ctx),
                'configuration': docs.get('configuration', {}),
                'verification': docs.get('verification', [])
            }

            return state.evolve(
                template_data={
                    **state.template_data,
                    'documentation': filtered_docs,
                    'platform_context': ctx.dict()
                }
            )
        except DocumentationFetchError as e:
            logger.error("Documentation fetch failed: %s", e)
            return state.add_warning(f"Documentation unavailable: {e}")
        except Exception as e:
            logger.error("Enhancement failed: %s", e, exc_info=True)
            raise KnowledgeEnhancementError(f"State enhancement failed: {e}") from e

    def _extract_context(self, state: Any) -> IntegrationContext:
        """Extract and validate platform context from state."""
        raw_data = state.system_context.get('platform', {}) if state.system_context else {}
        return IntegrationContext.from_raw_data(raw_data)

    async def _get_documentation(self, integration_type: str) -> Dict:
        """Get cached or fresh documentation with validation."""
        if integration_type in self.cache:
            return self.cache[integration_type]
            
        docs = await self.parser.fetch_integration_docs(integration_type)
        self._validate_documentation(docs)
        self.cache[integration_type] = docs
        return docs

    def _validate_documentation(self, docs: Dict) -> None:
        """Validate documentation structure."""
        required_sections = ['prerequisites', 'installation_methods']
        for section in required_sections:
            if section not in docs:
                raise KnowledgeEnhancementError(f"Missing documentation section: {section}")

    def _filter_items(self, items: List[Dict], ctx: IntegrationContext) -> List[Dict]:
        """Filter items based on platform compatibility."""
        return [item for item in items if self._is_compatible(item.get('platforms', []), ctx)]

    def _filter_installation_methods(self, methods: List[Dict], ctx: IntegrationContext) -> List[Dict]:
        """Filter and prioritize installation methods."""
        compatible_methods = [m for m in methods if self._is_compatible(m.get('platforms', []), ctx)]
        return sorted(compatible_methods, key=lambda m: m.get('priority', 0), reverse=True)

    def _is_compatible(self, platforms: List[str], ctx: IntegrationContext) -> bool:
        """Check compatibility with platform context."""
        if not platforms:
            return True
            
        platform_patterns = [
            self._create_pattern(ctx.system),
            self._create_pattern(ctx.distribution),
            self._create_pattern(ctx.architecture)
        ]
        
        return any(
            re.search(pattern, platform, re.IGNORECASE)
            for platform in platforms
            for pattern in platform_patterns
            if pattern
        )

    def _create_pattern(self, value: str) -> str:
        """Create regex pattern for platform matching."""
        return f"\\b{re.escape(value)}\\b" if value else "" 