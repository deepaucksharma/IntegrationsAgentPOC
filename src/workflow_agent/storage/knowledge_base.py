"""
Knowledge base for storing integration documentation and improvements.
"""
import os
import logging
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncio

logger = logging.getLogger(__name__)

class KnowledgeBase:
    """Storage for integration documentation and learning data."""
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or os.path.join(os.path.dirname(__file__), "knowledge")
        self.documents = {}
        self.improvements = {}
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize the knowledge base."""
        try:
            os.makedirs(self.storage_path, exist_ok=True)
        except Exception as e:
            logger.error(f"Error creating knowledge base directory: {e}")
            self.storage_path = tempfile.mkdtemp(prefix="workflow_kb_")
            logger.warning(f"Using temporary directory: {self.storage_path}")
            
        docs_path = os.path.join(self.storage_path, "documents.json")
        if os.path.exists(docs_path):
            try:
                with open(docs_path, "r") as f:
                    self.documents = json.load(f)
                logger.info(f"Loaded {len(self.documents)} documents from knowledge base")
            except Exception as e:
                logger.error(f"Error loading documents: {e}")
        improvements_path = os.path.join(self.storage_path, "improvements.json")
        if os.path.exists(improvements_path):
            try:
                with open(improvements_path, "r") as f:
                    self.improvements = json.load(f)
                logger.info(f"Loaded improvements for {len(self.improvements)} integrations")
            except Exception as e:
                logger.error(f"Error loading improvements: {e}")
    
    async def add_document(self, integration_type: str, target_name: str, doc_type: str, content: Dict[str, Any]) -> None:
        """Add a document to the knowledge base."""
        key = f"{integration_type}_{target_name}_{doc_type}"
        async with self._lock:
            self.documents[key] = content
            try:
                docs_path = os.path.join(self.storage_path, "documents.json")
                with open(docs_path, "w") as f:
                    json.dump(self.documents, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving documents: {e}")
    
    async def retrieve_documents(self, integration_type: str, target_name: str, action: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve documents for an integration."""
        result = {}
        def_key = f"{integration_type}_{target_name}_definition"
        if def_key in self.documents:
            result["definition"] = self.documents[def_key]
        param_key = f"{integration_type}_{target_name}_parameters"
        if param_key in self.documents:
            result["parameters"] = self.documents[param_key]
        verify_key = f"{integration_type}_{target_name}_verification"
        if verify_key in self.documents:
            result["verification"] = self.documents[verify_key]
        return result
    
    async def get_all_documents(self, integration_type: Optional[str] = None) -> Dict[str, Any]:
        """Get all documents, optionally filtered by integration type."""
        if not integration_type:
            return self.documents
        return {
            k: v
            for k, v in self.documents.items()
            if k.startswith(f"{integration_type}_")
        }
    
    async def add_improvement(self, integration_type: str, target_name: str, improvement: Dict[str, Any]) -> None:
        """Add an improvement to the knowledge base."""
        key = f"{integration_type}_{target_name}"
        async with self._lock:
            if key not in self.improvements:
                self.improvements[key] = []
            self.improvements[key].append(improvement)
            try:
                improvements_path = os.path.join(self.storage_path, "improvements.json")
                with open(improvements_path, "w") as f:
                    json.dump(self.improvements, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving improvements: {e}")
    
    async def get_improvements(self, integration_type: str, target_name: str) -> List[Dict[str, Any]]:
        """Get improvements for an integration."""
        key = f"{integration_type}_{target_name}"
        return self.improvements.get(key, [])
    
    async def query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Query the knowledge base."""
        result = {"query": query, "results": []}
        integration_type = context.get("integration_type")
        target_name = context.get("target_name")
        if integration_type and target_name:
            docs = await self.retrieve_documents(integration_type, target_name)
            if docs:
                result["results"].append({"source": "integration_docs", "content": docs})
            improvements = await self.get_improvements(integration_type, target_name)
            if improvements:
                result["results"].append({"source": "improvements", "content": improvements})
        # Minimal textual search across docs
        search_term = query.lower()
        for doc_key, doc_content in self.documents.items():
            text = json.dumps(doc_content).lower()
            if search_term in text:
                result["results"].append({
                    "source": f"doc:{doc_key}",
                    "content": doc_content
                })
        return result