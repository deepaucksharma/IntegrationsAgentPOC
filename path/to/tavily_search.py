import os
import logging
import aiohttp
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class TavilySearchClient:
    """Client for interacting with Tavily Search API."""
    
    def __init__(self, api_key: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize Tavily Search client with API key and optional caching.
        
        Args:
            api_key: Tavily API key (defaults to TAVILY_API_KEY environment variable)
            cache_dir: Directory for caching search results
        """
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com/v1"
        self.cache_dir = Path(cache_dir) if cache_dir else None
        
        if self.cache_dir:
            self.cache_dir.mkdir(exist_ok=True, parents=True)
            
        if not self.api_key:
            logger.warning("No Tavily API key provided. Set the TAVILY_API_KEY environment variable.")
    
    async def search(self, 
                    query: str, 
                    search_depth: str = "basic", 
                    include_domains: Optional[List[str]] = None,
                    exclude_domains: Optional[List[str]] = None,
                    max_results: int = 5,
                    use_cache: bool = True) -> Dict[str, Any]:
        """
        Perform a search using Tavily API.
        
        Args:
            query: Search query
            search_depth: "basic" or "advanced"
            include_domains: List of domains to include in search
            exclude_domains: List of domains to exclude from search
            max_results: Maximum number of results to return
            use_cache: Whether to use cached results if available
            
        Returns:
            Search results dictionary
        """
        if not self.api_key:
            return {"error": "No API key provided", "results": []}
            
        # Check cache if enabled
        if self.cache_dir and use_cache:
            cached_result = self._check_cache(query, include_domains, exclude_domains)
            if cached_result:
                logger.debug(f"Using cached result for query: {query}")
                return cached_result
        
        try:
            # Prepare search parameters
            params = {
                "query": query,
                "search_depth": search_depth,
                "max_results": max_results
            }
            
            if include_domains:
                params["include_domains"] = include_domains
                
            if exclude_domains:
                params["exclude_domains"] = exclude_domains
            
            # Make API request
            headers = {"Content-Type": "application/json", "x-api-key": self.api_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/search",
                    headers=headers,
                    json=params
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # Cache result if enabled
                        if self.cache_dir:
                            self._cache_result(query, result, include_domains, exclude_domains)
                            
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Tavily API error ({response.status}): {error_text}")
                        return {
                            "error": f"API error ({response.status}): {error_text}",
                            "results": []
                        }
        
        except Exception as e:
            logger.error(f"Error during Tavily search: {e}")
            return {"error": str(e), "results": []}
    
    def _get_cache_key(self, query: str, include_domains: Optional[List[str]], exclude_domains: Optional[List[str]]) -> str:
        """Generate a cache key for the query and domain filters."""
        key_parts = [query]
        
        if include_domains:
            key_parts.append("include:" + ",".join(sorted(include_domains)))
            
        if exclude_domains:
            key_parts.append("exclude:" + ",".join(sorted(exclude_domains)))
            
        # Create a filename-safe key
        import hashlib
        hash_obj = hashlib.md5("_".join(key_parts).encode())
        return hash_obj.hexdigest()
    
    def _check_cache(self, query: str, include_domains: Optional[List[str]], exclude_domains: Optional[List[str]]) -> Optional[Dict[str, Any]]:
        """Check if a cached result exists."""
        if not self.cache_dir:
            return None
            
        cache_key = self._get_cache_key(query, include_domains, exclude_domains)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)
                    
                # Check if cache is still valid
                import time
                if time.time() - cached_data.get("cached_at", 0) < 86400:  # 24 hour cache
                    return cached_data.get("data", {})
            except Exception as e:
                logger.warning(f"Error reading cache file: {e}")
                
        return None
    
    def _cache_result(self, query: str, result: Dict[str, Any], include_domains: Optional[List[str]], exclude_domains: Optional[List[str]]) -> None:
        """Cache a search result."""
        if not self.cache_dir:
            return
            
        try:
            cache_key = self._get_cache_key(query, include_domains, exclude_domains)
            cache_file = self.cache_dir / f"{cache_key}.json"
            
            import time
            cache_data = {
                "cached_at": time.time(),
                "query": query,
                "include_domains": include_domains,
                "exclude_domains": exclude_domains,
                "data": result
            }
            
            with open(cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)
                
        except Exception as e:
            logger.warning(f"Error caching search result: {e}")

class TavilyDocumentationSearcher:
    """Documentation searcher using Tavily search API."""
    
    def __init__(self, api_key: Optional[str] = None, cache_dir: Optional[str] = None):
        """Initialize the documentation searcher."""
        self.client = TavilySearchClient(api_key, cache_dir)
    
    async def search_documentation(self, integration_type: str, search_domains: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search for documentation on a specific integration type.
        
        Args:
            integration_type: Integration type to search for
            search_domains: Optional domains to limit the search to
            
        Returns:
            List of search result dictionaries
        """
        # Define search domains if not provided
        if not search_domains:
            search_domains = [
                "docs.newrelic.com", 
                "newrelic.com",
                "github.com"
            ]
        
        # Construct query
        query = f"{integration_type} integration installation documentation"
        
        # Perform search
        result = await self.client.search(
            query=query,
            search_depth="advanced",
            include_domains=search_domains,
            max_results=10,
            use_cache=True
        )
        
        if "error" in result:
            logger.error(f"Search error: {result['error']}")
            return []
            
        return result.get("results", [])
    
    async def search_verification_steps(self, integration_type: str) -> List[Dict[str, Any]]:
        """
        Search for verification steps for an integration.
        
        Args:
            integration_type: Integration type to search for
            
        Returns:
            List of verification steps
        """
        query = f"{integration_type} integration verification steps how to verify"
        
        result = await self.client.search(
            query=query,
            search_depth="basic",
            include_domains=["docs.newrelic.com", "newrelic.com", "github.com"],
            max_results=5,
            use_cache=True
        )
        
        if "error" in result:
            logger.error(f"Search error: {result['error']}")
            return []
            
        return result.get("results", [])
    
    def extract_verification_steps(self, search_results: List[Dict[str, Any]]) -> List[str]:
        """
        Extract verification steps from search results.
        
        Args:
            search_results: Search results from Tavily
            
        Returns:
            List of verification step strings
        """
        steps = []
        
        for result in search_results:
            content = result.get("content", "")
            
            # Look for patterns that might indicate verification steps
            import re
            
            # Check for numbered lists
            numbered_steps = re.findall(r'(\d+\.\s+.*?)(?=\d+\.\s+|$)', content, re.DOTALL)
            if numbered_steps:
                steps.extend([step.strip() for step in numbered_steps])
                continue
                
            # Check for bullet points
            bullet_steps = re.findall(r'(?:•|\*|-)\s+(.*?)(?=(?:•|\*|-)|$)', content, re.DOTALL)
            if bullet_steps:
                steps.extend([step.strip() for step in bullet_steps])
                continue
                
            # As a fallback, look for "verify" or "check" sentences
            verify_sentences = re.findall(r'(?:verify|check|confirm|ensure|validate)(?:[^.!?]*)[.!?]', content, re.IGNORECASE)
            if verify_sentences:
                steps.extend([sentence.strip() for sentence in verify_sentences])
        
        # Remove duplicates while preserving order
        unique_steps = []
        for step in steps:
            if step not in unique_steps and len(step) > 10:  # Minimum length to filter out noise
                unique_steps.append(step)
        
        return unique_steps[:5]  # Limit to 5 steps 