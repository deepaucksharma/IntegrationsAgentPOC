"""
Enhanced knowledge base implementation that leverages caching and better search.
This implementation is a wrapper around the EnhancedKnowledgeBase from knowledge_cache.py.
"""
import logging
import os
import json
import yaml
from typing import Dict, Any, List, Optional, Union
import asyncio
from pathlib import Path

from .knowledge_cache import EnhancedKnowledgeBase

logger = logging.getLogger(__name__)

class KnowledgeBase:
    """
    Knowledge base with enhanced caching, search, and real-time updates.
    Provides backward compatibility with older code while adding enhanced features.
    """
    
    def __init__(self, storage_dir: Optional[str] = None, cache_enabled: bool = True):
        """
        Initialize knowledge base.
        
        Args:
            storage_dir: Directory for knowledge storage
            cache_enabled: Whether to enable caching
        """
        self.enhanced_kb = EnhancedKnowledgeBase(storage_dir, cache_enabled)
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize the knowledge base."""
        if not self._initialized:
            await self.enhanced_kb.initialize()
            self._initialized = True
        
    async def retrieve_documents(self, 
                                integration_type: str, 
                                target_name: Optional[str] = None, 
                                action: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve documents for a specific integration type.
        
        Args:
            integration_type: Integration type
            target_name: Optional target name
            action: Optional action
            
        Returns:
            Dictionary of documents
        """
        if not self._initialized:
            await self.initialize()
            
        return await self.enhanced_kb.retrieve_documents(integration_type, target_name, action)
        
    async def add_document(self, 
                          integration_type: str, 
                          target_name: str, 
                          doc_type: str, 
                          content: Dict[str, Any],
                          source: Optional[str] = None) -> bool:
        """
        Add a document to the knowledge base.
        
        Args:
            integration_type: Integration type
            target_name: Target name
            doc_type: Document type (definition, installation, etc.)
            content: Document content
            source: Optional source information
            
        Returns:
            True if document was added
        """
        if not self._initialized:
            await self.initialize()
            
        return await self.enhanced_kb.add_document(integration_type, target_name, doc_type, content, source)
        
    async def update_knowledge(self, 
                              integration_type: str, 
                              knowledge_update: Dict[str, Any],
                              source: Optional[str] = None) -> bool:
        """
        Update knowledge for an integration type.
        
        Args:
            integration_type: Integration type
            knowledge_update: Updated knowledge
            source: Optional source information
            
        Returns:
            True if update was successful
        """
        if not self._initialized:
            await self.initialize()
            
        return await self.enhanced_kb.update_knowledge(integration_type, knowledge_update, source)
        
    async def search_knowledge(self, 
                              query: str, 
                              context: Optional[Dict[str, Any]] = None, 
                              max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search for knowledge using a query string.
        
        Args:
            query: Search query
            context: Optional search context
            max_results: Maximum number of results
            
        Returns:
            List of matching knowledge items
        """
        if not self._initialized:
            await self.initialize()
            
        return await self.enhanced_kb.retrieve_knowledge(query, context, max_results)
        
    async def get_integration_knowledge(self, integration_type: str) -> Optional[Dict[str, Any]]:
        """
        Get preloaded knowledge for an integration type.
        
        Args:
            integration_type: Integration type
            
        Returns:
            Preloaded knowledge or None if not found
        """
        if not self._initialized:
            await self.initialize()
            
        # Try to get from cache
        knowledge = await self.enhanced_kb.cache.get_integration_knowledge(integration_type)
        if knowledge:
            return knowledge
            
        # Retrieve from storage
        return await self.retrieve_documents(integration_type)
        
    async def preload_integration(self, integration_type: str) -> bool:
        """
        Preload knowledge for an integration type.
        
        Args:
            integration_type: Integration type
            
        Returns:
            True if preloading was successful
        """
        if not self._initialized:
            await self.initialize()
            
        # Retrieve documents
        docs = await self.retrieve_documents(integration_type)
        
        # Preload into cache
        if docs and self.enhanced_kb.cache:
            await self.enhanced_kb.cache.preload_knowledge(integration_type, docs)
            return True
            
        return False
        
    async def clear_cache(self) -> None:
        """Clear all caches."""
        if self._initialized and self.enhanced_kb.cache:
            await self.enhanced_kb.cache.clear()
            
    async def invalidate_cache_for_integration(self, integration_type: str) -> None:
        """
        Invalidate cache for a specific integration.
        
        Args:
            integration_type: Integration type
        """
        if self._initialized and self.enhanced_kb.cache:
            await self.enhanced_kb.cache.invalidate_for_integration(integration_type)
            
    async def get_all_integration_types(self) -> List[str]:
        """
        Get all integration types in the knowledge base.
        
        Returns:
            List of integration types
        """
        if not self._initialized:
            await self.initialize()
            
        # Get integration types from storage directory
        storage_dir = self.enhanced_kb.storage_dir
        integration_types = []
        
        if os.path.exists(storage_dir):
            for entry in os.listdir(storage_dir):
                entry_path = os.path.join(storage_dir, entry)
                if os.path.isdir(entry_path) and entry != "common":
                    integration_types.append(entry)
                    
        return integration_types
