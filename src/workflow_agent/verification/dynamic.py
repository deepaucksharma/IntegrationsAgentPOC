import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class DynamicVerificationBuilder:
    """Builder for dynamic verification scripts."""
    
    def __init__(self):
        self._verifiers = {}

    def register_verifier(self, integration: str, verifier: Any) -> None:
        """Register a verifier for an integration."""
        self._verifiers[integration] = verifier
        logger.debug(f"Registered verifier for integration {integration}")

    async def build_verification_script(self, state: Dict[str, Any]) -> Optional[str]:
        """Build a verification script for a given state."""
        integration_type = state.get('integration_type')
        verifier = self._verifiers.get(integration_type)
        
        if not verifier:
            logger.warning(f"No verifier found for integration {integration_type}")
            return None

        try:
            logger.info(f"Building verification script for {integration_type}")
            script = await verifier.build_verification_script(state)
            return script
        except Exception as e:
            logger.error(f"Error building verification script: {e}")
            return None
