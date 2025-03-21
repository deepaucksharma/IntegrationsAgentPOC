"""Storage handling for integrations."""
from typing import Dict, Any, Optional
import os
import json

class StorageManager:
    """Manages persistent storage for integrations."""
    
    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        
    def save(self, integration: str, data: Dict[str, Any]) -> None:
        """Save integration data."""
        path = os.path.join(self.storage_dir, f"{integration}.json")
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
            
    def load(self, integration: str) -> Optional[Dict[str, Any]]:
        """Load integration data."""
        path = os.path.join(self.storage_dir, f"{integration}.json")
        if not os.path.exists(path):
            return None
            
        with open(path, 'r') as f:
            return json.load(f)
            
    def delete(self, integration: str) -> bool:
        """Delete integration data."""
        path = os.path.join(self.storage_dir, f"{integration}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False 