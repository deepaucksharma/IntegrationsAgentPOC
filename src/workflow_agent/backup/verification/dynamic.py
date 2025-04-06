from typing import Dict, Any, Optional
import asyncio

class DynamicVerificationBuilder:
    """Builder for dynamic verification scripts."""
    
    def __init__(self):
        self._verifiers = {}

    def register_verifier(self, integration: str, verifier: Any) -> None:
        """Register a verifier for an integration."""
        self._verifiers[integration] = verifier

    async def build_verification_script(self, state: Dict[str, Any]) -> Optional[str]:
        """Build a verification script for a given state."""
        verifier = self._verifiers.get(state['integration_type'])
        if not verifier:
            return None

        try:
            script = await verifier.build_verification_script(state)
            return script
        except Exception as e:
            logger.error(f"Error building verification script: {e}")
            return None
