"""Documentation handling for integrations."""
from typing import Dict, Any, Optional

class DocumentationHandler:
    """Handles integration documentation."""
    
    def __init__(self):
        self._docs = {}
        
    def add_documentation(self, integration: str, docs: Dict[str, Any]) -> None:
        """Add documentation for an integration."""
        self._docs[integration] = docs
        
    def get_documentation(self, integration: str) -> Optional[Dict[str, Any]]:
        """Get documentation for an integration."""
        return self._docs.get(integration)
        
    def list_documented_integrations(self) -> list:
        """List all integrations with documentation."""
        return list(self._docs.keys())
